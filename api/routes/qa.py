from fastapi import APIRouter, HTTPException
from api.schemas import AskRequest, AskResponse, SearchRequest, SearchResult, Source

router = APIRouter()


@router.post("/subjects/{subject_id}/ask", response_model=AskResponse)
def ask(subject_id: str, body: AskRequest):
    from src.subjects import get_subject
    from src.rag import ask as _ask
    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    result = _ask(subject_id, body.question, topic_filter=body.topic_filter)
    sources = [Source(file=s["file"], page=s["page"]) for s in result.get("sources", [])]
    return AskResponse(answer=result["answer"], sources=sources)


@router.post("/subjects/{subject_id}/suggest-followups")
def suggest_followups(subject_id: str, question: str, answer: str):
    from src.llm import suggest_followups as _sf
    return {"followups": _sf(question, answer)}


@router.post("/search", response_model=list[SearchResult])
def search_all(body: SearchRequest):
    from src.subjects import list_subjects
    from src.rag import search_all_subjects
    subjects = list_subjects()
    results = search_all_subjects(body.question, subjects, top_k=body.top_k)
    return [
        SearchResult(
            subject_id=r["subject_id"],
            subject_name=r["subject_name"],
            best_distance=r.get("best_distance", 0.0),
            chunks=r.get("chunks", []),
        )
        for r in results
    ]
