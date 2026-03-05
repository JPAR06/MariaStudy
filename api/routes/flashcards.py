import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from api.schemas import (
    FlashcardBase,
    FlashcardFavoriteRequest,
    FlashcardGenerateRequest,
    FlashcardImportRequest,
    FlashcardImportResponse,
    FlashcardInDB,
    FlashcardResultRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_BATCH = 3  # cards per LLM call for streaming generation


def _normalized_topics(topic: str, topics: list[str] | None) -> list[str]:
    picked = [t.strip() for t in (topics or []) if t and t.strip() and t != "Toda a UC"]
    if picked:
        return list(dict.fromkeys(picked))
    if topic and topic.strip() and topic != "Toda a UC":
        return [topic.strip()]
    return []


@router.post("/subjects/{subject_id}/flashcards/generate")
async def generate_flashcards(subject_id: str, body: FlashcardGenerateRequest):
    """Stream flashcards in batches of 3 via SSE. Each event is a JSON FlashcardBase.
    Final event: {"done": true, "total": N}
    Error event: {"error": "message"}
    """
    from src.llm import LLMConfigurationError
    from src.llm import generate_flashcards as _gen
    from src.progress import save_card_to_deck
    from src.rag import get_topic_chunks
    from src.subjects import get_subject

    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")

    selected_topics = _normalized_topics(body.topic, body.topics)
    topic_label = ", ".join(selected_topics) if selected_topics else body.topic
    logger.info("Generating %d flashcards for subject=%s topic=%s", body.n, subject_id, topic_label)

    try:
        if selected_topics:
            seen_texts = set()
            chunks = []
            for selected_topic in selected_topics:
                for chunk in get_topic_chunks(subject_id, selected_topic, top_k=8):
                    text = chunk.get("text", "")
                    if text in seen_texts:
                        continue
                    seen_texts.add(text)
                    chunks.append(chunk)
        else:
            query = body.topic if body.topic and body.topic != "Toda a UC" else "medicina clínica"
            chunks = get_topic_chunks(subject_id, query, top_k=8)
    except Exception as exc:
        raise HTTPException(422, f"Erro ao pesquisar conteudo: {exc}") from exc

    if not chunks:
        raise HTTPException(422, "Sem conteudo para este topico. Certifica-te de que tens ficheiros carregados.")

    loop = asyncio.get_event_loop()

    async def event_stream():
        emitted = 0
        remaining = body.n
        while remaining > 0:
            batch_n = min(_BATCH, remaining)
            remaining -= batch_n
            try:
                cards = await loop.run_in_executor(
                    None, lambda bn=batch_n: _gen(chunks, topic_label, bn)
                )
                for card in cards:
                    try:
                        validated = FlashcardBase(**card)
                        save_card_to_deck(subject_id, card)
                        payload = {
                            "frente": validated.frente,
                            "verso": validated.verso,
                            "fonte": validated.fonte,
                            "card_type": validated.card_type,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                        emitted += 1
                    except Exception:
                        pass
            except LLMConfigurationError as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                return
            except Exception:
                pass  # skip failed batch

        logger.info("Flashcard generation done: subject=%s topic=%s emitted=%d", subject_id, topic_label, emitted)
        yield f"data: {json.dumps({'done': True, 'total': emitted})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/subjects/{subject_id}/flashcards", response_model=list[FlashcardInDB])
def get_deck(subject_id: str):
    from src.progress import get_deck_cards

    return get_deck_cards(subject_id)


@router.get("/subjects/{subject_id}/flashcards/due", response_model=list[FlashcardInDB])
def get_due_cards(subject_id: str):
    from datetime import date

    from src.progress import get_deck_cards

    today = date.today().isoformat()
    all_cards = get_deck_cards(subject_id)
    return [c for c in all_cards if c.get("next_review", "9999") <= today or c.get("reps", 0) == 0]


@router.get("/subjects/{subject_id}/flashcards/favorites", response_model=list[FlashcardInDB])
def get_favorites(subject_id: str):
    from src.progress import get_favorite_cards

    return get_favorite_cards(subject_id)


@router.post("/subjects/{subject_id}/flashcards/result")
def save_result(subject_id: str, body: FlashcardResultRequest):
    from src.progress import save_flashcard_result

    save_flashcard_result(subject_id, body.card, body.result)
    return {"ok": True}


@router.post("/subjects/{subject_id}/flashcards/favorite")
def toggle_favorite(subject_id: str, body: FlashcardFavoriteRequest):
    from src.progress import toggle_favorite as _toggle

    new_state = _toggle(subject_id, body.card)
    return {"favorite": new_state}


@router.delete("/subjects/{subject_id}/flashcards/all", status_code=204)
def clear_deck(subject_id: str):
    from src.progress import clear_deck as _clear
    _clear(subject_id)
    logger.info("Cleared all flashcards for subject=%s", subject_id)


@router.delete("/subjects/{subject_id}/flashcards/{card_id}", status_code=204)
def delete_card(subject_id: str, card_id: str):
    from src.progress import delete_card as _delete

    # card_id is the frente text (URL-encoded by caller)
    _delete(subject_id, card_id)


@router.post("/subjects/{subject_id}/flashcards/import", response_model=FlashcardImportResponse)
def import_cards(subject_id: str, body: FlashcardImportRequest):
    from src.progress import import_cards as _import
    from src.progress import parse_import_text

    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    cards = parse_import_text(body.text)
    count = _import(subject_id, cards)
    return FlashcardImportResponse(imported=count)


@router.get("/subjects/{subject_id}/flashcards/export/anki")
def export_anki(subject_id: str):
    """Export the full deck as an Anki .apkg file (download)."""
    from src.progress import build_anki_package
    from src.subjects import get_subject as _get

    subject = _get(subject_id)
    if not subject:
        raise HTTPException(404, "Subject not found")
    try:
        data = build_anki_package(subject_id, subject["name"])
    except Exception as exc:
        raise HTTPException(500, f"Erro ao gerar ficheiro Anki: {exc}") from exc
    if not data:
        raise HTTPException(422, "Sem cartoes para exportar.")
    safe = subject["name"].replace(" ", "_").replace("/", "_")[:40]
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe}.apkg"'},
    )


def get_subject(subject_id: str):
    from src.subjects import get_subject as _get

    return _get(subject_id)
