# RAG Evaluation Harness

This folder provides a repeatable benchmark to compare retrieval configurations on:

- speed (retrieval and answer latency)
- retrieval quality (Hit@k, MRR-like, keyword coverage)
- optional answer quality via LLM-as-judge

## Files

- `eval/run_eval.py`: benchmark runner
- `eval/dataset.sample.jsonl`: sample dataset
- `eval/configs.sample.json`: sample config variants
- `eval/results/<timestamp>/`: output directory

## Dataset format (`jsonl`)

One JSON object per line:

```json
{
  "id": "sample-001",
  "subject_id": "1912e7c3",
  "question": "Qual e a causa mais comum de neuropatia diabetica?",
  "topic_filter": "Neuropatias",
  "expected_answer": "A forma mais comum e a polineuropatia sensitivo-motora distal simetrica.",
  "expected_keywords": ["polineuropatia", "distal", "simetrica"],
  "expected_sources": [{ "file": "Resumos_Neuro.pdf", "page": 120 }]
}
```

Fields:

- `id` (required)
- `subject_id` (required)
- `question` (required)
- `topic_filter` (optional)
- `expected_answer` (optional, for judge)
- `expected_keywords` (optional, deterministic retrieval metric)
- `expected_sources` (optional, deterministic retrieval metric)

## Config format (`json`)

```json
[
  {
    "name": "hybrid_top6_dist075",
    "retrieval_mode": "hybrid",
    "top_k": 6,
    "max_distance": 0.75,
    "use_hyde": true,
    "file_type": "notes"
  }
]
```

## Run

Retrieval-only benchmark:

```bash
python -m eval.run_eval --dataset eval/dataset.sample.jsonl --configs eval/configs.sample.json
```

Add answer generation latency:

```bash
python -m eval.run_eval --dataset eval/dataset.sample.jsonl --configs eval/configs.sample.json --with-answer
```

Add LLM judge scoring (requires `GROQ_API_KEY`):

```bash
python -m eval.run_eval --dataset eval/dataset.sample.jsonl --configs eval/configs.sample.json --with-answer --with-judge
```

## Output

Each run writes to `eval/results/<timestamp>/`:

- `rows.jsonl`: one row per sample x config
- `summary.json`: aggregated metrics per config

Main metrics:

- `retrieve_ms`, `answer_ms`
- `hit_at_k`, `mrr_like`
- `keyword_coverage`
- `citation_index_valid_ratio`
- judge scores (optional):
  - `judge_correctness` (0-5)
  - `judge_faithfulness` (0-5)
  - `judge_completeness` (0-5)

## Suggested decision rule

1. Reject configs with low retrieval grounding (`hit_at_k`, `mrr_like`, `keyword_coverage`).
2. If using judge, reject low-faithfulness configs first.
3. From remaining configs, pick the fastest (`retrieve_ms` then `answer_ms`).

This keeps retrieval meaningful while still optimizing latency.

## Threshold Gate (optional)

Use this to fail a build/run when quality drops below your accepted floor:

```bash
python -m eval.check_thresholds \
  --summary eval/results/<timestamp>/summary.json \
  --min-hit 0.60 \
  --min-keyword 0.50 \
  --min-faithfulness 3.0
```
