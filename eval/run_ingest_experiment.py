from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from experiments.ingest_experimental import IngestExperimentOptions, ingest_file_experimental
from src.rag import ingest_file


def run_baseline(subject_id: str, file_path: Path, file_type: str) -> dict:
    file_bytes = file_path.read_bytes()
    t0 = time.perf_counter()
    chunks = ingest_file(
        subject_id,
        file_bytes,
        file_path.name,
        enable_images=False,
        progress_cb=None,
        file_type=file_type,
    )
    total_s = round(time.perf_counter() - t0, 3)
    return {"mode": "baseline", "chunks": chunks, "total_s": total_s}


def run_experimental(subject_id: str, file_path: Path, file_type: str, use_cache: bool) -> dict:
    file_bytes = file_path.read_bytes()
    result = ingest_file_experimental(
        subject_id,
        file_bytes,
        file_path.name,
        options=IngestExperimentOptions(file_type=file_type, use_hash_cache=use_cache),
    )
    return {
        "mode": "experimental",
        "chunks": result.chunks,
        "pages": result.pages,
        "dedupe_hit": result.dedupe_hit,
        "timings": result.timings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline vs experimental ingest safely.")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--file-type", default="notes", choices=["notes", "exercises"])
    parser.add_argument("--mode", default="experimental", choices=["baseline", "experimental", "both"])
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    outputs = []
    if args.mode in {"baseline", "both"}:
        outputs.append(run_baseline(args.subject_id, file_path, args.file_type))
    if args.mode in {"experimental", "both"}:
        outputs.append(run_experimental(args.subject_id, file_path, args.file_type, not args.no_cache))

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
