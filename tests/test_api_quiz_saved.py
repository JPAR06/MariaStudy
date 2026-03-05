from __future__ import annotations

from fastapi.testclient import TestClient


def test_quiz_saved_toggle_and_list(client: TestClient, auth_headers):
    created = client.post("/api/subjects", json={"name": "Neurologia"}, headers=auth_headers)
    assert created.status_code == 201, created.text
    subject_id = created.json()["id"]

    question = {
        "pergunta": "Qual é o nervo craniano I?",
        "opcoes": ["A) Olfatório", "B) Óptico", "C) Trigémio", "D) Vago"],
        "correta": 0,
        "explicacao": "É o olfatório.",
        "fonte": "neuro.pdf, Pág. 2",
    }

    save_res = client.post(
        f"/api/subjects/{subject_id}/quiz/saved",
        json={"question": question},
        headers=auth_headers,
    )
    assert save_res.status_code == 200, save_res.text
    assert save_res.json()["saved"] is True

    listed = client.get(f"/api/subjects/{subject_id}/quiz/saved", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    saved_items = listed.json()
    assert len(saved_items) == 1
    assert saved_items[0]["pergunta"] == question["pergunta"]

    unsave_res = client.post(
        f"/api/subjects/{subject_id}/quiz/saved",
        json={"question": question},
        headers=auth_headers,
    )
    assert unsave_res.status_code == 200, unsave_res.text
    assert unsave_res.json()["saved"] is False

    listed_after = client.get(f"/api/subjects/{subject_id}/quiz/saved", headers=auth_headers)
    assert listed_after.status_code == 200, listed_after.text
    assert listed_after.json() == []
