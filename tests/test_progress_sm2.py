from __future__ import annotations

import src.progress as progress


def _base_card():
    return {
        "frente": "Qual a causa mais comum de AVC isquémico?",
        "verso": "Aterosclerose de grandes vasos.",
        "fonte": "Neuro.pdf, Pág. 12",
        "card_type": "basic",
    }


def test_sm2_again_resets_interval():
    sid = "subj1"
    card = _base_card()

    progress.save_card_to_deck(sid, card)
    progress.save_flashcard_result(sid, card, "again")
    deck = progress.get_deck_cards(sid)
    c = next(x for x in deck if x["frente"] == card["frente"])

    assert c["interval"] == 1
    assert c["reps"] == 0
    assert c["status"] == "nova"


def test_sm2_good_advances_interval_and_reps():
    sid = "subj2"
    card = _base_card()

    progress.save_card_to_deck(sid, card)
    progress.save_flashcard_result(sid, card, "good")
    deck = progress.get_deck_cards(sid)
    c = next(x for x in deck if x["frente"] == card["frente"])

    assert c["reps"] == 1
    assert c["interval"] >= 2
    assert c["status"] in {"a aprender", "para rever", "dominada"}


def test_sm2_easy_increases_ease():
    sid = "subj3"
    card = _base_card()

    progress.save_card_to_deck(sid, card)
    before = next(x for x in progress.get_deck_cards(sid) if x["frente"] == card["frente"])
    progress.save_flashcard_result(sid, card, "easy")
    after = next(x for x in progress.get_deck_cards(sid) if x["frente"] == card["frente"])

    assert after["ease"] > before["ease"]
    assert after["reps"] == 1
