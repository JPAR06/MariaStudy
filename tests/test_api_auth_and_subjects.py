from __future__ import annotations

from fastapi.testclient import TestClient


def test_protected_route_requires_auth(client: TestClient):
    res = client.get("/api/subjects")
    assert res.status_code == 401


def test_login_success(client: TestClient, auth_headers):
    assert "Authorization" in auth_headers


def test_subject_lifecycle_and_status(client: TestClient, auth_headers):
    created = client.post("/api/subjects", json={"name": "Neurologia"}, headers=auth_headers)
    assert created.status_code == 201, created.text
    subject = created.json()
    assert subject["name"] == "Neurologia"
    assert subject["status"] == "active"
    subject_id = subject["id"]

    fetched = client.get(f"/api/subjects/{subject_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == subject_id

    updated = client.put(
        f"/api/subjects/{subject_id}/status",
        json={"status": "finished"},
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "finished"

    listed = client.get("/api/subjects", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["status"] == "finished"
