"""ChromaDB wrapper — one persistent collection per subject."""
import streamlit as st
import chromadb
from src.config import CHROMA_DIR


@st.cache_resource(show_spinner=False)
def _get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def _col_name(subject_id: str) -> str:
    return f"subject_{subject_id}"


def get_collection(subject_id: str):
    return _get_client().get_or_create_collection(
        name=_col_name(subject_id),
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(subject_id: str, chunks: list[dict], embeddings: list):
    col = get_collection(subject_id)
    ids = [
        f"{c['metadata']['file']}_{c['metadata']['page']}_{c['metadata']['chunk_index']}"
        for c in chunks
    ]
    texts = [c["text"] for c in chunks]
    metas = [c["metadata"] for c in chunks]

    batch = 100
    for i in range(0, len(ids), batch):
        col.upsert(
            ids=ids[i:i + batch],
            embeddings=embeddings[i:i + batch],
            documents=texts[i:i + batch],
            metadatas=metas[i:i + batch],
        )


def query(
    subject_id: str,
    query_embedding: list,
    top_k: int = 6,
    file_type: str | None = None,
    max_distance: float = 0.75,
) -> list[dict]:
    """
    Retrieve top_k chunks by cosine similarity.
    - file_type: if set, restrict to chunks with that file_type metadata value.
      Use "notes" to exclude exercise files from Q&A, or "exercises" to target them.
    - max_distance: cosine distance ceiling (0–1). Chunks above this threshold are
      too dissimilar to be useful and are dropped to avoid hallucination.
    """
    col = get_collection(subject_id)
    count = col.count()
    if count == 0:
        return []

    where = {"file_type": file_type} if file_type else None

    try:
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
            where=where,
        )
    except Exception:
        # where filter may fail if collection has no file_type metadata (old data)
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
        if dist <= max_distance
    ]


def _rrf_merge(list1: list[dict], list2: list[dict], top_k: int, k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: final_score = Σ 1/(k + rank). k=60 is the standard constant."""
    rrf_scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for rank, item in enumerate(list1):
        key = item["text"][:120]
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        items[key] = item

    for rank, item in enumerate(list2):
        key = item["text"][:120]
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        if key not in items:
            items[key] = item

    sorted_keys = sorted(rrf_scores, key=rrf_scores.__getitem__, reverse=True)
    return [items[k_] for k_ in sorted_keys[:top_k]]


def hybrid_query(
    subject_id: str,
    query_text: str,
    query_embedding: list,
    top_k: int = 6,
    file_type: str | None = None,
    max_distance: float = 0.75,
) -> list[dict]:
    """
    Hybrid BM25 + vector search fused with Reciprocal Rank Fusion (RRF).
    - BM25 captures exact medical term matches (drug names, lab values, criteria).
    - Vector search captures semantic similarity via embeddings.
    - RRF merges both ranked lists into a single ordering.
    query_text  : original question/topic used for BM25 keyword matching.
    query_embedding : HyDE or topic embedding used for vector similarity.
    """
    from rank_bm25 import BM25Okapi

    col = get_collection(subject_id)
    count = col.count()
    if count == 0:
        return []

    # ── 1. Vector search ──────────────────────────────────────────────────
    vector_results = query(subject_id, query_embedding, top_k * 2, file_type, max_distance)

    # ── 2. BM25 search ────────────────────────────────────────────────────
    where = {"file_type": file_type} if file_type else None
    try:
        all_items = col.get(include=["documents", "metadatas"], where=where)
    except Exception:
        all_items = col.get(include=["documents", "metadatas"])

    docs = all_items.get("documents") or []
    metas = all_items.get("metadatas") or []

    if not docs:
        return vector_results[:top_k]

    tokenized_corpus = [d.lower().split() for d in docs]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query_text.lower().split())

    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k * 2]
    bm25_results = [
        {"text": docs[i], "metadata": metas[i], "distance": 0.0}
        for i in top_indices
        if scores[i] > 0
    ]

    # ── 3. RRF fusion ─────────────────────────────────────────────────────
    return _rrf_merge(vector_results, bm25_results, top_k)


def delete_collection(subject_id: str):
    try:
        _get_client().delete_collection(_col_name(subject_id))
    except Exception:
        pass


def collection_count(subject_id: str) -> int:
    try:
        return get_collection(subject_id).count()
    except Exception:
        return 0


def get_early_pages(subject_id: str, total_pages: int = 0, n: int = 20) -> list[dict]:
    """
    Return chunks from the first pages (table of contents / introduction).
    Range is dynamic: 3% of total pages, minimum 3, maximum 15.
    """
    col = get_collection(subject_id)
    if col.count() == 0:
        return []

    # Dynamic TOC range based on document length
    if total_pages > 0:
        max_page = max(3, min(15, round(total_pages * 0.03)))
    else:
        # Infer from collection if not provided
        try:
            all_meta = col.get(include=["metadatas"])["metadatas"]
            doc_max = max((m.get("page", 1) for m in all_meta), default=1)
            max_page = max(3, min(15, round(doc_max * 0.03)))
        except Exception:
            max_page = 10

    try:
        results = col.get(
            where={"page": {"$lte": max_page}},
            include=["documents", "metadatas"],
        )
        docs, metas = results["documents"], results["metadatas"]
        combined = sorted(zip(docs, metas), key=lambda x: (x[1].get("page", 0), x[1].get("chunk_index", 0)))
        return [{"text": d, "metadata": m} for d, m in combined[:n]]
    except Exception:
        return []


def sample_spread(subject_id: str, n: int = 30) -> list[dict]:
    """
    Return ~n chunks spread evenly across the whole collection (all pages/files).
    Used for summary generation on large documents.
    """
    col = get_collection(subject_id)
    total = col.count()
    if total == 0:
        return []

    # Fetch all ids + metadatas (no embeddings needed)
    all_items = col.get(include=["documents", "metadatas"])
    docs = all_items["documents"]
    metas = all_items["metadatas"]

    if not docs:
        return []

    # Sort by (file, page, chunk_index) for deterministic spread
    combined = sorted(zip(docs, metas), key=lambda x: (x[1].get("file", ""), x[1].get("page", 0), x[1].get("chunk_index", 0)))

    # Pick evenly spaced indices
    step = max(1, len(combined) // n)
    sampled = combined[::step][:n]

    return [{"text": d, "metadata": m} for d, m in sampled]


def update_file_type(subject_id: str, filename: str, file_type: str):
    """Update the file_type metadata on all ChromaDB chunks belonging to a file."""
    col = get_collection(subject_id)
    try:
        results = col.get(where={"file": filename}, include=["metadatas"])
        ids = results["ids"]
        if not ids:
            return
        # Build updated metadatas with new file_type
        new_metas = [{**m, "file_type": file_type} for m in results["metadatas"]]
        col.update(ids=ids, metadatas=new_metas)
    except Exception:
        pass


def delete_file_chunks(subject_id: str, filename: str):
    """Remove all chunks belonging to a specific file."""
    col = get_collection(subject_id)
    try:
        col.delete(where={"file": filename})
    except Exception:
        pass
