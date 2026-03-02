from fastapi import APIRouter, HTTPException
from api.schemas import (
    FlashcardGenerateRequest, FlashcardGenerateResponse,
    FlashcardResultRequest, FlashcardFavoriteRequest,
    FlashcardImportRequest, FlashcardImportResponse,
    FlashcardBase, FlashcardInDB,
)

router = APIRouter()


@router.post("/subjects/{subject_id}/flashcards/generate", response_model=FlashcardGenerateResponse)
def generate_flashcards(subject_id: str, body: FlashcardGenerateRequest):
    from src.subjects import get_subject
    from src.rag import get_topic_chunks
    from src.llm import generate_flashcards as _gen
    from src.progress import save_card_to_deck

    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")

    chunks = get_topic_chunks(subject_id, body.topic, top_k=8)
    if not chunks:
        raise HTTPException(422, "No content found for this topic")

    cards = _gen(chunks, body.topic, body.n)
    for card in cards:
        save_card_to_deck(subject_id, card)

    return FlashcardGenerateResponse(flashcards=[FlashcardBase(**c) for c in cards])


@router.get("/subjects/{subject_id}/flashcards", response_model=list[FlashcardInDB])
def get_deck(subject_id: str):
    from src.progress import get_deck_cards
    return get_deck_cards(subject_id)


@router.get("/subjects/{subject_id}/flashcards/due", response_model=list[FlashcardInDB])
def get_due_cards(subject_id: str):
    from src.progress import get_deck_cards
    from datetime import date
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


@router.delete("/subjects/{subject_id}/flashcards/{card_id}", status_code=204)
def delete_card(subject_id: str, card_id: str):
    from src.progress import delete_card as _delete
    # card_id is the frente text (URL-encoded by caller)
    _delete(subject_id, card_id)


@router.post("/subjects/{subject_id}/flashcards/import", response_model=FlashcardImportResponse)
def import_cards(subject_id: str, body: FlashcardImportRequest):
    from src.progress import parse_import_text, import_cards as _import
    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    cards = parse_import_text(body.text)
    count = _import(subject_id, cards)
    return FlashcardImportResponse(imported=count)


def get_subject(subject_id: str):
    from src.subjects import get_subject as _get
    return _get(subject_id)
