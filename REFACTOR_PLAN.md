# MariaStudy — Refactor Plan
> Focus: deliver the best possible study experience for Maria. Ship fast, iterate.

---

## The Problem With What We Have

Streamlit was the right tool to build fast. It is the wrong tool to build great.
The ceiling is low: layout is rigid, components can't be composed, animations don't exist,
and every interaction does a full Python rerun. For a study app that a student uses daily
for hours, this matters enormously.

The goal is not to rebuild for the sake of it — it is to build something Maria opens
every day because it feels good to use, and that actually makes her study better.

---

## New Architecture

### Frontend — Next.js 14 (App Router) + Tailwind CSS
**Why not Reflex / Streamlit / Gradio:**
Reflex is still immature and has rough edges. Streamlit is a dead end for real UI.
Gradio is for demos. Next.js is what Quizlet, Notion, Linear and every serious web
product is built on. It compiles to static assets, has excellent TypeScript support,
and with Tailwind you can implement any Apple-level design in hours.

João writes Python. The frontend will be ~20% of the codebase and mostly HTML/Tailwind
with minimal logic. The backend stays Python. This is a clean separation.

**Stack:**
- Next.js 14 (App Router, React Server Components)
- Tailwind CSS + shadcn/ui (pre-built accessible components, fully customizable)
- Framer Motion (subtle animations — card flips, page transitions)
- React Query (server state, caching)

### Backend — FastAPI
The existing `src/` modules (rag.py, llm.py, vectorstore.py, embedder.py, progress.py)
stay **100% unchanged**. Only `app.py` is replaced — by FastAPI routes.

```
src/           ← untouched
├── rag.py
├── llm.py
├── vectorstore.py
├── embedder.py
├── progress.py
├── processor.py
└── subjects.py

api/           ← new
├── main.py         (FastAPI app, CORS, mounts)
├── routes/
│   ├── subjects.py
│   ├── files.py
│   ├── qa.py
│   ├── flashcards.py
│   ├── quiz.py
│   └── progress.py
└── schemas.py      (Pydantic models)

frontend/      ← new (Next.js)
├── app/
│   ├── layout.tsx
│   ├── page.tsx          (home)
│   ├── [subject]/
│   │   ├── qa/
│   │   ├── flashcards/
│   │   ├── quiz/
│   │   └── progress/
└── components/
    ├── Flashcard.tsx
    ├── PDFViewer.tsx
    ├── ConceptMap.tsx
    └── ...
```

### Storage
Keep for now:
- ChromaDB (vector store) — works well, no reason to change
- JSON files (subjects, progress, SRS) — fine for single user

When going multi-user later: PostgreSQL + Alembic migrations. The JSON → SQL
migration is one script. Don't over-engineer now.

### Deployment
- Docker Compose: FastAPI container + Next.js container (or Next.js built to static + served by nginx)
- Linux laptop server (as planned)
- ngrok static domain for access

---

## Design Language

**Inspiration:** Apple Notes, Linear, Vercel dashboard, Anki (functionality) + Quizlet (feel).

**Principles:**
- Every screen has one primary action. No clutter.
- Dark mode is first-class, not an afterthought.
- Motion is functional — card flips should feel physical.
- Information hierarchy through weight and spacing, not borders.
- Never make Maria think about the tool. She should think about medicine.

**Typography:** Inter (already in place). SF Pro is Apple's but Inter is the web equivalent.

**Colors:**
```
Light:  background #FAFAFA, surface #FFFFFF, primary #007AFF, text #1D1D1F
Dark:   background #000000, surface #1C1C1E, elevated #2C2C2E, primary #0A84FF
```

---

## Feature Roadmap

### Already Done (keep, polish)
- RAG Q&A with citations
- Hybrid search (BM25 + vector)
- SRS flashcards (SM-2, 4 ratings)
- Cloze cards
- Deck browser + import
- Quiz with MCQ
- Progress tracking
- Cross-subject search
- "Toda a UC" topic option

---

### Phase 1 — Core UX Upgrades (the refactor sprint)

#### 1. Heading-Aware PDF Chunking
**What:** During ingest, detect document structure (headings, numbered sections) and tag
each chunk with its parent section. Store `section` and `subsection` in ChromaDB metadata.

**Detection strategy (in order of reliability):**
1. pdfplumber font size analysis — headings are typically larger/bolder
2. Regex patterns for numbered sections: `1.`, `1.1`, `CAPÍTULO`, `SECÇÃO`
3. TOC cross-reference — if TOC exists, map page ranges to sections
4. LLM fallback for unstructured docs (current approach)

**Why it matters:** Topic → chunks becomes a metadata filter, not a semantic guess.
Flashcards for "Síndrome Nefrótico" use *only* those chunks. Precision goes up dramatically.

**Fallback:** Unstructured PDFs silently use current semantic search. User experience
is identical, just slightly less precise. Truthfulness is never compromised either way
(RAG always answers from real document content).

#### 2. PDF Viewer with Page Pinning
**What:** When a flashcard or Q&A answer shows a source (file + page), the user can
click "Ver no PDF" to open a side-by-side view with the PDF at that exact page.

**Implementation:**
- Files already stored in `data/uploads/{subject_id}/`
- FastAPI serves files via `/api/files/{subject_id}/{filename}` endpoint
- Next.js embeds PDF using `<iframe src="/api/files/...#page=12">`
- Side-by-side layout: answer on left, PDF on right, collapsible

**Phase 2 upgrade:** PDF.js for in-page text highlighting — the exact sentence that
generated the answer is highlighted in yellow. This would be completely unique in
the study app market.

#### 3. Study Session Mode
**What:** A focused study session with a timer, session goal, and end-of-session report.

**UX:** User picks a UC + estimated time → enters a distraction-free fullscreen mode →
at the end gets a summary card: "45 min studied · 23 flashcards · 3 weak spots found."

**Data:** Sessions stored in progress.json. Feeds the analytics dashboard.

**Why:** Top performers (Quizlet, Forest) know that the *feeling* of accomplishment
after a session is a core retention driver. A summary card is motivating.

#### 4. Clinical Case Mode *(completely new in market)*
**What:** The AI generates a mini clinical case from Maria's own notes and asks her
to diagnose, investigate, and treat — all grounded in her study materials.

**Example output:**
```
Caso Clínico — Nefrologia

Doente do sexo feminino, 8 anos, com edema periorbitário matinal,
proteinúria nefrótica (++++) e hipoalbuminemia (1.8 g/dL).
Sem hematúria. PA normal.

1. Qual o diagnóstico mais provável?
2. Qual o exame que confirmaria o diagnóstico?
3. Qual a primeira linha de tratamento?
```

Answer is evaluated by the LLM against the source chunks. Feedback includes what
she got right, what she missed, and which pages to review.

**Why it's different:** No study app generates clinical cases from your own notes.
This is the intersection of RAG + medical education that doesn't exist yet.
For medical students, this is exam simulation at its best.

#### 5. Weak Spot Radar
**What:** A visual dashboard showing which topics Maria struggles with, based on
flashcard history and quiz scores.

**Display:** Radar/spider chart (Recharts in Next.js) with one axis per topic.
Strong topics are full, weak topics are sunken. Clicking a weak topic goes straight
to targeted flashcards for that topic.

**Algorithm:** Weight quiz errors (×2) + flashcard "Again" ratings (×1.5) + days
since last correct review. Topics with highest weighted score = weakest.

**Why it matters:** This is what a private tutor does — identifies the gaps and
directs study effort. No generic study app does this with RAG-backed specificity.

#### 6. Smart Daily Digest
**What:** When Maria opens the app, the home screen shows:
- Cards due for review today (SRS)
- Weak spot of the day (one topic to focus on)
- A "question of the day" generated from her notes
- Streak counter

**Why:** Habit formation. The best apps (Duolingo, Anki) make you want to open them
daily. A personalised digest is the hook.

---

### Phase 2 — Scale & Polish (after Phase 1 ships)
- Multi-user auth (NextAuth.js + per-user data isolation)
- PostgreSQL replacing JSON files
- PDF annotation (highlight → create flashcard from selection)
- Collaborative decks (share flashcard collections between students)
- Mobile-responsive (or React Native app)
- Exam simulation (full timed mock exam, final grade, detailed breakdown)
- Knowledge graph visualisation (topics as nodes, relationships as edges)
- Voice Q&A (Web Speech API — speak your question)
- Offline mode (PWA + cached content)

---

## Migration Strategy

The migration is non-destructive. `src/` never changes.

1. Build FastAPI wrapper around existing `src/` functions (1-2 days)
2. Build Next.js frontend calling the API (replaces app.py entirely)
3. Run both in Docker Compose — old Streamlit app stays running until new is verified
4. Switch ngrok domain to new frontend port
5. Delete Streamlit app.py

Data migration: zero. ChromaDB and JSON files are untouched.

---

## What Makes This a Top University App

The honest answer: **RAG on your own documents + SRS + clinical cases** is a
combination that doesn't exist in any product on the market.

- Anki: SRS ✓, AI ✗, your docs ✗
- Quizlet: UI ✓, AI ✓ (premium), your docs ✗, SRS ✗
- NotebookLM: RAG ✓, your docs ✓, flashcards ✗, SRS ✗, clinical cases ✗
- Osmosis: Medical ✓, your docs ✗, expensive ✗

MariaStudy with Phase 1 done: RAG ✓, your docs ✓, SRS ✓, clinical cases ✓,
PDF viewer ✓, weak spot detection ✓, zero cost ✓.

That is the gap. Fill it with a great UI and you have something real.

---

## Immediate Next Steps (tomorrow)

1. Set up Next.js project inside `frontend/`
2. Set up FastAPI in `api/` wrapping existing `src/`
3. Design the component library (Flashcard, PDFViewer, NavSidebar) in Tailwind
4. Port pages one by one, starting with Flashcards (most used) and Q&A
5. Implement heading-aware chunking in `src/processor.py`
6. Implement Clinical Case Mode in `src/llm.py` + new page

---

*Last updated: 2026-03-02*
