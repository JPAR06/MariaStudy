import logging
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from api.schemas import SubjectCreate, SubjectResponse, SubjectStatusUpdate

_executor = ThreadPoolExecutor(max_workers=1)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/subjects", response_model=list[SubjectResponse])
def list_subjects():
    from src.subjects import list_subjects as _list
    return _list()


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
def get_subject(subject_id: str):
    from src.subjects import get_subject as _get
    subj = _get(subject_id)
    if not subj:
        raise HTTPException(404, "Subject not found")
    return subj


@router.post("/subjects", response_model=SubjectResponse, status_code=201)
def create_subject(body: SubjectCreate):
    from src.subjects import create_subject as _create
    subject = _create(body.name)
    logger.info("Created subject %s (%s)", subject["id"], body.name)
    return subject


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(subject_id: str):
    from src.subjects import get_subject, delete_subject as _delete
    from src.vectorstore import delete_collection
    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    delete_collection(subject_id)
    _delete(subject_id)
    logger.info("Deleted subject %s", subject_id)


@router.put("/subjects/{subject_id}/topics")
def update_topics(subject_id: str, topics: list[str]):
    from src.subjects import update_topics
    update_topics(subject_id, topics)
    return {"ok": True}


@router.delete("/subjects/{subject_id}/topics/{topic}")
def delete_topic(subject_id: str, topic: str):
    from src.subjects import get_subject, update_topics
    subj = get_subject(subject_id)
    if not subj:
        raise HTTPException(404, "Subject not found")
    topics = [t for t in subj.get("topics", []) if t != topic]
    update_topics(subject_id, topics)
    return {"ok": True}


@router.get("/subjects/{subject_id}/source-text")
def get_source_text(subject_id: str, file: str, page: int):
    """Return chunk texts for a specific file+page (used for reference text panel)."""
    from src.vectorstore import get_page_chunks
    texts = get_page_chunks(subject_id, file, page)
    return {"texts": texts}


@router.post("/subjects/{subject_id}/refresh-summaries", status_code=202)
def refresh_summaries(subject_id: str):
    """Generates missing per-topic summaries in the background."""
    from src.subjects import get_subject
    subj = get_subject(subject_id)
    if not subj:
        raise HTTPException(404, "Subject not found")

    def _run():
        from src.rag import get_topic_chunks
        from src.llm import generate_topic_summary
        from src.subjects import update_topic_summary, get_subject as _get
        s = _get(subject_id)
        if not s:
            return
        existing = s.get("topic_summaries", {})
        missing = [t for t in s.get("topics", []) if not existing.get(t)]
        logger.info("refresh-summaries: %d missing for %s", len(missing), subject_id)
        for topic in missing:
            try:
                chunks = get_topic_chunks(subject_id, topic, top_k=8)
                if chunks:
                    text = " ".join(c["text"] for c in chunks)
                    summary = generate_topic_summary(topic, text)
                    if summary:
                        update_topic_summary(subject_id, topic, summary)
                time.sleep(1)
            except Exception as e:
                logger.warning("Topic summary generation failed for '%s': %s", topic, e)

    _executor.submit(_run)
    return {"ok": True}


@router.put("/subjects/{subject_id}/status", response_model=SubjectResponse)
def update_subject_status(subject_id: str, body: SubjectStatusUpdate):
    from src.subjects import get_subject, set_subject_status
    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    updated = set_subject_status(subject_id, body.status)
    if not updated:
        raise HTTPException(404, "Subject not found")
    return updated
