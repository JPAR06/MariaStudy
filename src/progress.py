import json
import hashlib
import re
from datetime import date, timedelta
from src.config import PROGRESS_FILE, SRS_FILE


def _load(path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Quiz History ──────────────────────────────────────────────────────────────

def save_quiz_result(subject_id: str, topic: str, score: int, total: int):
    data = _load(PROGRESS_FILE)
    if subject_id not in data:
        data[subject_id] = []
    data[subject_id].append({
        "date": date.today().isoformat(),
        "topic": topic,
        "score": score,
        "total": total,
        "pct": round(score / total * 100, 1) if total > 0 else 0,
    })
    _save(PROGRESS_FILE, data)


def get_quiz_history(subject_id: str) -> list:
    return _load(PROGRESS_FILE).get(subject_id, [])


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
    return hashlib.md5(frente.encode()).hexdigest()[:12]


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
        _save(SRS_FILE, data)


def save_flashcard_result(subject_id: str, card: dict, result: str):
    """
    result: 'again' | 'hard' | 'good' | 'easy'
    SM-2 intervals:
      again → reset to 1 day, ease -0.20
      hard  → interval × 1.2, ease -0.15
      good  → interval × ease (normal advance)
      easy  → interval × ease × 1.3, ease +0.15
    """
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
    _save(SRS_FILE, data)


def toggle_favorite(subject_id: str, card: dict) -> bool:
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
    _save(SRS_FILE, data)
    return new_state


def delete_card(subject_id: str, frente: str):
    """Remove a card from the deck."""
    data = _load(SRS_FILE)
    sid = data.get(subject_id, {})
    cid = _card_id(frente)
    sid.pop(cid, None)
    data[subject_id] = sid
    _save(SRS_FILE, data)


def get_deck_cards(subject_id: str) -> list[dict]:
    """Return all cards in the deck with their SRS state."""
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
            "reps": reps,
            "next_review": next_rev,
            "favorite": v.get("favorite", False),
            "status": status,
        })
    return sorted(cards, key=lambda x: x["next_review"])


def get_favorite_cards(subject_id: str) -> list[dict]:
    data = _load(SRS_FILE).get(subject_id, {})
    return [
        {
            "frente": v["frente"], "verso": v["verso"],
            "fonte": v.get("fonte", ""), "card_type": v.get("card_type", "basic"),
        }
        for v in data.values()
        if v.get("favorite") and v.get("frente")
    ]


def is_favorite(subject_id: str, frente: str) -> bool:
    data = _load(SRS_FILE).get(subject_id, {})
    cid = _card_id(frente)
    return data.get(cid, {}).get("favorite", False)


def get_srs_stats(subject_id: str) -> dict:
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


def sort_cards_by_due(subject_id: str, cards: list) -> list:
    data = _load(SRS_FILE).get(subject_id, {})
    today = date.today().isoformat()

    def _priority(card):
        cid = _card_id(card.get("frente", ""))
        info = data.get(cid, {})
        next_rev = info.get("next_review", "0000")
        return (0 if next_rev <= today else 1, next_rev)

    return sorted(cards, key=_priority)


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
    _save(SRS_FILE, data)
    return added
