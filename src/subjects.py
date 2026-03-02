import json
import shutil
import uuid
from datetime import datetime
from src.config import SUBJECTS_FILE, UPLOADS_DIR


def _load() -> list:
    if not SUBJECTS_FILE.exists():
        return []
    return json.loads(SUBJECTS_FILE.read_text(encoding="utf-8"))


def _save(data: list):
    SUBJECTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_subjects() -> list:
    return _load()


def get_subject(subject_id: str) -> dict | None:
    return next((s for s in _load() if s["id"] == subject_id), None)


def create_subject(name: str) -> dict:
    data = _load()
    subject = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "created_at": datetime.now().isoformat(),
        "files": [],
        "topics": [],
        "summary": "",
    }
    data.append(subject)
    _save(data)
    return subject


def delete_subject(subject_id: str):
    data = [s for s in _load() if s["id"] != subject_id]
    _save(data)
    subject_dir = UPLOADS_DIR / subject_id
    if subject_dir.exists():
        shutil.rmtree(subject_dir)


def add_file_to_subject(subject_id: str, filename: str, pages: int = 0, file_type: str = "notes"):
    data = _load()
    for s in data:
        if s["id"] == subject_id:
            names = [f["name"] for f in s["files"]]
            if filename not in names:
                s["files"].append({"name": filename, "pages": pages, "type": file_type})
    _save(data)


def set_file_type(subject_id: str, filename: str, file_type: str):
    """
    Change the type of an already-ingested file (notes | exercises).
    Updates both subjects.json and ChromaDB chunk metadata so filters work immediately.
    """
    data = _load()
    for s in data:
        if s["id"] == subject_id:
            for f in s["files"]:
                if f["name"] == filename:
                    f["type"] = file_type
    _save(data)
    # Sync ChromaDB so the file_type filter in query() reflects the change
    from src.vectorstore import update_file_type
    update_file_type(subject_id, filename, file_type)


def remove_file_from_subject(subject_id: str, filename: str):
    data = _load()
    for s in data:
        if s["id"] == subject_id:
            s["files"] = [f for f in s["files"] if f["name"] != filename]
    _save(data)


def update_topics(subject_id: str, topics: list):
    data = _load()
    for s in data:
        if s["id"] == subject_id:
            s["topics"] = topics
    _save(data)


def update_summary(subject_id: str, summary: str):
    data = _load()
    for s in data:
        if s["id"] == subject_id:
            s["summary"] = summary
    _save(data)
