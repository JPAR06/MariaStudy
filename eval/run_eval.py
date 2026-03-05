from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src import embedder, llm, vectorstore


@dataclass
class EvalConfig:
    name: str
    retrieval_mode: str = "hybrid"  # hybrid | vector
    top_k: int = 6
    max_distance: float = 0.75
    use_hyde: bool = True
    file_type: str | None = "notes"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {i}: {exc}") from exc
    return rows


def _load_configs(path: Path | None) -> list[EvalConfig]:
    if path is None:
        return [
            EvalConfig(name="hybrid_top6_dist075", retrieval_mode="hybrid", top_k=6, max_distance=0.75, use_hyde=True, file_type="notes"),
            EvalConfig(name="vector_top8_dist080", retrieval_mode="vector", top_k=8, max_distance=0.80, use_hyde=True, file_type="notes"),
            EvalConfig(name="hybrid_top6_nohyde", retrieval_mode="hybrid", top_k=6, max_distance=0.75, use_hyde=False, file_type="notes"),
        ]

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Configs JSON must be an array")

    out: list[EvalConfig] = []
    for obj in data:
        if not isinstance(obj, dict):
            raise ValueError("Each config entry must be an object")
        out.append(
            EvalConfig(
                name=str(obj.get("name") or "unnamed"),
                retrieval_mode=str(obj.get("retrieval_mode") or "hybrid"),
                top_k=int(obj.get("top_k", 6)),
                max_distance=float(obj.get("max_distance", 0.75)),
                use_hyde=bool(obj.get("use_hyde", True)),
                file_type=obj.get("file_type", "notes"),
            )
        )
    return out


def _retrieve(sample: dict[str, Any], cfg: EvalConfig) -> tuple[list[dict[str, Any]], float, str]:
    question = str(sample["question"])
    topic_filter = sample.get("topic_filter")
    subject_id = str(sample["subject_id"])

    retrieval_text = question
    if cfg.use_hyde:
        hyde = llm.hypothetical_answer(question, topic=topic_filter)
        if hyde:
            retrieval_text = hyde

    emb = embedder.embed([retrieval_text])[0]
    bm25_text = f"{topic_filter}: {question}" if topic_filter else question

    start = time.perf_counter()
    if cfg.retrieval_mode == "vector":
        chunks = vectorstore.query(
            subject_id,
            emb,
            top_k=cfg.top_k,
            file_type=cfg.file_type,
            max_distance=cfg.max_distance,
            topic_filter=topic_filter,
        )
    else:
        chunks = vectorstore.hybrid_query(
            subject_id,
            bm25_text,
            emb,
            top_k=cfg.top_k,
            file_type=cfg.file_type,
            max_distance=cfg.max_distance,
            topic_filter=topic_filter,
        )
    retrieve_ms = (time.perf_counter() - start) * 1000.0
    return chunks, retrieve_ms, retrieval_text


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _metrics_for_retrieval(chunks: list[dict[str, Any]], sample: dict[str, Any]) -> dict[str, Any]:
    expected_sources = sample.get("expected_sources") or []
    expected_keywords = sample.get("expected_keywords") or []

    hit_at_k = None
    mrr_like = None

    if expected_sources:
        rank_hits: list[int] = []
        for i, c in enumerate(chunks, start=1):
            meta = c.get("metadata") or {}
            for src in expected_sources:
                if not isinstance(src, dict):
                    continue
                sf = src.get("file")
                sp = src.get("page")
                if sf == meta.get("file") and sp == meta.get("page"):
                    rank_hits.append(i)
                    break
        hit_at_k = 1.0 if rank_hits else 0.0
        mrr_like = (1.0 / min(rank_hits)) if rank_hits else 0.0

    keyword_coverage = None
    if expected_keywords:
        corpus = _normalize_text("\n".join(c.get("text", "") for c in chunks))
        hits = 0
        for kw in expected_keywords:
            if _normalize_text(str(kw)) in corpus:
                hits += 1
        keyword_coverage = hits / max(len(expected_keywords), 1)

    return {
        "hit_at_k": hit_at_k,
        "mrr_like": mrr_like,
        "keyword_coverage": keyword_coverage,
    }


def _citation_index_valid_ratio(answer: str, n_chunks: int) -> float | None:
    cited = [int(x) for x in re.findall(r"\[(\d+)\]", answer or "")]
    if not cited:
        return None
    valid = sum(1 for idx in cited if 1 <= idx <= n_chunks)
    return valid / len(cited)


def _judge_answer(question: str, expected_answer: str, answer: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    context = "\n\n".join(
        f"[{i}] {c.get('text', '')}" for i, c in enumerate(chunks, start=1)
    )
    prompt = (
        "Score the model answer against the expected answer and provided context. "
        "Return strict JSON with keys correctness, faithfulness, completeness, rationale. "
        "Each score must be integer 0-5.\n\n"
        f"Question: {question}\n\n"
        f"Expected answer: {expected_answer}\n\n"
        f"Model answer: {answer}\n\n"
        f"Retrieved context:\n{context}"
    )
    raw = llm._chat(  # noqa: SLF001 - internal helper reuse for benchmarking
        model=llm.LLM_FAST,
        messages=[{"role": "user", "content": prompt}],
        json_mode=True,
        max_tokens=350,
    )
    parsed = json.loads(raw)
    return {
        "judge_correctness": int(parsed.get("correctness", 0)),
        "judge_faithfulness": int(parsed.get("faithfulness", 0)),
        "judge_completeness": int(parsed.get("completeness", 0)),
        "judge_rationale": str(parsed.get("rationale", ""))[:400],
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_cfg: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_cfg.setdefault(r["config"], []).append(r)

    summary: dict[str, Any] = {}
    for cfg, cfg_rows in by_cfg.items():
        def mean_of(key: str) -> float | None:
            values = [r[key] for r in cfg_rows if isinstance(r.get(key), (int, float))]
            return statistics.fmean(values) if values else None

        summary[cfg] = {
            "n": len(cfg_rows),
            "retrieve_ms_avg": mean_of("retrieve_ms"),
            "answer_ms_avg": mean_of("answer_ms"),
            "hit_at_k_avg": mean_of("hit_at_k"),
            "mrr_like_avg": mean_of("mrr_like"),
            "keyword_coverage_avg": mean_of("keyword_coverage"),
            "citation_index_valid_ratio_avg": mean_of("citation_index_valid_ratio"),
            "judge_correctness_avg": mean_of("judge_correctness"),
            "judge_faithfulness_avg": mean_of("judge_faithfulness"),
            "judge_completeness_avg": mean_of("judge_completeness"),
            "errors": sum(1 for r in cfg_rows if r.get("error")),
        }
    return summary


def run(dataset_path: Path, config_path: Path | None, with_answer: bool, with_judge: bool) -> Path:
    samples = _load_jsonl(dataset_path)
    configs = _load_configs(config_path)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("eval") / "results" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []

    total = len(samples) * len(configs)
    done = 0

    for sample in samples:
        for cfg in configs:
            done += 1
            sid = str(sample.get("id", "unknown"))
            print(f"[{done}/{total}] sample={sid} config={cfg.name}")

            row: dict[str, Any] = {
                "sample_id": sid,
                "subject_id": sample.get("subject_id"),
                "config": cfg.name,
                "retrieval_mode": cfg.retrieval_mode,
                "top_k": cfg.top_k,
                "max_distance": cfg.max_distance,
                "use_hyde": cfg.use_hyde,
                "file_type": cfg.file_type,
            }

            try:
                chunks, retrieve_ms, retrieval_text = _retrieve(sample, cfg)
                row["retrieve_ms"] = round(retrieve_ms, 2)
                row["retrieved_n"] = len(chunks)
                row["retrieval_preview"] = retrieval_text[:160]

                r_metrics = _metrics_for_retrieval(chunks, sample)
                row.update(r_metrics)

                answer = ""
                if with_answer:
                    t0 = time.perf_counter()
                    answer = llm.answer_question(chunks, str(sample["question"])) if chunks else ""
                    row["answer_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
                    row["citation_index_valid_ratio"] = _citation_index_valid_ratio(answer, len(chunks))
                    row["answer_preview"] = answer[:300]

                if with_judge:
                    if not with_answer:
                        raise ValueError("--with-judge requires --with-answer")
                    expected = str(sample.get("expected_answer") or "")
                    if expected and answer:
                        row.update(_judge_answer(str(sample["question"]), expected, answer, chunks))

            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"

            rows.append(row)

    rows_path = out_dir / "rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = _aggregate(rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nDone. Results written to: {out_dir}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG config benchmark (speed + quality).")
    parser.add_argument("--dataset", required=True, help="Path to JSONL dataset")
    parser.add_argument("--configs", default=None, help="Path to configs JSON")
    parser.add_argument("--with-answer", action="store_true", help="Generate answers for each sample/config")
    parser.add_argument("--with-judge", action="store_true", help="LLM judge scores (requires --with-answer)")
    args = parser.parse_args()

    run(
        dataset_path=Path(args.dataset),
        config_path=Path(args.configs) if args.configs else None,
        with_answer=bool(args.with_answer),
        with_judge=bool(args.with_judge),
    )


if __name__ == "__main__":
    main()
