from __future__ import annotations

import json

from fastapi.testclient import TestClient

import src.rag as rag


def test_upload_sse_includes_dynamic_chunk_progress(
    client: TestClient,
    auth_headers,
    monkeypatch,
):
    created = client.post("/api/subjects", json={"name": "Cardiologia"}, headers=auth_headers)
    assert created.status_code == 201, created.text
    subject_id = created.json()["id"]

    def fake_ingest_file(
        _subject_id: str,
        _file_bytes: bytes,
        _filename: str,
        enable_images: bool = True,
        progress_cb=None,
        file_type: str = "notes",
    ) -> int:
        assert enable_images is False
        assert file_type == "notes"
        if progress_cb:
            progress_cb("1/3 chunks", 55)
            progress_cb("2/3 chunks", 70)
            progress_cb("3/3 chunks", 85)
        return 3

    monkeypatch.setattr(rag, "ingest_file", fake_ingest_file)

    files = {"file": ("test.txt", b"lorem ipsum", "text/plain")}
    data = {"enable_images": "false", "file_type": "notes"}
    res = client.post(f"/api/subjects/{subject_id}/files", headers=auth_headers, files=files, data=data)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")

    events = [
        json.loads(line.replace("data: ", ""))
        for line in res.text.splitlines()
        if line.startswith("data: ")
    ]
    steps = [e.get("step", "") for e in events]

    assert "1/3 chunks" in steps
    assert "2/3 chunks" in steps
    assert "3/3 chunks" in steps
    assert events[-1].get("done") is True
    assert events[-1].get("chunks") == 3
