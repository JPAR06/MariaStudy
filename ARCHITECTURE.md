# MariaStudy — Architecture & Technical Overview

Study tool for Portuguese medical students. Built by João for Maria.
All UI text and LLM prompts are in **PT-PT** (European Portuguese, not Brazilian).

---

## System Overview

Three-layer architecture:

```
┌─────────────────────────────────────────────────────┐
│  Frontend (Next.js 14)          :3000               │
│  React SPA with Tailwind + shadcn/ui                │
├─────────────────────────────────────────────────────┤
│  API (FastAPI)                  :8000               │
│  Thin wrapper — calls src/ functions                │
├─────────────────────────────────────────────────────┤
│  src/ — Core Logic                                  │
│  RAG pipeline, LLM calls, SRS, data storage         │
└─────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
MariaStudy/
├── src/                         ← Core logic
│   ├── config.py                  Model names, paths, CHUNK_SIZE (400 words), CHUNK_OVERLAP (50)
│   ├── subjects.py                Subject CRUD (read/write subjects.json)
│   ├── processor.py               PDF/TXT/MD → text chunks (+ table/image extraction + TOC)
│   ├── embedder.py                SentenceTransformer singleton (multilingual)
│   ├── vectorstore.py             ChromaDB wrapper (one collection per subject, topic assignment)
│   ├── llm.py                     All Groq API calls with PT-PT prompts
│   ├── rag.py                     ingest_file(), ask(), get_topic_chunks(), delete_file()
│   └── progress.py                SRS/SM-2 flashcards + quiz history
│
├── api/                         ← FastAPI thin wrappers around src/
│   ├── main.py                    FastAPI app, CORS, lifespan startup
│   ├── schemas.py                 All Pydantic v2 request/response models
│   └── routes/
│       ├── auth.py                JWT login/register (bcrypt direct, not passlib)
│       ├── subjects.py            Subject CRUD routes
│       ├── files.py               File upload (SSE progress) + delete
│       ├── flashcards.py          Flashcard generation (SSE streaming) + SRS
│       ├── quiz.py                Quiz generation (SSE streaming) + results
│       ├── qa.py                  Q&A with citations
│       ├── progress.py            Progress stats (quiz history + SRS stats)
│       └── digest.py              Daily digest endpoint
│
├── frontend/                    ← Next.js 14 App Router UI
│   ├── app/
│   │   ├── layout.tsx             Root layout (Sidebar + main area)
│   │   ├── globals.css            CSS variables, custom utilities (.backface-hidden)
│   │   ├── page.tsx               Home: UC list + 14-day activity chart
│   │   └── [subjectId]/
│   │       ├── page.tsx           Workspace: Studio | Centro | Fontes panels
│   │       └── files/page.tsx     File upload (SSE progress) + file list
│   ├── components/
│   │   ├── layout/Sidebar.tsx     Collapsible subject nav + dark mode toggle
│   │   └── shared/                PageHeader, TopicChip
│   └── lib/
│       ├── api.ts                 Typed fetch wrapper for all API calls
│       ├── auth.ts                JWT token storage (localStorage)
│       └── utils.ts               cn(), clozeToBlank(), clozeHighlight()
│
├── data/                        ← Runtime data (Docker volume, never in container)
│   ├── subjects.json              Subject metadata + topics list
│   ├── progress.json              Quiz attempt history per subject
│   ├── srs.json                   Flashcard SRS state (SM-2 per card)
│   ├── digest.json                Daily digest cache (regenerated daily)
│   ├── uploads/{subject_id}/      Raw uploaded PDFs/TXTs
│   └── chroma_db/                 ChromaDB vector embeddings + primary_topic metadata
│
└── docker-compose.yml           ← api:8000 + web:3000
```

---

## RAG Pipeline — How Content Is Indexed and Retrieved

### 1. File Ingestion (`src/rag.py → ingest_file()`)

When Maria uploads a file:

1. **Processor** (`src/processor.py`) reads the file:
   - **PDF**: PyMuPDF extracts text page by page. Tables detected via heuristics → converted to Markdown. Images extracted and captioned by the vision LLM.
   - **TXT/MD**: Read directly.
2. **Chunking**: Text split into ~400-word chunks (`CHUNK_SIZE = 400`) with 50-word overlap. Paragraph-aware: respects `\n\n` boundaries, merges short paragraphs, sliding window for oversize blocks. Each chunk tagged with: `file`, `page`, `subject_id`, `file_type` (`notes` or `exercises`).
3. **Embedding**: Each chunk embedded using `paraphrase-multilingual-mpnet-base-v2` (local model, supports PT + EN). Model loaded once at startup via module-level singleton.
4. **Storage**: Chunks upserted into ChromaDB. One collection per subject. Embeddings persisted to `data/chroma_db/`.
5. **Topic extraction** (background): `_refresh_topics_and_summary()` runs after ingestion:
   - **TOC-first**: reads PDF bookmark outline (`fitz.get_toc`) — exact chapter titles, instant, free
   - **LLM fallback**: if TOC yields < 5 topics, sends early-page text to `LLM_FAST`
   - **Pre-computes `primary_topic`** for every chunk using cosine similarity on stored embeddings (no re-embedding cost). Stored in ChromaDB metadata.
6. **Summary**: Generated from spread sample using `LLM_QUALITY`.

**Progress events** are streamed via SSE during upload so the UI shows a live progress bar.

### 2. Retrieval (`src/rag.py → get_topic_chunks()`)

For quiz/flashcard generation and Q&A:

1. The query (topic name or question) is embedded.
2. **Primary-topic filter** (when available): chunks pre-filtered by `primary_topic` metadata — fast and precise. Falls back to full search if < top_k/2 results.
3. **HyDE** (Hypothetical Document Embedding): For Q&A, first generate a short "hypothetical textbook passage" that would answer the question, then embed *that*. This puts the query vector in "answer space", much closer to stored chunk vectors.
4. **Hybrid search** = BM25 (exact keyword matching for drug names, criteria, lab values) + vector search (semantic similarity), fused with Reciprocal Rank Fusion (RRF).

---

## LLM Model Choices (Groq Free Tier)

All inference via [Groq API](https://console.groq.com) — zero cost, very fast.

| Role | Model | Used For |
|------|-------|----------|
| `LLM_REASONING` | `llama-3.3-70b-versatile` | Q&A with citations |
| `LLM_QUALITY` | `llama-3.3-70b-versatile` | Flashcard + Quiz generation, summaries |
| `LLM_FAST` | `llama-3.1-8b-instant` | Topic extraction, HyDE |
| `LLM_VISION` | `llama-3.2-11b-vision-preview` | Image/figure captioning in PDFs |
| Embeddings | `paraphrase-multilingual-mpnet-base-v2` | Local, sentence-transformers library |

All prompts are written in PT-PT with explicit instructions to avoid Brazilian Portuguese.

---

## Flashcard System

### Generation (SSE Streaming)

`POST /api/subjects/{id}/flashcards/generate` streams cards as they're created:

1. Endpoint generates cards in **batches of 3** (one LLM call per batch).
2. Each batch call asks the LLM for 2 basic cards + 1 cloze card.
3. Each card is emitted as an SSE event immediately after generation.
4. Frontend shows the first 3 cards as soon as they arrive (switches to study view), while the remaining batches load in the background.

**Card types:**
- **Basic**: Question on front, answer on back. Clinical mechanism or definition questions.
- **Cloze**: Sentence with `{{c1::term}}` blank on front, complete sentence on back. Tests fill-in-the-blank recall.

### SRS Algorithm (SM-2 variant in `src/progress.py`)

Each card has: `interval` (days), `ease` (multiplier), `reps` (review count).

After each review, Maria rates herself:

| Rating | Effect |
|--------|--------|
| **1 · Outra vez** | Reset interval to 1d, ease −0.20 |
| **2 · Difícil** | interval × 1.2, ease −0.15 |
| **3 · Bom** | interval × ease (normal advance) |
| **4 · Fácil** | interval × ease × 1.3, ease +0.15 |

Card status is computed dynamically:
- `nova` → 0 reps
- `dominada` → interval ≥ 21 days
- `para rever` → next_review ≤ today AND reps > 0
- `a aprender` → reviewed but not yet due

**Card storage**: Keyed by `md5(frente)[:12]` in `data/srs.json`.

### Citation (fonte field)

Every card has a `fonte` string like `"Apontamentos_Neuro.pdf, Pág. 12"`. The flashcard player parses this and offers a "Ver referência" button that opens the PDF at that exact page in an iframe.

---

## Quiz System

### Generation (SSE Streaming)

`POST /api/subjects/{id}/quiz/generate` streams questions one-by-one:

1. Makes **one LLM call per question** (N=1 per call) for maximum responsiveness.
2. Each question emitted as SSE event immediately.
3. Frontend **buffers until 5 questions arrive** (or fewer if quizN < 5), then transitions to quiz view.
4. Remaining questions continue loading while Maria is answering the first ones.
5. The "Próxima →" button shows "A carregar…" and is disabled if Maria reaches the last loaded question and more are still streaming.

**Difficulty levels:**
- **Fácil**: Memory/definition questions with clearly distinct distractors.
- **Médio**: Comprehension + application — relate two concepts, explain a mechanism.
- **Difícil**: Clinical reasoning with case vignette (age/sex/symptoms) + differential diagnosis. Distractors share overlapping features.

Each question has: `pergunta`, `opcoes` (4 options), `correta` (0-3 index), `explicacao` (why correct), `fonte` (PDF source).

### Quiz Results

After the last question, `onFinish(answers)` is called → saves to `progress.json` (topic, score, pct, date). Results show score, percentage with colour coding (≥80% green, ≥60% amber, <60% red), and per-question breakdown with correct answers revealed for wrong ones.

---

## Q&A System

`POST /api/subjects/{id}/ask`:

1. Maria's question is embedded with HyDE enhancement.
2. Top-8 chunks retrieved via hybrid search from ChromaDB.
3. Chunks formatted as numbered references: `[1] text\n(Fonte: file.pdf, Pág. N)`.
4. `llama-3.3-70b-versatile` generates a detailed answer with inline citations `[1][2]` and a sources list.
5. Source citations are clickable chips → clicking opens the PDF at that page in the Sources panel.

---

## Topics System

Topics are extracted during file ingestion in two ways:

1. **TOC extraction** (`processor.extract_toc()`): reads PDF bookmark outline with `fitz.get_toc()`. Returns level-1 chapter headings (falls back to level-2 for flat documents). Fast and exact.
2. **LLM extraction** (fallback): if TOC yields < 5 topics, early-page text sent to `LLM_FAST` to extract 10-15 broad topic headings.

After topics are finalised, `vectorstore.assign_topics_to_chunks()` assigns a `primary_topic` field to every chunk using cosine similarity on already-stored embeddings (no re-embedding cost). This enables fast metadata-filtered retrieval.

In the UI, topics appear in the Sources panel (Fontes) as clickable chips that scope all studio views.

---

## Authentication

`POST /api/auth/login` + `POST /api/auth/register`:

- Passwords hashed with `bcrypt` directly (not passlib — bcrypt 5.0.0 from ChromaDB breaks passlib 1.7.4).
- JWT issued on login (HS256, 30-day expiry), stored in `localStorage`.
- All API routes except `/api/auth/*` and `GET /api/files/{subject_id}/{filename}` require `Authorization: Bearer <token>`.
- The file serve endpoint is intentionally public (no auth) because iframes cannot send custom headers.
- Next.js middleware excludes `/api/*` paths from redirect-to-login to avoid intercepting FastAPI calls.

---

## UI Architecture

### Workspace Page (`[subjectId]/page.tsx`)

Three-panel layout (hidden Sources panel during Flashcards/Quiz):

```
┌─────────────┬───────────────────────┬──────────────┐
│  Estúdio    │  Centro               │  Fontes      │
│  (330px)    │  (flex)               │  (340px)     │
│             │                       │              │
│  Nav tiles  │  Dashboard / Flash /  │  Topics      │
│  SRS stats  │  Quiz / Q&A / etc.    │  Files       │
└─────────────┴───────────────────────┴──────────────┘
```

**Studio views:** `dashboard` | `flashcards` | `quiz` | `qa` | `summary` | `notes` | `preview`

All inline in one file — no separate page routes for each view. State managed with `useState` at the page level.

### Key UI Patterns

- **SSE Streaming**: File upload, flashcard generation, quiz generation all use `fetch()` + `ReadableStream` reader loop. No `EventSource` (to support auth headers).
- **Quiz buffering**: Waits for min(5, N) questions before showing quiz. "Próxima →" disabled when on last loaded question and more are streaming.
- **3D Flashcard flip**: Framer Motion `rotateY` animation with `transformStyle: preserve-3d` + `.backface-hidden` CSS utility.
- **Animated PDF panel**: `motion.div` with `animate={{ height: open ? 540 : 0 }}` for smooth slide-down of the citation iframe.
- **React Query**: All server data fetched with `useQuery`, 30s staleTime.

### Design System

Inspired by NotebookLM. Dark-first (zinc palette), Inter font.

- `bg: zinc-900/950` | panels: `zinc-800/55` | border: `zinc-700/50`
- Primary: `blue-400` | amber for due/warnings | emerald for success
- `rounded-3xl` for panels | `rounded-full` for pills/buttons | `rounded-2xl` for cards within panels

---

## Data Files

| File | Format | Contents |
|------|--------|----------|
| `data/subjects.json` | `{id: {name, created_at, files: [...], topics: [...], summary, status}}` | Subject metadata |
| `data/progress.json` | `{subject_id: [{date, topic, score, total, pct}]}` | Quiz attempt history |
| `data/srs.json` | `{subject_id: {card_md5: {frente, verso, fonte, interval, ease, reps, ...}}}` | Flashcard SRS state |
| `data/digest.json` | `{date, streak, due_total, weak_topic, question_of_day}` | Cached daily digest |

All files are JSON, UTF-8, human-readable. Mounted as Docker volume → persist across container rebuilds.

---

## Docker Services

```yaml
api:   FastAPI + uvicorn    port 8000
web:   Next.js standalone   port 3000
```

Next.js rewrites `/api/*` → `http://api:8000/api/*` (configured in `next.config.mjs`).

```bash
docker compose up -d --build    # rebuild and start
docker compose logs -f api      # debug backend
docker compose logs -f web      # debug frontend
```

---

## Critical Implementation Notes

### Singleton Pattern

`src/embedder.py`, `src/vectorstore.py`, and `src/llm.py` use module-level singletons:

```python
_instance = None

def get_instance():
    global _instance
    if _instance is None:
        _instance = ...create...
    return _instance
```

Thread-safe for read-heavy workloads. The embedding model loads once at startup via `lifespan` in `api/main.py`.

### Flashcard Card ID

Cards are identified by `md5(frente.encode())[:12]`. Changing a card's front text creates a new card. This is intentional — deduplication happens on generation.

### Quiz Score Saving

Quiz results are saved **after** the user finishes all questions (in the `onFinish` callback), not after each question. The score is computed on the frontend from the answers array.

### Pre-computed Chunk Topics

`vectorstore.assign_topics_to_chunks()` uses **stored embeddings** from ChromaDB (`col.get(include=["embeddings"])`). No re-embedding needed — pure matrix multiply on already-computed vectors. Fast for collections up to ~10k chunks.

Existing collections (uploaded before this feature) do not have `primary_topic` metadata. `get_topic_chunks()` automatically falls back to full hybrid search for those.

### bcrypt Direct (not passlib)

bcrypt 5.0.0 (pulled in by ChromaDB) breaks passlib 1.7.4. Auth uses `bcrypt.hashpw()` / `bcrypt.checkpw()` directly.

### Groq Rate Limits (Free Tier)

- `llama-3.3-70b-versatile`: ~30 req/min, ~6000 tokens/min
- `llama-3.1-8b-instant`: ~30 req/min, ~30000 tokens/min
- Quiz streaming makes N sequential calls (1 question each). For N=10, all within rate limits.
- If rate limited, questions are silently skipped (error caught per-question).
