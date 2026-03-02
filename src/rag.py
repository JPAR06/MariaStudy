"""RAG pipeline: ingest files and answer questions with citations."""
from pathlib import Path
from typing import Callable

from src.config import UPLOADS_DIR, TOP_K
from src import embedder, vectorstore
from src import llm
from src import subjects as subject_store
from src import processor


def ingest_file(
    subject_id: str,
    file_bytes: bytes,
    filename: str,
    enable_images: bool = True,
    progress_cb: Callable | None = None,
    file_type: str = "notes",
) -> int:
    """
    Save, process, embed and store a file.
    file_type: 'notes' (default) | 'exercises'
    Returns number of chunks created (0 on failure).
    """
    # Save raw file
    dest_dir = UPLOADS_DIR / subject_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / filename
    file_path.write_bytes(file_bytes)

    caption_fn = llm.caption_image if enable_images else None

    # Extract chunks (file_type is embedded in each chunk's metadata)
    chunks = processor.extract_file(
        str(file_path), subject_id, filename, caption_fn, progress_cb, file_type
    )
    if not chunks:
        return 0

    # Embed
    texts = [c["text"] for c in chunks]
    embeddings = embedder.embed(texts)

    # Store in ChromaDB
    vectorstore.add_chunks(subject_id, chunks, embeddings)

    # Page count
    n_pages = max((c["metadata"]["page"] for c in chunks), default=1)
    subject_store.add_file_to_subject(subject_id, filename, n_pages, file_type)

    return len(chunks)


def ask(subject_id: str, question: str, topic_filter: str | None = None) -> dict:
    """
    RAG Q&A with citations.
    Uses HyDE: embeds a hypothetical textbook answer instead of the raw question,
    so the query vector lands in 'answer space' (much closer to stored chunks).
    Exercise files are excluded — they contain questions, not explanations.
    Returns {"answer": str, "sources": [{"file": str, "page": int}]}
    """
    # HyDE: generate a hypothetical textbook passage, fall back to raw question
    hyde_text = llm.hypothetical_answer(question, topic=topic_filter)
    retrieval_text = hyde_text if hyde_text else (
        f"{topic_filter}: {question}" if topic_filter else question
    )
    q_emb = embedder.embed([retrieval_text])[0]
    # Hybrid: BM25 uses original question for exact keyword matching (drug names, criteria);
    # vector search uses HyDE embedding for semantic matching.
    bm25_text = f"{topic_filter}: {question}" if topic_filter else question
    chunks = vectorstore.hybrid_query(subject_id, bm25_text, q_emb, TOP_K, file_type="notes")
    if not chunks:
        chunks = vectorstore.hybrid_query(subject_id, bm25_text, q_emb, TOP_K)

    if not chunks:
        return {
            "answer": (
                "Não encontrei informação suficiente neste assunto para responder. "
                "Certifica-te de que fizeste upload de ficheiros relevantes."
            ),
            "sources": [],
        }

    answer = llm.answer_question(chunks, question)

    # Unique sources in retrieval order
    seen, sources = set(), []
    for c in chunks:
        key = (c["metadata"]["file"], c["metadata"]["page"])
        if key not in seen:
            seen.add(key)
            sources.append({"file": c["metadata"]["file"], "page": c["metadata"]["page"]})

    return {"answer": answer, "sources": sources}


def get_topic_chunks(subject_id: str, topic: str, top_k: int = 8) -> list[dict]:
    """
    Retrieve chunks relevant to a topic for flashcards/quiz.
    Blends notes (explanations) + exercises (real exam questions) for richer quiz generation.
    """
    emb = embedder.embed([topic])[0]
    # Get notes chunks (primary source of content)
    notes = vectorstore.hybrid_query(subject_id, topic, emb, top_k, file_type="notes")
    # Get exercise chunks (real questions to inspire quiz style), fewer needed
    exercises = vectorstore.hybrid_query(subject_id, topic, emb, min(4, top_k // 2), file_type="exercises")
    # Merge: notes first, then exercises (deduplicated by text)
    seen = set()
    result = []
    for c in notes + exercises:
        if c["text"] not in seen:
            seen.add(c["text"])
            result.append(c)
    # Fall back to unfiltered if we got nothing (old data without file_type metadata)
    if not result:
        result = vectorstore.hybrid_query(subject_id, topic, emb, top_k)
    return result


def _refresh_topics_and_summary(subject_id: str):
    """
    Extract topics (TOC-first, LLM fallback) and generate a summary.

    Topic extraction strategy:
    1. Read the PDF bookmark outline (fitz.get_toc) from every uploaded PDF.
       This is instant, free, and gives exact chapter/section titles.
    2. Only if no file yields a usable outline (< 5 topics across all files),
       fall back to LLM extraction from early-page text.
    """
    import time

    spread_chunks = vectorstore.sample_spread(subject_id, n=40)
    if not spread_chunks:
        return

    subject = subject_store.get_subject(subject_id)
    if not subject:
        return

    # ── Step 1: TOC extraction from PDF bookmarks ──────────────────────────
    toc_topics: list[str] = []
    for file_info in subject.get("files", []):
        file_path = str(UPLOADS_DIR / subject_id / file_info["name"])
        if file_info["name"].lower().endswith(".pdf"):
            topics_from_file = processor.extract_toc(file_path)
            for t in topics_from_file:
                if t not in toc_topics:
                    toc_topics.append(t)

    # ── Step 2: LLM fallback if outline was sparse ─────────────────────────
    extracted_topics: list[str] = []
    if len(toc_topics) >= 5:
        extracted_topics = toc_topics
    else:
        # Supplement with LLM extraction from early pages
        total_pages = sum(f.get("pages", 0) for f in subject.get("files", []))
        early_chunks = vectorstore.get_early_pages(subject_id, total_pages=total_pages, n=20)
        topic_chunks = early_chunks if early_chunks else spread_chunks[:20]
        topic_sample = " ".join(c["text"] for c in topic_chunks)
        try:
            llm_topics = llm.extract_topics(topic_sample)
            # Merge: TOC titles first (more authoritative), then LLM additions
            merged = list(toc_topics)
            for t in llm_topics:
                if t not in merged:
                    merged.append(t)
            extracted_topics = merged
        except Exception:
            extracted_topics = toc_topics  # use what we have even if sparse

    if extracted_topics:
        subject_store.update_topics(subject_id, extracted_topics)

    # Pause to avoid back-to-back Groq rate limit on the same model
    time.sleep(2)

    # ── Summary ────────────────────────────────────────────────────────────
    summary_sample = " ".join(c["text"] for c in spread_chunks)
    all_topics = extracted_topics or subject_store.get_subject(subject_id).get("topics", [])
    try:
        summary = llm.generate_summary(summary_sample, topics=all_topics or None)
        if summary:
            subject_store.update_summary(subject_id, summary)
    except Exception:
        pass


def search_all_subjects(question: str, subjects: list[dict], top_k: int = 3) -> list[dict]:
    """
    Search across all subject collections.
    Returns subjects sorted by relevance, each with their best matching chunks.
    """
    q_emb = embedder.embed([question])[0]
    results = []
    for s in subjects:
        chunks = vectorstore.query(s["id"], q_emb, top_k=top_k)
        if chunks:
            results.append({
                "subject_id": s["id"],
                "subject_name": s["name"],
                "chunks": chunks,
                "best_distance": min(c["distance"] for c in chunks),
            })
    results.sort(key=lambda x: x["best_distance"])  # lower cosine distance = more relevant
    return results


def delete_file(subject_id: str, filename: str):
    """Remove a file's chunks from ChromaDB and its record from subject metadata."""
    vectorstore.delete_file_chunks(subject_id, filename)
    subject_store.remove_file_from_subject(subject_id, filename)
    # Also delete the raw file
    raw = UPLOADS_DIR / subject_id / filename
    if raw.exists():
        raw.unlink()
