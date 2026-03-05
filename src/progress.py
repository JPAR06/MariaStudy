import json
import hashlib
import logging
import os
import re
import tempfile
import threading
from datetime import date, timedelta
from src.config import PROGRESS_FILE, SRS_FILE

logger = logging.getLogger(__name__)

# Separate locks for each JSON file — no cross-file contention
_progress_lock = threading.Lock()
_srs_lock = threading.Lock()


def _load(path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Falha ao carregar %s: %s", path.name, e)
        return {}


def _atomic_save(path, data: dict):
    """Write to a temp file then atomically rename — crash-safe."""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.stem}_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ── Quiz History ──────────────────────────────────────────────────────────────

def _subject_progress_entry(data: dict, subject_id: str) -> dict:
    raw = data.get(subject_id)
    if isinstance(raw, list):
        return {"history": raw, "saved_quiz": []}
    if isinstance(raw, dict):
        return {
            "history": raw.get("history", []),
            "saved_quiz": raw.get("saved_quiz", []),
        }
    return {"history": [], "saved_quiz": []}


def _quiz_item_id(question: dict) -> str:
    seed = "|".join([
        str(question.get("pergunta", "")).strip(),
        str(question.get("fonte", "")).strip(),
        "||".join(question.get("opcoes", []) or []),
    ])
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def save_quiz_result(subject_id: str, topic: str, score: int, total: int):
    with _progress_lock:
        data = _load(PROGRESS_FILE)
        entry = _subject_progress_entry(data, subject_id)
        entry["history"].append({
            "date": date.today().isoformat(),
            "topic": topic,
            "score": score,
            "total": total,
            "pct": round(score / total * 100, 1) if total > 0 else 0,
        })
        data[subject_id] = entry
        _atomic_save(PROGRESS_FILE, data)
    logger.info("Quiz result saved: subject=%s topic=%s score=%d/%d", subject_id, topic, score, total)


def get_quiz_history(subject_id: str) -> list:
    with _progress_lock:
        data = _load(PROGRESS_FILE)
        return _subject_progress_entry(data, subject_id)["history"]


def toggle_saved_quiz_question(subject_id: str, question: dict) -> bool:
    with _progress_lock:
        data = _load(PROGRESS_FILE)
        entry = _subject_progress_entry(data, subject_id)
        saved = entry["saved_quiz"]
        qid = _quiz_item_id(question)
        idx = next((i for i, q in enumerate(saved) if _quiz_item_id(q) == qid), -1)
        if idx >= 0:
            saved.pop(idx)
            new_state = False
        else:
            saved.append({
                "pergunta": question.get("pergunta", ""),
                "opcoes": question.get("opcoes", []),
                "correta": int(question.get("correta", 0)),
                "explicacao": question.get("explicacao", ""),
                "fonte": question.get("fonte", ""),
            })
            new_state = True
        entry["saved_quiz"] = saved
        data[subject_id] = entry
        _atomic_save(PROGRESS_FILE, data)
    return new_state


def get_saved_quiz_questions(subject_id: str) -> list[dict]:
    with _progress_lock:
        data = _load(PROGRESS_FILE)
        return _subject_progress_entry(data, subject_id)["saved_quiz"]


def get_topic_stats(subject_id: str) -> list[dict]:
    history = get_quiz_history(subject_id)
    topics: dict[str, dict] = {}
    for h in history:
        t = h["topic"]
        if t not in topics:
            topics[t] = {"topic": t, "attempts": 0, "total_pct": 0.0, "last_date": ""}
        topics[t]["attempts"] += 1
        topics[t]["total_pct"] += h["pct"]
        if h["date"] > topics[t]["last_date"]:
            topics[t]["last_date"] = h["date"]

    result = []
    for t, d in topics.items():
        result.append({
            "topic": t,
            "attempts": d["attempts"],
            "avg_pct": round(d["total_pct"] / d["attempts"], 1),
            "last_date": d["last_date"],
        })
    return sorted(result, key=lambda x: x["last_date"], reverse=True)


# ── SRS Flashcards (SM-2 with 4 ratings) ─────────────────────────────────────

def _card_id(frente: str) -> str:
    # SHA-256 prefix — low collision probability vs truncated MD5
    return hashlib.sha256(frente.encode()).hexdigest()[:16]


def _default_card() -> dict:
    return {
        "interval": 1,
        "ease": 2.5,
        "reps": 0,
        "favorite": False,
        "next_review": date.today().isoformat(),
    }


def save_card_to_deck(subject_id: str, card: dict):
    """Save a card to the deck immediately on generation (no rating yet)."""
    with _srs_lock:
        data = _load(SRS_FILE)
        sid = data.get(subject_id, {})
        cid = _card_id(card["frente"])
        if cid not in sid:
            entry = _default_card()
            entry["frente"] = card["frente"]
            entry["verso"] = card["verso"]
            entry["fonte"] = card.get("fonte", "")
            entry["card_type"] = card.get("card_type", "basic")
            sid[cid] = entry
            data[subject_id] = sid
            _atomic_save(SRS_FILE, data)


def save_flashcard_result(subject_id: str, card: dict, result: str):
    """
    result: 'again' | 'hard' | 'good' | 'easy'
    SM-2 intervals:
      again → reset to 1 day, ease -0.20
      hard  → interval × 1.2, ease -0.15
      good  → interval × ease (normal advance)
      easy  → interval × ease × 1.3, ease +0.15
    """
    with _srs_lock:
        data = _load(SRS_FILE)
        sid = data.get(subject_id, {})
        cid = _card_id(card["frente"])
        existing = sid.get(cid, _default_card())

        if result == "again":
            existing["interval"] = 1
            existing["ease"] = max(1.3, existing["ease"] - 0.20)
            existing["reps"] = 0
        elif result == "hard":
            existing["interval"] = max(1, round(existing["interval"] * 1.2))
            existing["ease"] = max(1.3, existing["ease"] - 0.15)
            existing["reps"] = existing.get("reps", 0) + 1
        elif result == "good":
            existing["interval"] = max(1, round(existing["interval"] * existing["ease"]))
            existing["reps"] = existing.get("reps", 0) + 1
        else:  # easy
            existing["interval"] = max(1, round(existing["interval"] * existing["ease"] * 1.3))
            existing["ease"] = min(3.0, existing["ease"] + 0.15)
            existing["reps"] = existing.get("reps", 0) + 1

        existing["last_reviewed"] = date.today().isoformat()
        existing["next_review"] = (date.today() + timedelta(days=existing["interval"])).isoformat()
        existing["frente"] = card["frente"]
        existing["verso"] = card["verso"]
        existing["fonte"] = card.get("fonte", "")
        existing["card_type"] = card.get("card_type", "basic")

        sid[cid] = existing
        data[subject_id] = sid
        _atomic_save(SRS_FILE, data)

    _increment_daily_activity(subject_id)


def _increment_daily_activity(subject_id: str):
    today = date.today().isoformat()
    with _progress_lock:
        data = _load(PROGRESS_FILE)
        entry = _subject_progress_entry(data, subject_id)
        activity = entry.setdefault("activity", {})
        activity[today] = activity.get(today, 0) + 1
        data[subject_id] = entry
        _atomic_save(PROGRESS_FILE, data)


def get_daily_activity(subject_id: str) -> dict:
    with _progress_lock:
        data = _load(PROGRESS_FILE)
        return _subject_progress_entry(data, subject_id).get("activity", {})


def toggle_favorite(subject_id: str, card: dict) -> bool:
    with _srs_lock:
        data = _load(SRS_FILE)
        sid = data.get(subject_id, {})
        cid = _card_id(card["frente"])
        if cid not in sid:
            entry = _default_card()
            entry["frente"] = card["frente"]
            entry["verso"] = card["verso"]
            entry["fonte"] = card.get("fonte", "")
            entry["card_type"] = card.get("card_type", "basic")
            sid[cid] = entry
        new_state = not sid[cid].get("favorite", False)
        sid[cid]["favorite"] = new_state
        data[subject_id] = sid
        _atomic_save(SRS_FILE, data)
    return new_state


def delete_card(subject_id: str, frente: str):
    """Remove a card from the deck."""
    with _srs_lock:
        data = _load(SRS_FILE)
        sid = data.get(subject_id, {})
        cid = _card_id(frente)
        sid.pop(cid, None)
        data[subject_id] = sid
        _atomic_save(SRS_FILE, data)


def clear_deck(subject_id: str):
    """Remove all flashcards for a subject."""
    with _srs_lock:
        data = _load(SRS_FILE)
        data[subject_id] = {}
        _atomic_save(SRS_FILE, data)


def get_deck_cards(subject_id: str) -> list[dict]:
    """Return all cards in the deck with their SRS state."""
    with _srs_lock:
        data = _load(SRS_FILE).get(subject_id, {})
    today = date.today().isoformat()
    cards = []
    for v in data.values():
        if not v.get("frente"):
            continue
        next_rev = v.get("next_review", today)
        interval = v.get("interval", 1)
        reps = v.get("reps", 0)
        if reps == 0:
            status = "nova"
        elif interval >= 21:
            status = "dominada"
        elif next_rev <= today:
            status = "para rever"
        else:
            status = "a aprender"
        cards.append({
            "frente": v["frente"],
            "verso": v["verso"],
            "fonte": v.get("fonte", ""),
            "card_type": v.get("card_type", "basic"),
            "interval": interval,
            "ease": v.get("ease", 2.5),
            "reps": reps,
            "last_reviewed": v.get("last_reviewed"),
            "next_review": next_rev,
            "favorite": v.get("favorite", False),
            "status": status,
        })
    return sorted(cards, key=lambda x: x["next_review"])


def get_favorite_cards(subject_id: str) -> list[dict]:
    with _srs_lock:
        data = _load(SRS_FILE).get(subject_id, {})
    return [
        {
            "frente": v["frente"], "verso": v["verso"],
            "fonte": v.get("fonte", ""), "card_type": v.get("card_type", "basic"),
        }
        for v in data.values()
        if v.get("favorite") and v.get("frente")
    ]


def get_srs_stats(subject_id: str) -> dict:
    with _srs_lock:
        data = _load(SRS_FILE).get(subject_id, {})
    today = date.today().isoformat()
    due = sum(1 for c in data.values() if c.get("next_review", "9999") <= today)
    mastered = sum(1 for c in data.values() if c.get("interval", 0) >= 21)
    new = sum(1 for c in data.values() if c.get("reps", 0) == 0)
    favorites = sum(1 for c in data.values() if c.get("favorite"))
    return {
        "total": len(data), "due": due, "mastered": mastered,
        "learning": len(data) - mastered - new, "new": new, "favorites": favorites,
    }


# ── Anki Export ──────────────────────────────────────────────────────────────

def build_anki_package(subject_id: str, subject_name: str) -> bytes:
    """
    Export the full deck as an Anki .apkg file.
    Basic and cloze cards use separate Anki model types.
    Cloze syntax {{c1::term}} is already compatible with Anki natively.
    Requires genanki (pip install genanki).
    Returns raw .apkg bytes; empty bytes if deck is empty.
    """
    import genanki, tempfile, os

    cards = get_deck_cards(subject_id)
    if not cards:
        return b""

    # Deterministic model/deck IDs from subject_id — stable across re-exports
    def _stable_id(seed: str) -> int:
        return int(hashlib.md5(seed.encode()).hexdigest(), 16) % (1 << 31)

    basic_model = genanki.Model(
        _stable_id(f"{subject_id}_basic"),
        "MariaStudy Basic",
        fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Source"}],
        templates=[{
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id=answer>{{Back}}<br><small style="color:#888">{{Source}}</small>',
        }],
    )
    cloze_model = genanki.Model(
        _stable_id(f"{subject_id}_cloze"),
        "MariaStudy Cloze",
        fields=[{"name": "Text"}, {"name": "Source"}],
        templates=[{
            "name": "Cloze",
            "qfmt": "{{cloze:Text}}",
            "afmt": '{{cloze:Text}}<br><small style="color:#888">{{Source}}</small>',
        }],
        model_type=genanki.Model.CLOZE,
    )

    deck = genanki.Deck(_stable_id(f"{subject_id}_deck"), subject_name)

    for card in cards:
        fonte = card.get("fonte", "")
        if card.get("card_type") == "cloze":
            note = genanki.Note(model=cloze_model, fields=[card["frente"], fonte])
        else:
            note = genanki.Note(model=basic_model, fields=[card["frente"], card["verso"], fonte])
        deck.add_note(note)

    package = genanki.Package(deck)
    with tempfile.NamedTemporaryFile(suffix=".apkg", delete=False) as f:
        tmp_path = f.name
    try:
        package.write_to_file(tmp_path)
        with open(tmp_path, "rb") as rf:
            return rf.read()
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ── Import ────────────────────────────────────────────────────────────────────

def parse_import_text(text: str) -> list[dict]:
    """
    Parse flashcards from plain text.
    Supported formats (auto-detected per line):
      - Tab-separated:       front\\tback   or   front\\tback\\tsource
      - Semicolon-separated: front;back    or   front;back;source
      - Anki cloze markup {{c1::term}} is preserved as card_type='cloze'
    Lines starting with # are treated as comments.
    """
    cards = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            parts = line.split("\t")
        elif ";" in line:
            parts = line.split(";")
        else:
            continue  # skip lines with no recognised separator
        if len(parts) < 2:
            continue
        frente = parts[0].strip()
        verso = parts[1].strip()
        fonte = parts[2].strip() if len(parts) > 2 else ""
        if not frente or not verso:
            continue
        card_type = "cloze" if re.search(r"\{\{c\d+::", frente) else "basic"
        cards.append({"frente": frente, "verso": verso, "fonte": fonte, "card_type": card_type})
    return cards


def import_cards(subject_id: str, cards: list[dict]) -> int:
    """Bulk-import cards into the deck. Returns count of new cards added."""
    with _srs_lock:
        data = _load(SRS_FILE)
        sid = data.get(subject_id, {})
        today = date.today().isoformat()
        added = 0
        for card in cards:
            if not card.get("frente") or not card.get("verso"):
                continue
            cid = _card_id(card["frente"])
            if cid not in sid:
                entry = _default_card()
                entry["frente"] = card["frente"]
                entry["verso"] = card["verso"]
                entry["fonte"] = card.get("fonte", "")
                entry["card_type"] = card.get("card_type", "basic")
                entry["next_review"] = today
                sid[cid] = entry
                added += 1
        data[subject_id] = sid
        _atomic_save(SRS_FILE, data)
    logger.info("Imported %d cards into subject %s", added, subject_id)
    return added
