from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient

# Ensure local packages (api/, src/) resolve when running plain `pytest`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import api.main as api_main
import api.routes.auth as auth_routes
import src.config as config
import src.progress as progress
import src.subjects as subjects


@pytest.fixture(autouse=True)
def isolate_data_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    uploads_dir = data_dir / "uploads"
    chroma_dir = data_dir / "chroma_db"
    data_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    subjects_file = data_dir / "subjects.json"
    progress_file = data_dir / "progress.json"
    srs_file = data_dir / "srs.json"
    users_file = data_dir / "users.json"

    # Patch shared config
    monkeypatch.setattr(config, "DATA_DIR", data_dir, raising=False)
    monkeypatch.setattr(config, "UPLOADS_DIR", uploads_dir, raising=False)
    monkeypatch.setattr(config, "CHROMA_DIR", chroma_dir, raising=False)
    monkeypatch.setattr(config, "SUBJECTS_FILE", subjects_file, raising=False)
    monkeypatch.setattr(config, "PROGRESS_FILE", progress_file, raising=False)
    monkeypatch.setattr(config, "SRS_FILE", srs_file, raising=False)

    # Patch modules that copied config paths at import time
    monkeypatch.setattr(subjects, "UPLOADS_DIR", uploads_dir, raising=False)
    monkeypatch.setattr(subjects, "SUBJECTS_FILE", subjects_file, raising=False)
    monkeypatch.setattr(progress, "PROGRESS_FILE", progress_file, raising=False)
    monkeypatch.setattr(progress, "SRS_FILE", srs_file, raising=False)
    monkeypatch.setattr(auth_routes, "USERS_FILE", users_file, raising=False)

    users_file.write_text("{}", encoding="utf-8")
    yield


@pytest.fixture(scope="session", autouse=True)
def disable_app_lifespan():
    @asynccontextmanager
    async def _noop(_app):
        yield

    api_main.app.router.lifespan_context = _noop


@pytest.fixture
def client():
    return TestClient(api_main.app)


@pytest.fixture
def auth_headers(client: TestClient):
    users = {
        "maria": {
            "password_hash": bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode(),
            "display_name": "Maria",
        }
    }
    auth_routes.USERS_FILE.write_text(json.dumps(users), encoding="utf-8")

    res = client.post("/api/auth/login", json={"username": "maria", "password": "123456"})
    assert res.status_code == 200, res.text
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}
