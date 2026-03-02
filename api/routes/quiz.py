from fastapi import APIRouter, HTTPException
from api.schemas import (
    QuizGenerateRequest, QuizGenerateResponse,
    QuizResultRequest, QuizQuestion,
)

router = APIRouter()


@router.post("/subjects/{subject_id}/quiz/generate", response_model=QuizGenerateResponse)
def generate_quiz(subject_id: str, body: QuizGenerateRequest):
    from src.subjects import get_subject
    from src.rag import get_topic_chunks
    from src.llm import generate_quiz as _gen

    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")

    chunks = get_topic_chunks(subject_id, body.topic, top_k=10)
    if not chunks:
        raise HTTPException(422, "No content found for this topic")

    questions = _gen(chunks, body.topic, body.n, body.difficulty)
    return QuizGenerateResponse(
        questoes=[QuizQuestion(**q) for q in questions]
    )


@router.post("/subjects/{subject_id}/quiz/result", status_code=201)
def save_result(subject_id: str, body: QuizResultRequest):
    from src.progress import save_quiz_result
    save_quiz_result(subject_id, body.topic, body.score, body.total)
    return {"ok": True}
