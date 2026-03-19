"""RAG pipeline: ingest files and answer questions with citations."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from src.config import UPLOADS_DIR, TOP_K, GROQ_RATE_LIMIT_DELAY

logger = logging.getLogger(__name__)
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

    total_chunks = len(chunks)
    texts = [c["text"] for c in chunks]

    # Embed in batches so progress is tied to real work
    embeddings: list[list[float]] = []
    embed_batch = 32
    if progress_cb:
        progress_cb(f"A calcular embeddings… 0/{total_chunks} chunks", 46)
    for i in range(0, total_chunks, embed_batch):
        end = min(i + embed_batch, total_chunks)
        embeddings.extend(embedder.embed(texts[i:end]))
        if progress_cb:
            pct = round(46 + (end / max(total_chunks, 1)) * 32, 1)  # 46 -> 78
            progress_cb(f"A calcular embeddings… {end}/{total_chunks} chunks", pct)

    # Store in ChromaDB with real batch progress
    if progress_cb:
        progress_cb(f"A indexar vetores… 0/{total_chunks} chunks", 79)
    vectorstore.add_chunks(
        subject_id,
        chunks,
        embeddings,
        progress_cb=(
            (lambda done, total: progress_cb(
                f"A indexar vetores… {done}/{total} chunks",
                round(79 + (done / max(total, 1)) * 19, 1),  # 79 -> 98
            ))
            if progress_cb
            else None
        ),
    )

    n_pages = max((c["metadata"]["page"] for c in chunks), default=1)
    subject_store.add_file_to_subject(subject_id, filename, n_pages, file_type)

    if progress_cb:
        progress_cb("A extrair tópicos…", 99)

    _refresh_topics_and_summary(subject_id)

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

    Strategy:
    1. Hybrid search (BM25 + vector) to find seed chunks — these identify the most
       relevant pages, not necessarily the best context by themselves.
    2. Page-anchored expansion: find the top N pages from those seeds, then fetch ALL
       chunks from those pages in reading order. This gives the LLM coherent, consecutive
       passages rather than scattered fragments, and ensures page citations are accurate.
    3. Falls back to seeds if expansion returns nothing.
    """
    from collections import Counter

    emb = embedder.embed([topic])[0]

    # ── Step 1: Seed retrieval ──────────────────────────────────────────────
    notes_filtered = vectorstore.hybrid_query(
        subject_id, topic, emb, top_k, file_type="notes", topic_filter=topic
    )
    exercises_filtered = vectorstore.hybrid_query(
        subject_id, topic, emb, min(4, top_k // 2), file_type="exercises", topic_filter=topic
    )
    if len(notes_filtered) >= top_k // 2:
        notes, exercises = notes_filtered, exercises_filtered
    else:
        notes = vectorstore.hybrid_query(subject_id, topic, emb, top_k, file_type="notes")
        exercises = vectorstore.hybrid_query(
            subject_id, topic, emb, min(4, top_k // 2), file_type="exercises"
        )

    seen: set[str] = set()
    seeds: list[dict] = []
    for c in notes + exercises:
        if c["text"] not in seen:
            seen.add(c["text"])
            seeds.append(c)

    if not seeds:
        seeds = vectorstore.hybrid_query(subject_id, topic, emb, top_k)

    # Strip very short chunks — titles, headers, cover pages (real chunks are ~400 words)
    seeds = [c for c in seeds if len(c["text"].split()) >= 30]

    # ── Step 2: Page-anchored expansion ────────────────────────────────────
    # Count how many seeds fall on each (file, page) pair.  The most-cited pages
    # are the most topically relevant; fetch ALL their chunks in reading order.
    page_counts: Counter = Counter(
        (c["metadata"]["file"], c["metadata"]["page"]) for c in seeds
    )
    n_pages = min(3, len(page_counts))
    top_pages = [p for p, _ in page_counts.most_common(n_pages)]

    expanded: list[dict] = []
    seen_texts: set[str] = set()
    for (filename, page) in top_pages:
        for c in vectorstore.get_page_chunks_full(subject_id, filename, page):
            if c["text"] not in seen_texts and len(c["text"].split()) >= 30:
                seen_texts.add(c["text"])
                expanded.append(c)

    return expanded if expanded else seeds


def _refresh_topics_and_summary(subject_id: str):
    """
    Extract topics (TOC-first, LLM fallback), assign topics to chunks, generate summary.

    Topic extraction strategy:
    1. Read the PDF bookmark outline (fitz.get_toc) from every uploaded PDF.
       This is instant, free, and gives exact chapter/section titles.
    2. Only if no file yields a usable outline (< 5 topics across all files),
       fall back to LLM extraction from early-page text.
    3. After topics are finalised, pre-compute primary_topic for every chunk
       using cosine similarity (stored embeddings — no re-embedding needed).
    """
    spread_chunks = vectorstore.sample_spread(subject_id, n=40)
    if not spread_chunks:
        return

    subject = subject_store.get_subject(subject_id)
    if not subject:
        return

    # ── Step 1: TOC extraction from PDF bookmarks ──────────────────────────
    toc_topics: list[str] = []
    per_file_topics: dict[str, list[str]] = {}  # filename → file-level topics from its TOC
    for file_info in subject.get("files", []):
        file_path = str(UPLOADS_DIR / subject_id / file_info["name"])
        if file_info["name"].lower().endswith(".pdf"):
            topics_from_file = processor.extract_toc(file_path)
            if topics_from_file:
                per_file_topics[file_info["name"]] = topics_from_file
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
        except Exception as e:
            logger.warning("LLM topic extraction failed, falling back to TOC: %s", e)
            extracted_topics = toc_topics  # use what we have even if sparse

    if extracted_topics:
        subject_store.update_topics(subject_id, extracted_topics)

    # Store per-file topics (from TOC) so the UI can show two-tier topic navigation
    for fname, ftopics in per_file_topics.items():
        subject_store.set_file_topics(subject_id, fname, ftopics)

    # ── Step 3: Pre-compute primary_topic per chunk ────────────────────────
    # Uses stored embeddings (no re-embedding cost). Enables fast metadata-filtered retrieval.
    if extracted_topics:
        try:
            vectorstore.assign_topics_to_chunks(subject_id, extracted_topics)
        except Exception as e:
            logger.warning("Topic assignment failed (non-fatal, retrieval falls back to hybrid): %s", e)

    # Pause to avoid back-to-back Groq rate limit on the same model
    time.sleep(GROQ_RATE_LIMIT_DELAY)

    # ── Subject-level summary ──────────────────────────────────────────────
    summary_sample = " ".join(c["text"] for c in spread_chunks)
    all_topics = extracted_topics or subject_store.get_subject(subject_id).get("topics", [])
    try:
        summary = llm.generate_summary(summary_sample, topics=all_topics or None)
        if summary:
            subject_store.update_summary(subject_id, summary)
    except Exception as e:
        logger.warning("Summary generation failed for subject %s: %s", subject_id, e)

    # ── Per-topic summaries ────────────────────────────────────────────────
    for topic in extracted_topics:
        try:
            topic_chunks = get_topic_chunks(subject_id, topic, top_k=8)
            if topic_chunks:
                topic_text = " ".join(c["text"] for c in topic_chunks)
                topic_summary = llm.generate_topic_summary(topic, topic_text)
                if topic_summary:
                    subject_store.update_topic_summary(subject_id, topic, topic_summary)
            time.sleep(GROQ_RATE_LIMIT_DELAY // 2)  # avoid consecutive Groq rate-limit hits
        except Exception as e:
            logger.warning("Per-topic summary failed for '%s': %s", topic, e)


def search_all_subjects(question: str, subjects: list[dict], top_k: int = 3) -> list[dict]:
    """
    Search across all subject collections in parallel.
    Returns subjects sorted by relevance, each with their best matching chunks.
    """
    if not subjects:
        return []

    q_emb = embedder.embed([question])[0]

    def _search_one(s: dict):
        chunks = vectorstore.query(s["id"], q_emb, top_k=top_k)
        if not chunks:
            return None
        return {
            "subject_id": s["id"],
            "subject_name": s["name"],
            "chunks": chunks,
            "best_distance": min(c["distance"] for c in chunks),
        }

    results = []
    max_workers = min(4, len(subjects))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_search_one, s) for s in subjects]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

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
