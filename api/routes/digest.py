"""
Daily Digest endpoint — aggregates across all subjects.
Cached in data/digest.json; refreshed once per day.
"""
import json
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter
from api.schemas import DigestResponse, DigestQuestionOfDay

router = APIRouter()

_DIGEST_CACHE = Path("data/digest.json")


def _load_cache() -> dict:
    if _DIGEST_CACHE.exists():
        try:
            return json.loads(_DIGEST_CACHE.read_text())
        except Exception:
            pass
    return {}


def _save_cache(data: dict):
    _DIGEST_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _DIGEST_CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _compute_streak() -> int:
    """Count consecutive study days ending today."""
    from src.subjects import list_subjects
    from src.progress import get_quiz_history
    import json as _json
    from src.config import SRS_FILE

    study_days: set[str] = set()

    # Dates from quiz history
    for subj in list_subjects():
        for entry in get_quiz_history(subj["id"]):
            d = entry.get("date", "")
            if d:
                study_days.add(d)

    # Dates from SRS last_reviewed
    if Path(SRS_FILE).exists():
        try:
            srs_data = _json.loads(Path(SRS_FILE).read_text())
            for subj_cards in srs_data.values():
                for card in subj_cards.values():
                    lr = card.get("last_reviewed", "")
                    if lr:
                        study_days.add(lr)
        except Exception:
            pass

    streak = 0
    today = date.today()
    for i in range(365):
        day = (today - timedelta(days=i)).isoformat()
        if day in study_days:
            streak += 1
        else:
            break
    return streak


def _compute_due_total() -> int:
    from src.subjects import list_subjects
    from src.progress import get_srs_stats
    total = 0
    for subj in list_subjects():
        stats = get_srs_stats(subj["id"])
        total += stats.get("due", 0)
    return total


def _find_weak_topic() -> tuple[str | None, str | None]:
    """Return (topic_name, subject_name) with lowest avg_pct, min 2 attempts."""
    from src.subjects import list_subjects
    from src.progress import get_topic_stats

    best_topic = None
    best_subject = None
    best_pct = 101.0

    for subj in list_subjects():
        for stat in get_topic_stats(subj["id"]):
            if stat.get("attempts", 0) >= 2:
                pct = stat.get("avg_pct", 100.0)
                if pct < best_pct:
                    best_pct = pct
                    best_topic = stat["topic"]
                    best_subject = subj["name"]

    return best_topic, best_subject


def _get_question_of_day(weak_topic: str | None, weak_subject_name: str | None) -> dict | None:
    """Generate or return cached daily question."""
    today = date.today().isoformat()
    cache = _load_cache()

    if cache.get("qod_date") == today and cache.get("question_of_day"):
        q = cache["question_of_day"]
        q["subject_name"] = cache.get("qod_subject", "")
        return q

    if not weak_topic:
        return None

    # Find subject_id from name
    from src.subjects import list_subjects
    from src.rag import get_topic_chunks
    from src.llm import generate_flashcards

    subject_id = None
    for subj in list_subjects():
        if subj["name"] == weak_subject_name:
            subject_id = subj["id"]
            break

    if not subject_id:
        return None

    try:
        chunks = get_topic_chunks(subject_id, weak_topic, top_k=5)
        if not chunks:
            return None
        cards = generate_flashcards(chunks, weak_topic, n=1)
        if not cards:
            return None
        q = cards[0]
        q["subject_name"] = weak_subject_name or ""

        # Cache it
        cache["qod_date"] = today
        cache["question_of_day"] = {k: v for k, v in q.items() if k != "subject_name"}
        cache["qod_subject"] = weak_subject_name or ""
        _save_cache(cache)

        return q
    except Exception:
        return None


@router.get("/digest", response_model=DigestResponse)
def get_digest():
    streak = _compute_streak()
    due_total = _compute_due_total()
    weak_topic, weak_subject = _find_weak_topic()
    qod_raw = _get_question_of_day(weak_topic, weak_subject)

    qod = None
    if qod_raw:
        qod = DigestQuestionOfDay(
            frente=qod_raw.get("frente", ""),
            verso=qod_raw.get("verso", ""),
            fonte=qod_raw.get("fonte", ""),
            card_type=qod_raw.get("card_type", "basic"),
            subject_name=qod_raw.get("subject_name", ""),
        )

    return DigestResponse(
        streak=streak,
        due_total=due_total,
        weak_topic=weak_topic,
        weak_topic_subject=weak_subject,
        question_of_day=qod,
    )
