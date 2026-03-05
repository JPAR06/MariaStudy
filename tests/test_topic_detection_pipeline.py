from __future__ import annotations

from pathlib import Path

import src.llm as llm
import src.processor as processor
import src.rag as rag
import src.subjects as subject_store
import src.vectorstore as vectorstore


def test_ingest_triggers_topic_refresh(monkeypatch):
    called = {"refresh": False, "added": False}

    monkeypatch.setattr(
        processor,
        "extract_file",
        lambda *args, **kwargs: [
            {"text": "texto exemplo", "metadata": {"page": 1, "file": "a.txt"}}
        ],
    )
    monkeypatch.setattr(rag.embedder, "embed", lambda texts: [[0.1, 0.2, 0.3] for _ in texts])
    monkeypatch.setattr(vectorstore, "add_chunks", lambda *args, **kwargs: None)

    def _add_file(subject_id: str, filename: str, pages: int = 0, file_type: str = "notes"):
        called["added"] = True

    monkeypatch.setattr(subject_store, "add_file_to_subject", _add_file)

    def _refresh(_subject_id: str):
        called["refresh"] = True

    monkeypatch.setattr(rag, "_refresh_topics_and_summary", _refresh)

    chunks = rag.ingest_file("subject-x", b"hello world", "a.txt", enable_images=False)
    assert chunks == 1
    assert called["added"] is True
    assert called["refresh"] is True


def test_refresh_topics_populates_topics_and_topic_summaries(monkeypatch):
    subject = subject_store.create_subject("Cardio")
    subject_id = subject["id"]
    subject_store.add_file_to_subject(subject_id, "notes.pdf", pages=5, file_type="notes")
    (Path(subject_store.UPLOADS_DIR) / subject_id).mkdir(parents=True, exist_ok=True)
    (Path(subject_store.UPLOADS_DIR) / subject_id / "notes.pdf").write_bytes(b"%PDF-1.7")

    monkeypatch.setattr(
        vectorstore,
        "sample_spread",
        lambda *_args, **_kwargs: [
            {"text": "insuficiencia cardiaca", "metadata": {"file": "notes.pdf", "page": 1}},
            {"text": "choque cardiogenico", "metadata": {"file": "notes.pdf", "page": 2}},
        ],
    )
    monkeypatch.setattr(processor, "extract_toc", lambda *_args, **_kwargs: ["Insuficiencia", "Choque"])
    monkeypatch.setattr(llm, "extract_topics", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(vectorstore, "assign_topics_to_chunks", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(llm, "generate_summary", lambda *_args, **_kwargs: "Resumo geral")
    monkeypatch.setattr(rag, "get_topic_chunks", lambda *_args, **_kwargs: [{"text": "topico texto"}])
    monkeypatch.setattr(llm, "generate_topic_summary", lambda topic, *_args, **_kwargs: f"Resumo {topic}")

    rag._refresh_topics_and_summary(subject_id)

    updated = subject_store.get_subject(subject_id)
    assert updated is not None
    assert updated["topics"] == ["Insuficiencia", "Choque"]
    assert updated["summary"] == "Resumo geral"
    assert updated["topic_summaries"]["Insuficiencia"] == "Resumo Insuficiencia"
    assert updated["topic_summaries"]["Choque"] == "Resumo Choque"
