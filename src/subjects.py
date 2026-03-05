import json
import logging
import os
import shutil
import tempfile
import threading
import uuid
from datetime import datetime

from src.config import SUBJECTS_FILE, UPLOADS_DIR

logger = logging.getLogger(__name__)

VALID_SUBJECT_STATUS = {"active", "finished"}

_lock = threading.Lock()


def _normalize_subject(subject: dict) -> dict:
    status = subject.get("status", "active")
    if status not in VALID_SUBJECT_STATUS:
        status = "active"
    subject["status"] = status
    subject.setdefault("files", [])
    subject.setdefault("topics", [])
    subject.setdefault("summary", "")
    subject.setdefault("topic_summaries", {})
    for f in subject["files"]:
        f.setdefault("topics", [])
    return subject


def _load() -> list:
    if not SUBJECTS_FILE.exists():
        return []
    try:
        data = json.loads(SUBJECTS_FILE.read_text(encoding="utf-8"))
        return [_normalize_subject(s) for s in data]
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Falha ao carregar subjects.json: %s", e)
        return []


def _save(data: list):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    SUBJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=SUBJECTS_FILE.parent, prefix=".subjects_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, SUBJECTS_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def list_subjects() -> list:
    with _lock:
        return _load()


def get_subject(subject_id: str) -> dict | None:
    with _lock:
        return next((s for s in _load() if s["id"] == subject_id), None)


def create_subject(name: str) -> dict:
    with _lock:
        data = _load()
        subject = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "created_at": datetime.now().isoformat(),
            "files": [],
            "topics": [],
            "summary": "",
            "topic_summaries": {},
            "status": "active",
        }
        data.append(subject)
        _save(data)
        logger.info("Criado subject %s (%s)", subject["id"], name)
        return subject


def delete_subject(subject_id: str):
    with _lock:
        data = [s for s in _load() if s["id"] != subject_id]
        _save(data)
    subject_dir = UPLOADS_DIR / subject_id
    if subject_dir.exists():
        shutil.rmtree(subject_dir)
    logger.info("Eliminado subject %s", subject_id)


def add_file_to_subject(subject_id: str, filename: str, pages: int = 0, file_type: str = "notes"):
    with _lock:
        data = _load()
        for s in data:
            if s["id"] == subject_id:
                names = [f["name"] for f in s["files"]]
                if filename not in names:
                    s["files"].append({"name": filename, "pages": pages, "type": file_type, "topics": []})
        _save(data)


def set_file_type(subject_id: str, filename: str, file_type: str):
    with _lock:
        data = _load()
        for s in data:
            if s["id"] == subject_id:
                for f in s["files"]:
                    if f["name"] == filename:
                        f["type"] = file_type
        _save(data)
    from src.vectorstore import update_file_type
    update_file_type(subject_id, filename, file_type)


def remove_file_from_subject(subject_id: str, filename: str):
    with _lock:
        data = _load()
        for s in data:
            if s["id"] == subject_id:
                s["files"] = [f for f in s["files"] if f["name"] != filename]
        _save(data)


def set_file_topics(subject_id: str, filename: str, topics: list):
    with _lock:
        data = _load()
        for s in data:
            if s["id"] == subject_id:
                for f in s["files"]:
                    if f["name"] == filename:
                        f["topics"] = topics
        _save(data)


def update_topics(subject_id: str, topics: list):
    with _lock:
        data = _load()
        for s in data:
            if s["id"] == subject_id:
                s["topics"] = topics
        _save(data)


def update_topic_summary(subject_id: str, topic: str, summary: str):
    with _lock:
        data = _load()
        for s in data:
            if s["id"] == subject_id:
                if "topic_summaries" not in s:
                    s["topic_summaries"] = {}
                s["topic_summaries"][topic] = summary
        _save(data)


def update_summary(subject_id: str, summary: str):
    with _lock:
        data = _load()
        for s in data:
            if s["id"] == subject_id:
                s["summary"] = summary
        _save(data)


def set_subject_status(subject_id: str, status: str) -> dict | None:
    normalized_status = status if status in VALID_SUBJECT_STATUS else "active"
    with _lock:
        data = _load()
        updated: dict | None = None
        for s in data:
            if s["id"] == subject_id:
                s["status"] = normalized_status
                updated = s
                break
        _save(data)
    return updated
