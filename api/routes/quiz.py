import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.schemas import (
    QuizGenerateRequest,
    QuizQuestion,
    QuizResultRequest,
    QuizSavedToggleRequest,
    QuizSavedToggleResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _normalized_topics(topic: str, topics: list[str] | None) -> list[str]:
    picked = [t.strip() for t in (topics or []) if t and t.strip() and t != "Toda a UC"]
    if picked:
        return list(dict.fromkeys(picked))
    if topic and topic.strip() and topic != "Toda a UC":
        return [topic.strip()]
    return []


@router.post("/subjects/{subject_id}/quiz/generate")
async def generate_quiz(subject_id: str, body: QuizGenerateRequest):
    """Stream quiz questions one-by-one via SSE. Each event is a JSON QuizQuestion.
    Final event: {"done": true, "total": N}
    Error event: {"error": "message"}
    """
    from src.llm import LLMConfigurationError
    from src.llm import generate_quiz as _gen
    from src.rag import get_topic_chunks
    from src.subjects import get_subject

    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")

    selected_topics = _normalized_topics(body.topic, body.topics)
    topic_label = ", ".join(selected_topics) if selected_topics else body.topic
    logger.info(
        "Generating %d quiz questions for subject=%s topic=%s difficulty=%s",
        body.n,
        subject_id,
        topic_label,
        body.difficulty,
    )

    try:
        if selected_topics:
            seen_texts = set()
            chunks = []
            for selected_topic in selected_topics:
                for chunk in get_topic_chunks(subject_id, selected_topic, top_k=10):
                    text = chunk.get("text", "")
                    if text in seen_texts:
                        continue
                    seen_texts.add(text)
                    chunks.append(chunk)
        else:
            chunks = get_topic_chunks(subject_id, body.topic, top_k=10)
    except Exception as exc:
        raise HTTPException(422, f"Erro ao pesquisar conteudo: {exc}") from exc

    if not chunks:
        raise HTTPException(422, "Sem conteudo para este topico. Certifica-te de que tens ficheiros carregados.")

    loop = asyncio.get_event_loop()

    async def event_stream():
        emitted = 0
        for _ in range(body.n):
            try:
                qs = await loop.run_in_executor(
                    None, lambda: _gen(chunks, topic_label, 1, body.difficulty)
                )
                for q in qs:
                    try:
                        validated = QuizQuestion(**q)
                        payload = {
                            "pergunta": validated.pergunta,
                            "opcoes": validated.opcoes,
                            "correta": validated.correta,
                            "explicacao": validated.explicacao,
                            "fonte": validated.fonte,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                        emitted += 1
                    except Exception:
                        pass  # skip malformed question from LLM
            except LLMConfigurationError as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                return
            except Exception:
                pass  # skip this iteration on Groq/network error

        logger.info("Quiz generation done: subject=%s topic=%s emitted=%d", subject_id, topic_label, emitted)
        yield f"data: {json.dumps({'done': True, 'total': emitted})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/subjects/{subject_id}/quiz/result", status_code=201)
def save_result(subject_id: str, body: QuizResultRequest):
    from src.progress import save_quiz_result

    save_quiz_result(subject_id, body.topic, body.score, body.total)
    return {"ok": True}


@router.get("/subjects/{subject_id}/quiz/saved", response_model=list[QuizQuestion])
def get_saved_questions(subject_id: str):
    from src.progress import get_saved_quiz_questions
    from src.subjects import get_subject

    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    return get_saved_quiz_questions(subject_id)


@router.post("/subjects/{subject_id}/quiz/saved", response_model=QuizSavedToggleResponse)
def toggle_saved_question(subject_id: str, body: QuizSavedToggleRequest):
    from src.progress import toggle_saved_quiz_question
    from src.subjects import get_subject

    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    question = body.question.model_dump() if hasattr(body.question, "model_dump") else body.question.dict()
    saved = toggle_saved_quiz_question(subject_id, question)
    return QuizSavedToggleResponse(saved=saved)
