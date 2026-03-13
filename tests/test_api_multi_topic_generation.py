from __future__ import annotations

import json

from fastapi.testclient import TestClient

import src.llm as llm
import src.progress as progress
import src.rag as rag
import src.subjects as subjects


def _sse_events(text: str) -> list[dict]:
    return [
        json.loads(line.replace("data: ", ""))
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def test_quiz_generate_uses_only_selected_topics(
    client: TestClient,
    auth_headers,
    monkeypatch,
):
    created = client.post("/api/subjects", json={"name": "Neurologia"}, headers=auth_headers)
    assert created.status_code == 201, created.text
    subject_id = created.json()["id"]

    requested_topics: list[str] = []

    def fake_get_subject(_subject_id: str):
        return {"id": _subject_id, "name": "Neurologia"}

    def fake_get_topic_chunks(_subject_id: str, topic: str, top_k: int = 10):
        requested_topics.append(topic)
        return [{"text": f"chunk-{topic}", "metadata": {"file": f"{topic}.pdf", "page": 1}}]

    def fake_generate_quiz(chunks, topic: str, n: int, difficulty: str):
        assert "Cardio" not in {c["text"] for c in chunks}
        return [
            {
                "pergunta": f"Pergunta sobre {topic}",
                "opcoes": ["A) 1", "B) 2", "C) 3", "D) 4"],
                "correta": 0,
                "explicacao": difficulty,
                "fonte": chunks[i % len(chunks)]["metadata"]["file"],
            }
            for i in range(n)
        ]

    monkeypatch.setattr(subjects, "get_subject", fake_get_subject)
    monkeypatch.setattr(rag, "get_topic_chunks", fake_get_topic_chunks)
    monkeypatch.setattr(llm, "generate_quiz", fake_generate_quiz)

    res = client.post(
        f"/api/subjects/{subject_id}/quiz/generate",
        headers=auth_headers,
        json={"topic": "Toda a UC", "topics": ["Coma", "Epilepsia"], "n": 2, "difficulty": "Médio"},
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(res.text)
    questions = [e for e in events if e.get("pergunta")]
    assert len(questions) == 2
    assert requested_topics == ["Coma", "Epilepsia"]
    assert all(q["fonte"] in {"Coma.pdf", "Epilepsia.pdf"} for q in questions)


def test_flashcards_generate_uses_only_selected_topics(
    client: TestClient,
    auth_headers,
    monkeypatch,
):
    created = client.post("/api/subjects", json={"name": "Neurologia"}, headers=auth_headers)
    assert created.status_code == 201, created.text
    subject_id = created.json()["id"]

    requested_topics: list[str] = []

    def fake_get_subject(_subject_id: str):
        return {"id": _subject_id, "name": "Neurologia"}

    def fake_get_topic_chunks(_subject_id: str, topic: str, top_k: int = 8):
        requested_topics.append(topic)
        return [{"text": f"chunk-{topic}", "metadata": {"file": f"{topic}.pdf", "page": 2}}]

    def fake_generate_flashcards(chunks, topic: str, n: int):
        assert "Cardio" not in {c["text"] for c in chunks}
        return [{
            "frente": f"Frente {topic}",
            "verso": "Verso",
            "fonte": chunks[0]["metadata"]["file"],
            "card_type": "basic",
        }]

    monkeypatch.setattr(subjects, "get_subject", fake_get_subject)
    monkeypatch.setattr(rag, "get_topic_chunks", fake_get_topic_chunks)
    monkeypatch.setattr(llm, "generate_flashcards", fake_generate_flashcards)
    monkeypatch.setattr(progress, "save_card_to_deck", lambda *_args, **_kwargs: None)

    res = client.post(
        f"/api/subjects/{subject_id}/flashcards/generate",
        headers=auth_headers,
        json={"topic": "Toda a UC", "topics": ["Coma", "Epilepsia"], "n": 2},
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(res.text)
    cards = [e for e in events if e.get("frente")]
    assert len(cards) == 1  # fake generator returns 1 card per batch call
    assert requested_topics == ["Coma", "Epilepsia"]
    assert cards[0]["fonte"] in {"Coma.pdf", "Epilepsia.pdf"}
