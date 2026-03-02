from fastapi import APIRouter, HTTPException
from api.schemas import ProgressResponse, QuizAttempt, TopicStat, SRSStats

router = APIRouter()


@router.get("/subjects/{subject_id}/progress", response_model=ProgressResponse)
def get_progress(subject_id: str):
    from src.subjects import get_subject
    from src.progress import get_quiz_history, get_topic_stats, get_srs_stats
    from src.vectorstore import collection_count

    subj = get_subject(subject_id)
    if not subj:
        raise HTTPException(404, "Subject not found")

    history = get_quiz_history(subject_id)
    topic_stats = get_topic_stats(subject_id)
    srs = get_srs_stats(subject_id)

    total_pages = sum(f.get("pages", 0) for f in subj.get("files", []))
    total_chunks = collection_count(subject_id)

    return ProgressResponse(
        quiz_history=[QuizAttempt(**h) for h in history],
        topic_stats=[TopicStat(**t) for t in topic_stats],
        srs_stats=SRSStats(**srs),
        file_stats={
            "total_files": len(subj.get("files", [])),
            "total_pages": total_pages,
            "total_chunks": total_chunks,
        },
    )
