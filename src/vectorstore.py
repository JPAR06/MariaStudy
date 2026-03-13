"""ChromaDB wrapper: one persistent collection per subject."""
import json
import logging
import threading

import chromadb

from src.config import CHROMA_DIR

logger = logging.getLogger(__name__)

_client = None

# BM25 cache to avoid rebuilding on every hybrid query.
_bm25_cache: dict[str, tuple] = {}
_bm25_lock = threading.Lock()


def _bm25_key(subject_id: str, where: dict | None) -> str:
    return f"{subject_id}:{json.dumps(where, sort_keys=True)}"


def _invalidate_bm25(subject_id: str):
    prefix = f"{subject_id}:"
    with _bm25_lock:
        stale = [k for k in _bm25_cache if k.startswith(prefix)]
        for k in stale:
            del _bm25_cache[k]


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def _col_name(subject_id: str) -> str:
    return f"subject_{subject_id}"


def get_collection(subject_id: str):
    return _get_client().get_or_create_collection(
        name=_col_name(subject_id),
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(subject_id: str, chunks: list[dict], embeddings: list, progress_cb=None):
    col = get_collection(subject_id)
    ids = [
        f"{c['metadata']['file']}_{c['metadata']['page']}_{c['metadata']['chunk_index']}"
        for c in chunks
    ]
    texts = [c["text"] for c in chunks]
    metas = [c["metadata"] for c in chunks]

    batch = 100
    for i in range(0, len(ids), batch):
        end = min(i + batch, len(ids))
        col.upsert(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=texts[i:end],
            metadatas=metas[i:end],
        )
        if progress_cb:
            progress_cb(end, len(ids))

    _invalidate_bm25(subject_id)


def _build_where(file_type: str | None, topic_filter: str | None) -> dict | None:
    conditions = []
    if file_type:
        conditions.append({"file_type": file_type})
    if topic_filter:
        conditions.append({"primary_topic": topic_filter})
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def query(
    subject_id: str,
    query_embedding: list,
    top_k: int = 6,
    file_type: str | None = None,
    max_distance: float = 0.75,
    topic_filter: str | None = None,
) -> list[dict]:
    col = get_collection(subject_id)
    count = col.count()
    if count == 0:
        return []

    where = _build_where(file_type, topic_filter)

    try:
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
            where=where,
        )
    except Exception as e:
        logger.debug("Filtered vector query failed (%s), retrying without where-clause", e)
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
        if dist <= max_distance
    ]


def _rrf_merge(list1: list[dict], list2: list[dict], top_k: int, k: int = 60) -> list[dict]:
    # Reciprocal Rank Fusion: score(d) = Σ 1/(k + rank(d) + 1), k=60 is the standard constant
    # Combines vector and BM25 rankings without requiring score normalisation.
    rrf_scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for rank, item in enumerate(list1):
        key = item["text"][:120]
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        items[key] = item

    for rank, item in enumerate(list2):
        key = item["text"][:120]
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        if key not in items:
            items[key] = item

    sorted_keys = sorted(rrf_scores, key=rrf_scores.__getitem__, reverse=True)
    return [items[k_] for k_ in sorted_keys[:top_k]]


def hybrid_query(
    subject_id: str,
    query_text: str,
    query_embedding: list,
    top_k: int = 6,
    file_type: str | None = None,
    max_distance: float = 0.75,
    topic_filter: str | None = None,
) -> list[dict]:
    from rank_bm25 import BM25Okapi

    col = get_collection(subject_id)
    count = col.count()
    if count == 0:
        return []

    vector_results = query(subject_id, query_embedding, top_k * 2, file_type, max_distance, topic_filter)

    where = _build_where(file_type, topic_filter)
    key = _bm25_key(subject_id, where)

    with _bm25_lock:
        cached = _bm25_cache.get(key)

    if cached is None:
        try:
            all_items = col.get(include=["documents", "metadatas"], where=where)
        except Exception as e:
            logger.debug("BM25 corpus filtered fetch failed (%s), using full collection", e)
            all_items = col.get(include=["documents", "metadatas"])

        docs = all_items.get("documents") or []
        metas = all_items.get("metadatas") or []
        if not docs:
            return vector_results[:top_k]

        tokenized_corpus = [d.lower().split() for d in docs]
        bm25 = BM25Okapi(tokenized_corpus)
        with _bm25_lock:
            _bm25_cache[key] = (docs, metas, bm25)
    else:
        docs, metas, bm25 = cached

    scores = bm25.get_scores(query_text.lower().split())
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k * 2]
    bm25_results = [
        {"text": docs[i], "metadata": metas[i], "distance": 0.0}  # BM25 has no distance metric; 0.0 is a sentinel
        for i in top_indices
        if scores[i] > 0
    ]

    return _rrf_merge(vector_results, bm25_results, top_k)


def delete_collection(subject_id: str):
    try:
        _get_client().delete_collection(_col_name(subject_id))
    except Exception as e:
        logger.debug("delete_collection(%s) failed (may not exist): %s", subject_id, e)
    _invalidate_bm25(subject_id)


def collection_count(subject_id: str) -> int:
    try:
        return get_collection(subject_id).count()
    except Exception as e:
        logger.debug("collection_count(%s) failed: %s", subject_id, e)
        return 0


def get_early_pages(subject_id: str, total_pages: int = 0, n: int = 20) -> list[dict]:
    col = get_collection(subject_id)
    if col.count() == 0:
        return []

    if total_pages > 0:
        max_page = max(3, min(15, round(total_pages * 0.03)))
    else:
        try:
            all_meta = col.get(include=["metadatas"])["metadatas"]
            doc_max = max((m.get("page", 1) for m in all_meta), default=1)
            max_page = max(3, min(15, round(doc_max * 0.03)))
        except Exception as e:
            logger.debug("Could not determine max page for %s: %s", subject_id, e)
            max_page = 10

    try:
        results = col.get(where={"page": {"$lte": max_page}}, include=["documents", "metadatas"])
        docs, metas = results["documents"], results["metadatas"]
        combined = sorted(zip(docs, metas), key=lambda x: (x[1].get("page", 0), x[1].get("chunk_index", 0)))
        return [{"text": d, "metadata": m} for d, m in combined[:n]]
    except Exception as e:
        logger.debug("get_early_pages(%s) failed: %s", subject_id, e)
        return []


def sample_spread(subject_id: str, n: int = 30) -> list[dict]:
    col = get_collection(subject_id)
    total = col.count()
    if total == 0:
        return []

    all_items = col.get(include=["documents", "metadatas"])
    docs = all_items["documents"]
    metas = all_items["metadatas"]
    if not docs:
        return []

    combined = sorted(zip(docs, metas), key=lambda x: (x[1].get("file", ""), x[1].get("page", 0), x[1].get("chunk_index", 0)))
    step = max(1, len(combined) // n)
    sampled = combined[::step][:n]
    return [{"text": d, "metadata": m} for d, m in sampled]


def get_page_chunks(subject_id: str, filename: str, page: int) -> list[str]:
    """Return all chunk texts from a specific file and page, sorted by chunk_index."""
    col = get_collection(subject_id)
    try:
        results = col.get(
            where={"$and": [{"file": {"$eq": filename}}, {"page": {"$eq": page}}]},
            include=["documents", "metadatas"],
        )
        docs = results.get("documents") or []
        metas = results.get("metadatas") or []
        paired = sorted(zip(docs, metas), key=lambda x: x[1].get("chunk_index", 0))
        return [d for d, _ in paired]
    except Exception:
        return []


def update_file_type(subject_id: str, filename: str, file_type: str):
    col = get_collection(subject_id)
    try:
        results = col.get(where={"file": filename}, include=["metadatas"])
        ids = results["ids"]
        if not ids:
            return
        new_metas = [{**m, "file_type": file_type} for m in results["metadatas"]]
        col.update(ids=ids, metadatas=new_metas)
        _invalidate_bm25(subject_id)
    except Exception as e:
        logger.debug("update_file_type(%s, %s) failed: %s", subject_id, filename, e)


def delete_file_chunks(subject_id: str, filename: str):
    col = get_collection(subject_id)
    try:
        col.delete(where={"file": filename})
        _invalidate_bm25(subject_id)
    except Exception as e:
        logger.debug("delete_file_chunks(%s, %s) failed: %s", subject_id, filename, e)


def assign_topics_to_chunks(subject_id: str, topics: list[str]) -> int:
    import numpy as np

    if not topics:
        return 0

    col = get_collection(subject_id)
    if col.count() == 0:
        return 0

    all_items = col.get(include=["metadatas", "embeddings"])
    ids = all_items.get("ids") or []
    metas = all_items.get("metadatas") or []
    chunk_embeddings = all_items.get("embeddings") or []

    if not ids or not chunk_embeddings:
        return 0

    from src.embedder import embed as _embed
    topic_embeddings = _embed(topics)

    t_embs = np.array(topic_embeddings, dtype=float)
    c_embs = np.array(chunk_embeddings, dtype=float)

    t_norms = np.linalg.norm(t_embs, axis=1, keepdims=True)
    c_norms = np.linalg.norm(c_embs, axis=1, keepdims=True)
    t_embs = t_embs / (t_norms + 1e-8)
    c_embs = c_embs / (c_norms + 1e-8)

    sims = c_embs @ t_embs.T
    best_idx = sims.argmax(axis=1)

    new_metas = [{**m, "primary_topic": topics[best_idx[i]]} for i, m in enumerate(metas)]

    batch = 100
    for i in range(0, len(ids), batch):
        col.update(ids=ids[i:i + batch], metadatas=new_metas[i:i + batch])

    _invalidate_bm25(subject_id)
    return len(ids)
