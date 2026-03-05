# RAG Evaluation — MariaStudy

A practical guide to understanding what the eval harness measures, how to interpret the results, and how to grow the benchmark into something that drives real RAG improvements.

---

## What the eval measures

The harness runs every dataset sample against every config and records:

| Metric | What it tells you | Requires |
|--------|------------------|----------|
| `retrieve_ms` | How long retrieval took (HyDE + vector/BM25 + RRF) | always |
| `answer_ms` | How long the LLM answer generation took | `--with-answer` |
| `hit_at_k` | Was any expected source file/page in the top-k chunks? (1 or 0) | `expected_sources` filled |
| `mrr_like` | How highly ranked was the first hit? (1/rank) | `expected_sources` filled |
| `keyword_coverage` | Fraction of expected keywords present in retrieved text | `expected_keywords` filled |
| `citation_index_valid_ratio` | Are in-text citations `[N]` pointing to real chunk indices? | `--with-answer` |
| `judge_correctness` | LLM rates answer correctness vs expected answer (0–5) | `--with-answer --with-judge` |
| `judge_faithfulness` | LLM rates whether answer is grounded in retrieved context (0–5) | `--with-answer --with-judge` |
| `judge_completeness` | LLM rates whether all key points are covered (0–5) | `--with-answer --with-judge` |

### The three eval tiers

```
Tier 1 (fast, free)     — retrieval only: latency + keyword coverage
Tier 2 (costs tokens)   — + answer generation: citation validity
Tier 3 (costs tokens²)  — + LLM judge: correctness, faithfulness, completeness
```

For day-to-day RAG tuning, Tier 1 + `keyword_coverage` is enough to catch regressions quickly. Run Tier 3 only when comparing fundamentally different configs.

---

## First run results (2026-03-03) — annotated

```
hybrid_top6_dist075:  retrieve_ms=253ms  retrieved_n=0  keyword_coverage=0.0
vector_top8_dist080:  retrieve_ms=46ms   retrieved_n=0  keyword_coverage=0.0
hybrid_top6_nohyde:   retrieve_ms=53ms   retrieved_n=0  keyword_coverage=0.0
```

**Root cause of retrieved_n=0**: The subject collection was either empty at eval time, or `max_distance=0.75` filtered everything out. The HyDE previews show the LLM was working — it just couldn't find matching chunks close enough.

**Key latency insight**: `hybrid_top6_dist075` took 437ms on the first sample, then 70ms on the second. The BM25 index was being rebuilt from a full ChromaDB scan on every call. This is now fixed — the BM25 index is cached per (subject_id, filter) and invalidated only on writes.

**HyDE cost**: ~200ms overhead (compare 437ms hybrid+HyDE vs 53ms hybrid+noHyDE on cold start). HyDE improves recall on semantic questions but adds latency. Worth benchmarking once you have ground-truth sources.

---

## Dataset format

One JSON object per line (`dataset.sample.jsonl`):

```jsonl
{
  "id": "sample-001",
  "subject_id": "1912e7c3",
  "question": "O que é a síndrome de Brown-Séquard?",
  "topic_filter": "Medula Espinal",
  "expected_answer": "É uma hemissecção medular...",
  "expected_keywords": ["hemissecção", "ipsilateral", "contralateral"],
  "expected_sources": [{"file": "Resumos_Neuro.pdf", "page": 47}]
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | unique string |
| `subject_id` | yes | must match a real subject in `data/subjects.json` |
| `question` | yes | question in PT-PT |
| `topic_filter` | no | topic name from the subject's topics list; enables pre-computed filter |
| `expected_answer` | no | reference answer for LLM judge |
| `expected_keywords` | no | list of terms that should appear in retrieved chunks |
| `expected_sources` | no | `[{"file": "...", "page": N}]` — enables hit@k and MRR |

---

## How to run

```bash
# Tier 1: retrieval only (free, ~seconds)
python -m eval.run_eval --dataset eval/dataset.sample.jsonl --configs eval/configs.sample.json

# Tier 2: + answer quality metrics (~1 Groq call per sample×config)
python -m eval.run_eval --dataset eval/dataset.sample.jsonl --configs eval/configs.sample.json --with-answer

# Tier 3: + LLM judge (~2 Groq calls per sample×config)
python -m eval.run_eval --dataset eval/dataset.sample.jsonl --configs eval/configs.sample.json --with-answer --with-judge
```

Results land in `eval/results/<timestamp>/`:
- `rows.jsonl` — one row per sample × config
- `summary.json` — aggregated means per config

---

## Config matrix explained

```json
[
  { "name": "hybrid_top6_dist075", "retrieval_mode": "hybrid", "top_k": 6, "max_distance": 0.75, "use_hyde": true,  "file_type": "notes" },
  { "name": "vector_top8_dist080", "retrieval_mode": "vector",  "top_k": 8, "max_distance": 0.80, "use_hyde": true,  "file_type": "notes" },
  { "name": "hybrid_top6_nohyde", "retrieval_mode": "hybrid", "top_k": 6, "max_distance": 0.75, "use_hyde": false, "file_type": "notes" }
]
```

| Parameter | What changing it tests |
|-----------|----------------------|
| `retrieval_mode` | BM25+vector fusion (hybrid) vs pure vector search |
| `top_k` | More chunks = better recall, more context tokens for LLM |
| `max_distance` | How strict the cosine similarity filter is (0=perfect, 1=unrelated) |
| `use_hyde` | HyDE hypothetical answer embedding vs raw question embedding |
| `file_type` | `"notes"` only vs `null` (notes+exercises) |

### Decision rule (from README)
1. Discard configs with `hit_at_k < 0.6` or `keyword_coverage < 0.5`
2. From survivors, discard `judge_faithfulness < 3.0` (hallucination risk)
3. Pick the fastest remaining config

---

## How to make the eval more useful

### 1. Fill in `expected_sources` — enables hit@k and MRR

After uploading a PDF, ask the Q&A panel a question, note which page the answer came from, then add it:

```jsonl
{"id": "sample-001", ..., "expected_sources": [{"file": "Resumos_Neuro.pdf", "page": 47}]}
```

Even one ground-truth source per sample transforms the eval from "did anything come back" to "did the right thing come back".

### 2. Increase dataset coverage

Target: **30–50 samples** covering:
- All major topics in the subject
- Mix of factual ("O que é X?"), reasoning ("Qual a diferença entre X e Y?"), and clinical ("Doente com X e Y — diagnóstico mais provável?")
- Edge cases: rare syndromes, drug names, numeric criteria (lab values, staging)

### 3. Add a relaxed-distance config

The first run showed `retrieved_n=0`. Add this to `configs.sample.json` to diagnose whether it's a distance threshold issue:

```json
{ "name": "hybrid_dist090", "retrieval_mode": "hybrid", "top_k": 6, "max_distance": 0.90, "use_hyde": true, "file_type": "notes" }
```

If this returns chunks and the current configs don't, the threshold needs recalibrating.

### 4. Add a no-file-type-filter config

To test whether restricting to `"notes"` is losing relevant exercise content:

```json
{ "name": "hybrid_no_filter", "retrieval_mode": "hybrid", "top_k": 6, "max_distance": 0.75, "use_hyde": true, "file_type": null }
```

### 5. Track regressions over time

After each significant RAG change (new chunk size, new embedding model, new topic assignment), run Tier 1 on the full dataset and compare `keyword_coverage_avg` and `retrieve_ms_avg` to the previous run. A drop in coverage means the change hurt retrieval — even if the change felt correct.

### 6. Clinical case questions

These are the hardest for RAG and the most useful for Maria:

```jsonl
{
  "id": "clinical-001",
  "question": "Doente de 45 anos com fraqueza assimétrica dos membros inferiores, arreflexia e perda de sensibilidade em luva e meia. Diagnóstico mais provável?",
  "expected_keywords": ["polineuropatia", "neuropatia periférica", "arreflexia"],
  "topic_filter": "Neuropatias"
}
```

---

## Limitations of the current implementation

| Limitation | Impact | Potential fix |
|-----------|--------|--------------|
| `hit_at_k` requires exact file+page match | Brittle for multi-page answers | Add page ± 1 tolerance |
| LLM judge uses `LLM_FAST` (8B model) | Judge scores may be noisy | Allow configuring judge model |
| No topic-assignment eval | Can't measure if `primary_topic` metadata is correct | Add `expected_topic` field + check chunk metadata |
| Single-turn only | Real usage is conversational (follow-up questions) | Add `conversation` field with prior turns |
| No cross-subject samples | Cross-subject search path not benchmarked | Add samples with `subject_id: "all"` |
| Results not compared to baseline automatically | Manual comparison of summary JSONs | Add a `compare` sub-command: `python -m eval.run_eval --compare dir1 dir2` |
