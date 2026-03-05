from __future__ import annotations

"""Opt-in ingest experiment pipeline.

This module is intentionally isolated from `src/rag.py` so we can benchmark
performance changes safely before adopting them in production.
"""

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src import embedder, processor, subjects, vectorstore
from src.config import DATA_DIR, UPLOADS_DIR


CACHE_INDEX = DATA_DIR / "file_cache_experimental.json"


@dataclass
class IngestExperimentOptions:
    file_type: str = "notes"
    enable_images: bool = False
    use_hash_cache: bool = True
    embed_batch_size: int = 0  # 0 => auto
    upsert_batch_size: int = 0  # 0 => auto


@dataclass
class IngestExperimentResult:
    chunks: int
    pages: int
    dedupe_hit: bool
    timings: dict[str, float]


def _load_cache() -> dict:
    if not CACHE_INDEX.exists():
        return {}
    try:
        return json.loads(CACHE_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    CACHE_INDEX.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=CACHE_INDEX.parent, prefix=".exp_cache_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, CACHE_INDEX)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _choose_embed_batch(total_chunks: int, forced: int) -> int:
    if forced > 0:
        return forced
    cpu = os.cpu_count() or 4
    if cpu <= 4:
        return 24
    if cpu <= 8:
        return 32 if total_chunks < 350 else 48
    return 48 if total_chunks < 350 else 64


def _choose_upsert_batch(total_chunks: int, forced: int) -> int:
    if forced > 0:
        return forced
    cpu = os.cpu_count() or 4
    if cpu <= 4:
        return 80
    if cpu <= 8:
        return 100 if total_chunks < 350 else 120
    return 120 if total_chunks < 350 else 160


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clone_from_cache(
    source_subject_id: str,
    source_filename: str,
    target_subject_id: str,
    target_filename: str,
    *,
    file_type: str,
    batch_size: int,
    progress_cb: Callable[[str, float], None] | None,
) -> tuple[int, int]:
    source = vectorstore.get_collection(source_subject_id)
    target = vectorstore.get_collection(target_subject_id)

    rows = source.get(where={"file": source_filename}, include=["documents", "metadatas", "embeddings"])
    docs = rows.get("documents") or []
    metas = rows.get("metadatas") or []
    embs = rows.get("embeddings") or []
    if not docs or not metas or not embs:
        return 0, 0

    ids: list[str] = []
    new_metas: list[dict] = []
    for m in metas:
        page = int(m.get("page", 1))
        idx = int(m.get("chunk_index", 0))
        ids.append(f"{target_filename}_{page}_{idx}")
        new_metas.append({
            **m,
            "file": target_filename,
            "subject_id": target_subject_id,
            "file_type": file_type,
        })

    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        target.upsert(
            ids=ids[i:end],
            documents=docs[i:end],
            metadatas=new_metas[i:end],
            embeddings=embs[i:end],
        )
        if progress_cb:
            pct = round(35 + (end / max(len(ids), 1)) * 60, 1)
            progress_cb(f"A reutilizar cache... {end}/{len(ids)} chunks", pct)

    pages = max((int(m.get("page", 1)) for m in new_metas), default=1)
    return len(ids), pages


def _add_chunks_batched(
    subject_id: str,
    chunks: list[dict],
    embeddings: list[list[float]],
    *,
    batch_size: int,
    progress_cb: Callable[[int, int], None] | None,
) -> None:
    col = vectorstore.get_collection(subject_id)
    ids = [
        f"{c['metadata']['file']}_{c['metadata']['page']}_{c['metadata']['chunk_index']}"
        for c in chunks
    ]
    texts = [c["text"] for c in chunks]
    metas = [c["metadata"] for c in chunks]

    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        col.upsert(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=texts[i:end],
            metadatas=metas[i:end],
        )
        if progress_cb:
            progress_cb(end, len(ids))


def ingest_file_experimental(
    subject_id: str,
    file_bytes: bytes,
    filename: str,
    options: IngestExperimentOptions | None = None,
    progress_cb: Callable[[str, float], None] | None = None,
) -> IngestExperimentResult:
    opts = options or IngestExperimentOptions()

    t0 = time.perf_counter()
    file_hash = _sha256(file_bytes)

    if progress_cb:
        progress_cb("A preparar...", 1)

    dest_dir = UPLOADS_DIR / subject_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / filename
    file_path.write_bytes(file_bytes)

    cache = _load_cache()
    cache_entry = cache.get(file_hash)
    upsert_batch = _choose_upsert_batch(1, opts.upsert_batch_size)

    if opts.use_hash_cache and isinstance(cache_entry, dict):
        source_subject_id = str(cache_entry.get("subject_id", ""))
        source_filename = str(cache_entry.get("filename", ""))
        if source_subject_id and source_filename:
            if progress_cb:
                progress_cb("A reutilizar embeddings de ficheiro igual...", 15)
            try:
                clone_start = time.perf_counter()
                chunks, pages = _clone_from_cache(
                    source_subject_id,
                    source_filename,
                    subject_id,
                    filename,
                    file_type=opts.file_type,
                    batch_size=upsert_batch,
                    progress_cb=progress_cb,
                )
                if chunks > 0:
                    subjects.add_file_to_subject(subject_id, filename, pages, opts.file_type)
                    if progress_cb:
                        progress_cb("Finalizar...", 99)
                    return IngestExperimentResult(
                        chunks=chunks,
                        pages=pages,
                        dedupe_hit=True,
                        timings={
                            "clone_s": round(time.perf_counter() - clone_start, 3),
                            "total_s": round(time.perf_counter() - t0, 3),
                        },
                    )
            except Exception:
                pass

    extract_start = time.perf_counter()
    caption_fn = None
    if opts.enable_images:
        from src import llm
        caption_fn = llm.caption_image

    chunks = processor.extract_file(
        str(file_path),
        subject_id,
        filename,
        caption_fn=caption_fn,
        progress_cb=progress_cb,
        file_type=opts.file_type,
    )
    extract_s = time.perf_counter() - extract_start

    if not chunks:
        return IngestExperimentResult(
            chunks=0,
            pages=0,
            dedupe_hit=False,
            timings={"extract_s": round(extract_s, 3), "total_s": round(time.perf_counter() - t0, 3)},
        )

    total_chunks = len(chunks)
    embed_batch = _choose_embed_batch(total_chunks, opts.embed_batch_size)
    upsert_batch = _choose_upsert_batch(total_chunks, opts.upsert_batch_size)

    texts = [c["text"] for c in chunks]

    embed_start = time.perf_counter()
    embs: list[list[float]] = []
    if progress_cb:
        progress_cb(f"A calcular embeddings... 0/{total_chunks} chunks", 46)
    for i in range(0, total_chunks, embed_batch):
        end = min(i + embed_batch, total_chunks)
        embs.extend(embedder.embed(texts[i:end]))
        if progress_cb:
            pct = round(46 + (end / max(total_chunks, 1)) * 32, 1)
            progress_cb(f"A calcular embeddings... {end}/{total_chunks} chunks", pct)
    embed_s = time.perf_counter() - embed_start

    index_start = time.perf_counter()
    if progress_cb:
        progress_cb(f"A indexar vetores... 0/{total_chunks} chunks", 79)
    _add_chunks_batched(
        subject_id,
        chunks,
        embs,
        batch_size=upsert_batch,
        progress_cb=(
            (lambda done, total: progress_cb(
                f"A indexar vetores... {done}/{total} chunks",
                round(79 + (done / max(total, 1)) * 19, 1),
            ))
            if progress_cb else None
        ),
    )
    index_s = time.perf_counter() - index_start

    pages = max((c["metadata"]["page"] for c in chunks), default=1)
    subjects.add_file_to_subject(subject_id, filename, pages, opts.file_type)

    cache[file_hash] = {
        "subject_id": subject_id,
        "filename": filename,
        "pages": pages,
        "chunks": total_chunks,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _save_cache(cache)

    if progress_cb:
        progress_cb("Finalizar...", 99)

    return IngestExperimentResult(
        chunks=total_chunks,
        pages=pages,
        dedupe_hit=False,
        timings={
            "extract_s": round(extract_s, 3),
            "embed_s": round(embed_s, 3),
            "index_s": round(index_s, 3),
            "total_s": round(time.perf_counter() - t0, 3),
            "embed_batch": float(embed_batch),
            "upsert_batch": float(upsert_batch),
        },
    )
