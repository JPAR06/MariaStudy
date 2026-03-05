# MariaStudy — Claude Context

RAG study app for Portuguese medical students. Built by João for Maria.
**Language everywhere: PT-PT** (not PT-BR).

---

## Architecture

```
MariaStudy/
├── src/          ← Core logic — modify carefully, keep logic intact
├── api/          ← FastAPI thin wrappers around src/
├── frontend/     ← Next.js 14 App Router UI
├── data/         ← Runtime data (persisted via Docker volume)
├── app.py        ← Old Streamlit UI (archived, not running)
└── docker-compose.yml  ← 2 services: api:8000 + web:3000
```

### The Rule
`src/` is the heart of the app. Modify it when needed (architecture improvements, adding features to the pipeline), but never break existing logic. The only imports allowed in `src/` are standard library, `groq`, `chromadb`, `sentence_transformers`, `pdfplumber`, `fitz`, `rank_bm25`, and `numpy` — **no Streamlit**.

---

## Stack

### Backend (`api/`)
- FastAPI + uvicorn
- All routes prefixed `/api`
- SSE streaming for file upload progress (ThreadPoolExecutor + asyncio.Queue)
- Pydantic models in `api/schemas.py`

### Frontend (`frontend/`)
- Next.js 14, App Router, TypeScript
- Tailwind CSS + shadcn/ui components
- Framer Motion (flashcard 3D flip, page transitions)
- @tanstack/react-query (server state, 30s staleTime)
- next-themes (dark mode, class strategy)
- Recharts (progress charts)
- All API calls through `frontend/lib/api.ts`
- API rewrites: `/api/*` → `http://api:8000/api/*` (via next.config.mjs)

### AI Models (Groq free tier)
- Q&A: `llama-3.3-70b-versatile` (config: `LLM_REASONING`)
- Flashcards/Quiz: `llama-3.3-70b-versatile` (config: `LLM_QUALITY`)
- Fast (topics, summaries, HyDE): `llama-3.1-8b-instant` (config: `LLM_FAST`)
- Vision (image captions): `llama-3.2-11b-vision-preview` (config: `LLM_VISION`)
- Embeddings: `paraphrase-multilingual-mpnet-base-v2` (local, sentence-transformers, multilingual)
- Vector DB: ChromaDB (persistent, `data/chroma_db/`)

### Singletons (no Streamlit)
`src/embedder.py`, `src/vectorstore.py`, and `src/llm.py` use module-level `_variable = None`
singletons initialised on first call. **No Streamlit dependency anywhere in the codebase.**
`api/_st_stub.py` has been deleted — do not recreate it.

---

## RAG Pipeline

### Chunking (`src/processor.py` + `src/config.py`)
- **CHUNK_SIZE = 400 words** (≈530 tokens), **CHUNK_OVERLAP = 50 words**
- Paragraph-aware: splits on `\n\n`, merges short paragraphs, sliding window for oversize blocks
- Each chunk tagged with: `file`, `page`, `chunk_index`, `subject_id`, `file_type`, `primary_topic`

### Topic Extraction (`src/rag.py → _refresh_topics_and_summary()`)
1. **TOC-first**: extracts chapter titles from PDF bookmark outline (`fitz.get_toc`) — instant and exact
2. **LLM fallback**: if TOC yields < 5 topics, sends early-page text to `LLM_FAST` for extraction
3. **Pre-computed chunk→topic**: after topics are finalised, `vectorstore.assign_topics_to_chunks()`
   assigns a `primary_topic` metadata field to every chunk using cosine similarity on stored embeddings

### Retrieval (`src/rag.py → get_topic_chunks()`)
- Tries metadata filter first: `where={"primary_topic": topic}` — fast and precise
- Falls back to full hybrid search if filtered results are sparse (< top_k/2)
- Hybrid search = BM25 (exact keyword) + vector (semantic) fused with RRF

---

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/subjects` | List / create subjects |
| DELETE | `/api/subjects/{id}` | Delete subject |
| POST | `/api/subjects/{id}/files` | Upload file (SSE progress stream) |
| DELETE | `/api/subjects/{id}/files/{name}` | Delete file |
| PUT | `/api/subjects/{id}/files/{name}/type` | Set file type |
| GET | `/api/files/{subject_id}/{filename}` | Serve raw PDF (for viewer) |
| POST | `/api/subjects/{id}/ask` | Q&A |
| POST | `/api/search` | Cross-subject search |
| POST | `/api/subjects/{id}/flashcards/generate` | Generate flashcards (SSE stream) |
| GET | `/api/subjects/{id}/flashcards` | Get all cards |
| GET | `/api/subjects/{id}/flashcards/due` | Get due cards |
| GET | `/api/subjects/{id}/flashcards/favorites` | Get favorites |
| POST | `/api/subjects/{id}/flashcards/{cid}/result` | Save SRS result |
| POST | `/api/subjects/{id}/flashcards/{cid}/favorite` | Toggle favorite |
| DELETE | `/api/subjects/{id}/flashcards/{cid}` | Delete card |
| POST | `/api/subjects/{id}/flashcards/import` | Import cards |
| POST | `/api/subjects/{id}/quiz/generate` | Generate quiz (SSE stream) |
| POST | `/api/subjects/{id}/quiz/result` | Save quiz result |
| GET | `/api/subjects/{id}/progress` | Progress stats |
| GET | `/api/digest` | Daily digest |

---

## Frontend Pages

```
app/
├── page.tsx                        ← Home: activity chart + UC list
└── [subjectId]/
    ├── page.tsx                    ← Unified workspace: Studio | Center | Fontes (NotebookLM-style)
    └── files/page.tsx              ← Upload (SSE progress) + file list
```

## Key Components

```
components/
├── layout/Sidebar.tsx              ← Subject selector, nav, dark mode toggle (collapsible)
└── shared/{PageHeader,TopicChip}.tsx
```

## Workspace Layout (`[subjectId]/page.tsx`)

Three-panel layout: **Estúdio** (left, 330px) | **Centro** (flex) | **Fontes** (right, 340px, hidden during flashcards/quiz)

Studio views: `dashboard` | `flashcards` | `quiz` | `qa` | `summary` | `notes` | `preview`

Inline components defined in the same file:
- `InlineFlashcardPlayer` — card flip + SRS buttons + PDF reference panel
- `QuizPlayer` — MCQ flow with answer reveal + PDF reference panel + loadingMore state
- `FeatureTile` — studio navigation grid
- `MinimalStatCard`, `MetricCard` — stat display
- `buildDailyActivity` — 14-day activity chart data

---

## Design System

**NotebookLM-inspired.** Inter font, charcoal dark, clean minimal.

```css
Dark (default): bg zinc-900/950, panels zinc-800/55, border zinc-700/50, primary blue-400
Light: bg #F2F2F7, card #FFFFFF, primary #4B7BE5, border rgba(0,0,0,0.07)
Panel border-radius: rounded-3xl (24px) | Buttons: rounded-full (pills)
```

CSS variables in `frontend/app/globals.css` as HSL values. Sidebar uses hardcoded zinc classes.
Custom utilities: `.backface-hidden` (needed for flashcard 3D flip).

### Tailwind custom classes (in tailwind.config.ts)
- `rounded-card` → 14px  (used in files page cards)
- `rounded-btn` → 10px
- `shadow-card` → subtle shadow (none in dark mode)

---

## Data (all in `data/`, mounted as Docker volume)

| File | Contents |
|------|----------|
| `data/subjects.json` | Subject metadata + topics list |
| `data/progress.json` | Quiz history per subject |
| `data/srs.json` | Flashcard SRS state (SM-2 algorithm) |
| `data/digest.json` | Daily digest cache (invalidated daily) |
| `data/uploads/{subject_id}/` | Raw uploaded PDFs |
| `data/chroma_db/` | ChromaDB vector embeddings + `primary_topic` metadata |

---

## Docker

```bash
docker compose up -d --build   # Start both services
docker compose logs -f api     # Debug backend
docker compose logs -f web     # Debug frontend
```

Services: `api` (port 8000) + `web` (port 3000).
Data persists in `./data/` on the host — never inside the container.

---

## Development (without Docker)

```bash
# Backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev   # runs on localhost:3000
```

---

## Rules for Future Changes

1. **PT-PT everywhere** — UI text, comments, variable names where sensible
2. **No Streamlit** — `src/` is clean Python. Module-level singletons only. `api/_st_stub.py` is gone.
3. **Keep the iOS design language** — no rounded-xl everywhere, use rounded-card/rounded-btn
4. **New API routes** go in the relevant `api/routes/*.py` file, add schema to `api/schemas.py`
5. **New pages** follow the existing pattern: `"use client"`, `params: { subjectId: string }` (Next.js 14 — not `use(params)`), useQuery for data
6. **No plotly** — recharts only for charts
7. **Citations always** — Q&A sources, flashcard `fonte` field, quiz `fonte` field
8. After any frontend change, run `npm run build` in `frontend/` to verify no errors before committing

---

## Codex

### Backend changes implemented

#### RAG Pipeline
- Chunk size increased: 300 → 400 words, overlap 30 → 50 words (better context for clinical content)
- TOC-first topic extraction: `processor.extract_toc()` reads PDF bookmark outline; LLM fallback if < 5 topics
- Pre-computed chunk→topic: `vectorstore.assign_topics_to_chunks()` runs after topic extraction, tags every chunk with `primary_topic` using cosine similarity on stored embeddings (no re-embedding cost)
- `get_topic_chunks()` tries `primary_topic` metadata filter first, falls back to full hybrid search
- `vectorstore.query()` and `hybrid_query()` now accept optional `topic_filter` parameter

#### Streamlit removal
- Removed `@st.cache_resource` from `src/embedder.py`, `src/vectorstore.py`, `src/llm.py`
- Replaced with module-level `_variable = None` singletons
- Deleted `api/_st_stub.py`
- Removed stub import from `api/main.py`

#### Streaming generation
- Quiz: `api/routes/quiz.py` streams one question per SSE event; frontend buffers until 5 ready
- Flashcards: `api/routes/flashcards.py` streams in batches of 3; frontend switches to study view after first batch

### UI changes implemented

#### Global navigation and layout
- Sidebar redesigned to a cleaner Notebook-style panel.
- Sidebar is collapsible and starts collapsed by default.
- Subject list in sidebar supports compact icon mode and expanded label mode.
- Subject cards in navigation/home now show UC state (`Ativa` / `Concluida`).

#### Subject workspace (`frontend/app/[subjectId]/page.tsx`)
- Unified workspace with Studio-driven views: Dashboard, Flashcards, Questionário, Q&A, Resumo, Notas, Preview PDF
- Studio feature tiles switch the center workspace.
- Sources panel supports collapsible groups (Tópicos, Ficheiros).
- Sources panel hidden during Flashcards/Quiz to maximise center space.

#### Flashcards UX
- Streaming generation: switches to study view after first 3 cards arrive
- Inline flashcard player with 3D flip animation (Framer Motion)
- SM-2 SRS: again / hard / good / easy ratings
- `Referencia` opens PDF viewer at cited page

#### Quiz UX
- Streaming generation: transitions to taking phase after 5 questions buffered
- `QuizPlayer` component with MCQ flow, answer reveal (green/red), explanation, PDF reference panel
- `loadingMore` prop disables "Próxima" button when on last question and more are still streaming

#### Home page
- Minimalist 2-column layout: UC list left + stacked activity chart right
- Multi-color 14-day chart separated by UC
- Searchable UC list with quick stats

### Known limitations / next tasks
- Home stacked chart uses latest `last_reviewed` only (not full daily flashcard log)
- Existing ChromaDB data does not have `primary_topic` metadata — only new uploads benefit
  from pre-computed topic filtering; existing data falls back to hybrid search automatically
- Chunk size change (300→400) applies to new uploads only; existing chunks not re-indexed

### Codex latest updates (benchmarking + upload progress)

#### Evaluation harness (new `eval/`)
- Added `eval/run_eval.py` to benchmark multiple RAG configs across:
  - retrieval latency (`retrieve_ms`)
  - optional answer latency (`answer_ms`)
  - retrieval quality (`hit_at_k`, `mrr_like`, `keyword_coverage`)
  - grounding quality (`citation_index_valid_ratio`)
  - optional LLM judge scores (`judge_correctness`, `judge_faithfulness`, `judge_completeness`)
- Added sample config matrix: `eval/configs.sample.json`
- Added sample dataset: `eval/dataset.sample.jsonl`
- Updated docs with run instructions and decision rule: `eval/README.md`
- Output format:
  - `eval/results/<timestamp>/rows.jsonl`
  - `eval/results/<timestamp>/summary.json`

Run examples:
```bash
python -m eval.run_eval --dataset eval/dataset.sample.jsonl --configs eval/configs.sample.json
python -m eval.run_eval --dataset eval/dataset.sample.jsonl --configs eval/configs.sample.json --with-answer
python -m eval.run_eval --dataset eval/dataset.sample.jsonl --configs eval/configs.sample.json --with-answer --with-judge
```

#### Upload/chunking progress sync improvements
- `src/rag.py` now reports real chunk-based progress for embedding and indexing phases.
- `src/vectorstore.py:add_chunks(...)` accepts `progress_cb` and reports batch progress during Chroma upserts.
- `src/processor.py` progress callback ordering aligned to `(step, pct)`.
- Frontend upload status now combines phase + chunk counters and includes an indeterminate running bar:
  - `frontend/app/[subjectId]/page.tsx`
  - `frontend/app/[subjectId]/files/page.tsx`
  - `frontend/app/globals.css` (upload animation utility)

#### Validation performed
- `npm run lint` (frontend) passed
- `python -m compileall src api` passed
- `python -m pytest -q tests/test_api_upload_progress.py` passed
- Eval smoke run completed successfully and wrote results to `eval/results/`

### Codex security + reliability audit fixes

#### Security hardening
- `api/auth.py` — logs CRITICAL warning when `SECRET_KEY` env var is missing (no silent weak default)
- `api/main.py` — CORS restricted to `ALLOWED_ORIGINS` env var (default `http://localhost:3000`), not `"*"`; `_safe_path()` guard on `serve_file` prevents directory traversal on the PDF endpoint
- `api/routes/files.py` — 200 MB hard cap on uploads; `PurePosixPath(filename).name` strips directory components from uploaded filenames

#### Data integrity
- `src/subjects.py` — full rewrite: `threading.Lock` for all read-modify-write ops; `_save()` uses atomic write (`tempfile.mkstemp` + `os.replace`) so a mid-write crash never corrupts `subjects.json`
- `src/progress.py` — same treatment: `_progress_lock` (PROGRESS_FILE) and `_srs_lock` (SRS_FILE) are independent so flashcard and quiz writes don't block each other; `_atomic_save()` helper; `_card_id()` upgraded from truncated MD5 to `sha256[:16]` (lower collision probability)

#### Schema validation
- `api/schemas.py` — `FileRecord.type`, `FileTypeUpdate.file_type`, `FlashcardResultRequest.result`, `QuizGenerateRequest.difficulty` are now `Literal[...]` types — Pydantic enforces valid values at API boundary

#### Performance
- `src/vectorstore.py` — BM25 index is now cached per `(subject_id, where_clause)` key; invalidated automatically on `add_chunks`, `delete_file_chunks`, `update_file_type`; repeated flashcard/quiz generation on same topic avoids rebuilding BM25 from full ChromaDB scan
- `src/rag.py` — `search_all_subjects()` now runs subject queries in parallel via `ThreadPoolExecutor(max_workers=4)`; search time scales with slowest subject, not sum of all subjects

#### Logging
- `api/main.py`, `api/auth.py` — already had logging; all API route files now have `logger = logging.getLogger(__name__)`
- Key operations logged: subject create/delete, file upload start/done, file delete, Q&A questions, flashcard/quiz generation start/done, import count, quiz results
- `src/subjects.py`, `src/progress.py` — error-level logs on JSON load failures; info-level on mutations

#### Validation performed
- `python -m compileall src api` — exit 0
- `npm run build` (frontend) — exit 0, all 6 pages generated cleanly
