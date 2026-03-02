# MariaStudy — Claude Context

RAG study app for Portuguese medical students. Built by João for Maria.
**Language everywhere: PT-PT** (not PT-BR).

---

## Architecture

```
MariaStudy/
├── src/          ← NEVER TOUCH — core logic, all working
├── api/          ← FastAPI thin wrappers around src/
├── frontend/     ← Next.js 14 App Router UI
├── data/         ← Runtime data (persisted via Docker volume)
├── app.py        ← Old Streamlit UI (archived, not running)
└── docker-compose.yml  ← 2 services: api:8000 + web:3000
```

### The Golden Rule
**`src/` is sacred.** Never modify it. All changes happen in `api/` or `frontend/`.

---

## Critical: Streamlit Stub

`src/embedder.py`, `src/vectorstore.py`, and `src/llm.py` use `@st.cache_resource`.
They crash on import without Streamlit installed.

**Fix:** `api/_st_stub.py` must be the very first import in `api/main.py`:
```python
import api._st_stub  # noqa: F401  ← MUST be line 1
```
This injects a no-op mock into `sys.modules["streamlit"]` before any src/ import.
**Never remove this stub or move it below any src/ import.**

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
- Q&A: `deepseek-r1-distill-llama-70b` — strip `<think>` tags from output
- Flashcards/Quiz: `llama-3.3-70b-versatile`
- Fast (topics, summaries): `llama-3.1-8b-instant`
- Vision (image captions): `llama-3.2-11b-vision-preview`
- Embeddings: `paraphrase-multilingual-mpnet-base-v2` (local, sentence-transformers)
- Vector DB: ChromaDB (persistent, `data/chroma_db/`)

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
| POST | `/api/subjects/{id}/flashcards/generate` | Generate flashcards |
| GET | `/api/subjects/{id}/flashcards` | Get all cards |
| GET | `/api/subjects/{id}/flashcards/due` | Get due cards |
| GET | `/api/subjects/{id}/flashcards/favorites` | Get favorites |
| POST | `/api/subjects/{id}/flashcards/{cid}/result` | Save SRS result |
| POST | `/api/subjects/{id}/flashcards/{cid}/favorite` | Toggle favorite |
| DELETE | `/api/subjects/{id}/flashcards/{cid}` | Delete card |
| POST | `/api/subjects/{id}/flashcards/import` | Import cards |
| POST | `/api/subjects/{id}/quiz/generate` | Generate quiz |
| POST | `/api/subjects/{id}/quiz/result` | Save quiz result |
| GET | `/api/subjects/{id}/progress` | Progress stats |
| GET | `/api/digest` | Daily digest |

---

## Frontend Pages

```
app/
├── page.tsx                        ← Home: DailyDigest + subject grid
└── [subjectId]/
    ├── files/page.tsx              ← Upload (SSE progress) + file list
    ├── topics/page.tsx             ← Topic chips + AI summary
    ├── qa/page.tsx                 ← Chat + PDF side panel
    ├── flashcards/page.tsx         ← Study (3D flip) + Deck browser + Import
    ├── quiz/page.tsx               ← Config → MCQ → Results
    └── progress/page.tsx           ← Bar chart + SRS donut + topic bars
```

## Key Components

```
components/
├── layout/Sidebar.tsx              ← Subject selector, nav, dark mode toggle
├── home/DailyDigest.tsx            ← 4 metric cards (streak/due/weak/QoD)
├── home/SubjectCard.tsx
├── flashcard/FlashcardCard.tsx     ← Framer Motion rotateY 3D flip
├── flashcard/DeckBrowser.tsx       ← Filter/search card list
├── qa/ChatMessage.tsx              ← Citation chips
├── qa/PDFViewer.tsx                ← iframe side panel
└── shared/{PageHeader,TopicChip}.tsx
```

---

## Design System

**Apple/iOS-inspired.** Inter font, clean, minimal.

```css
Light: bg #FAFAFA, surface #FFFFFF, primary #007AFF, text #1D1D1F, muted #6E6E73, border #E5E5EA
Dark:  bg #000000, surface #1C1C1E, primary #0A84FF, border rgba(255,255,255,0.08)
Card border-radius: 14px  |  Button border-radius: 10px
```

CSS variables defined in `frontend/app/globals.css` as HSL values consumed by Tailwind.
Custom utilities: `.backface-hidden` (needed for flashcard 3D flip).

### Tailwind custom classes (in tailwind.config.ts)
- `rounded-card` → 14px
- `rounded-btn` → 10px
- `shadow-card` → subtle iOS-style shadow
- `text-success/warning/destructive` → semantic colors

---

## Data (all in `data/`, mounted as Docker volume)

| File | Contents |
|------|----------|
| `data/subjects.json` | Subject metadata + topics list |
| `data/progress.json` | Quiz history per subject |
| `data/srs.json` | Flashcard SRS state (SM-2 algorithm) |
| `data/digest.json` | Daily digest cache (invalidated daily) |
| `data/uploads/{subject_id}/` | Raw uploaded PDFs |
| `data/chroma_db/` | ChromaDB vector embeddings |

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
2. **Don't touch `src/`** — all logic is there and works
3. **`api/_st_stub.py` must stay** and be the first import in `api/main.py`
4. **Keep the iOS design language** — no rounded-xl everywhere, use rounded-card/rounded-btn
5. **New API routes** go in the relevant `api/routes/*.py` file, add schema to `api/schemas.py`
6. **New pages** follow the existing pattern: `"use client"`, `use(params)` for subjectId, useQuery for data
7. **No plotly** — recharts only for charts
8. **Citations always** — Q&A sources, flashcard `fonte` field, quiz `fonte` field
9. After any frontend change, run `npm run build` in `frontend/` to verify no errors before committing
