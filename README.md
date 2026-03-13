# MariaStudy

AI-powered RAG study assistant for medical students. Upload your lecture notes and get personalized Q&A with citations, auto-generated flashcards (SRS/SM-2), and adaptive quizzes — all in European Portuguese.

Built to run at zero marginal cost: Groq free tier LLMs, local sentence-transformers embeddings, and file-based storage.

→ See [ARCHITECTURE.md](ARCHITECTURE.md) for a full breakdown of every design decision.

---

## Features

- **RAG Q&A** — ask questions about your notes, get cited answers with source page references
- **Flashcard generation** — auto-generates basic + cloze cards from your content, streamed via SSE
- **Spaced repetition (SM-2)** — review cards on the optimal schedule; Anki `.apkg` export
- **Quiz generation** — multiple-choice quizzes at three difficulty levels (Fácil / Médio / Difícil)
- **Topic extraction** — reads PDF bookmark outlines (TOC) first; LLM fallback for unstructured docs
- **Daily digest** — personalized summary of what's due and where gaps are
- **Hybrid retrieval** — BM25 + vector search merged with Reciprocal Rank Fusion

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + uvicorn |
| LLM (Q&A, generation) | Groq `llama-3.3-70b-versatile` |
| LLM (fast tasks) | Groq `llama-3.1-8b-instant` |
| LLM (image captions) | Groq `llama-3.2-11b-vision-preview` |
| Embeddings | `paraphrase-multilingual-mpnet-base-v2` (local) |
| Vector store | ChromaDB (persistent, file-based) |
| BM25 | `rank-bm25` (in-memory, cached) |
| PDF parsing | pdfplumber + PyMuPDF |
| Frontend | Next.js 14 App Router + shadcn/ui + Recharts |
| Auth | JWT (python-jose) + bcrypt |
| Infra | Docker Compose |

---

## Setup

### Prerequisites
- Docker + Docker Compose
- A [Groq API key](https://console.groq.com) (free tier)

### 1. Clone and configure

```bash
git clone https://github.com/your-username/mariastudy.git
cd mariastudy
cp .env.example .env
```

Edit `.env`:
```
GROQ_API_KEY=gsk_...
SECRET_KEY=your-random-secret-key-here
ALLOWED_ORIGINS=http://localhost:3000
```

### 2. Start

```bash
docker compose up -d --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000/docs

### 3. Create a user account

```bash
# Generate a bcrypt hash for your password
python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"

# Add to data/users.json
{
  "yourusername": {
    "password_hash": "<paste hash here>",
    "display_name": "Your Name"
  }
}
```

---

## Development

```bash
# Backend (with auto-reload)
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## Evaluation

The `eval/` directory contains a RAG benchmarking harness that measures retrieval hit rate, MRR, keyword coverage, and LLM judge scores.

```bash
# Run evaluation against a subject
python -m eval.run_eval --config eval/configs.sample.json

# Check results against quality thresholds
python -m eval.check_thresholds eval/results/<timestamp>/summary.json
```

See [eval/EVAL.md](eval/EVAL.md) for metric definitions and threshold rationale.

---

## Tests

```bash
pytest tests/ -v
```

Tests cover: auth flow, SSE upload progress, multi-topic generation, SM-2 algorithm correctness, topic detection pipeline, and quiz save/retrieve.

---

## Project Structure

```
api/            FastAPI routes + auth + schemas
src/            Core RAG engine (embedder, vectorstore, llm, rag, processor, subjects, progress)
frontend/       Next.js 14 App Router
eval/           RAG benchmarking harness
tests/          pytest test suite
data/           Runtime data (Docker volume — never committed)
```

---

## Design Decisions

All architecture decisions — why each model, why hybrid retrieval, why ChromaDB over Pinecone, why SM-2 over FSRS, why paragraph-aware chunking — are documented in [ARCHITECTURE.md](ARCHITECTURE.md).
