# Experimental Ingest (Safe Sandbox)

This folder is opt-in and does not change production routes/pipeline.

## Goal

Test ingest speed improvements safely before touching `src/rag.py`.

Implemented experiments:

- Adaptive embedding/upsert batch sizes (based on CPU + chunk count)
- File-hash dedupe cache (`data/file_cache_experimental.json`)
- Per-phase timing output (`extract_s`, `embed_s`, `index_s`, `total_s`)

## Run

```bash
python -m eval.run_ingest_experiment --subject-id <SUBJECT_ID> --file "C:\path\file.pdf" --mode experimental
```

Compare baseline vs experimental:

```bash
python -m eval.run_ingest_experiment --subject-id <SUBJECT_ID> --file "C:\path\file.pdf" --mode both
```

Disable dedupe cache:

```bash
python -m eval.run_ingest_experiment --subject-id <SUBJECT_ID> --file "C:\path\file.pdf" --mode experimental --no-cache
```

## Notes

- This is a sandbox path. Production upload still uses `src/rag.py`.
- Use a dedicated test subject for benchmarks.
