"""Pydantic models for all API request/response contracts."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel


# â”€â”€ Subjects â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SubjectCreate(BaseModel):
    name: str


class FileRecord(BaseModel):
    name: str
    pages: int = 0
    type: Literal["notes", "exercises"] = "notes"
    topics: list[str] = []


class SubjectResponse(BaseModel):
    id: str
    name: str
    created_at: str
    files: list[FileRecord] = []
    topics: list[str] = []
    summary: str = ""
    topic_summaries: dict[str, str] = {}
    status: Literal["active", "finished"] = "active"


class SubjectStatusUpdate(BaseModel):
    status: Literal["active", "finished"]


# â”€â”€ Files â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class FileTypeUpdate(BaseModel):
    file_type: Literal["notes", "exercises"]


class IngestResult(BaseModel):
    chunks: int
    filename: str


# â”€â”€ Q&A â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AskRequest(BaseModel):
    question: str
    topic_filter: str | None = None


class Source(BaseModel):
    file: str
    page: int


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


class SearchRequest(BaseModel):
    question: str
    top_k: int = 3


class SearchResult(BaseModel):
    subject_id: str
    subject_name: str
    best_distance: float
    chunks: list[dict[str, Any]]


# â”€â”€ Flashcards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class FlashcardBase(BaseModel):
    frente: str
    verso: str
    fonte: str = ""
    card_type: str = "basic"  # "basic" | "cloze"


class FlashcardInDB(FlashcardBase):
    interval: int = 1
    ease: float = 2.5
    reps: int = 0
    last_reviewed: str | None = None
    next_review: str = ""
    favorite: bool = False
    status: str = "nova"  # "nova"|"a aprender"|"para rever"|"dominada"


class FlashcardGenerateRequest(BaseModel):
    topic: str
    topics: list[str] | None = None
    n: int = 5


class FlashcardGenerateResponse(BaseModel):
    flashcards: list[FlashcardBase]


class FlashcardResultRequest(BaseModel):
    card: dict[str, Any]  # full card dict (frente, verso, fonte, card_type)
    result: Literal["again", "hard", "good", "easy"]


class FlashcardFavoriteRequest(BaseModel):
    card: dict[str, Any]


class FlashcardImportRequest(BaseModel):
    text: str  # raw tab/semicolon/Anki cloze text


class FlashcardImportResponse(BaseModel):
    imported: int


# â”€â”€ Quiz â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class QuizGenerateRequest(BaseModel):
    topic: str
    topics: list[str] | None = None
    n: int = 5
    difficulty: Literal["FÃ¡cil", "MÃ©dio", "DifÃ­cil"] = "MÃ©dio"


class QuizQuestion(BaseModel):
    pergunta: str
    opcoes: list[str]   # ["A) ...", "B) ...", "C) ...", "D) ..."]
    correta: int        # 0-3 index
    explicacao: str
    fonte: str


class QuizGenerateResponse(BaseModel):
    questoes: list[QuizQuestion]


class QuizSavedToggleRequest(BaseModel):
    question: QuizQuestion


class QuizSavedToggleResponse(BaseModel):
    saved: bool


class QuizResultRequest(BaseModel):
    topic: str
    score: int
    total: int


# â”€â”€ Progress â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class QuizAttempt(BaseModel):
    date: str
    topic: str
    score: int
    total: int
    pct: float


class TopicStat(BaseModel):
    topic: str
    attempts: int
    avg_pct: float
    last_date: str


class SRSStats(BaseModel):
    total: int
    due: int
    mastered: int
    learning: int
    new: int
    favorites: int


class ProgressResponse(BaseModel):
    quiz_history: list[QuizAttempt]
    topic_stats: list[TopicStat]
    srs_stats: SRSStats
    file_stats: dict[str, Any]  # total_files, total_pages, total_chunks


# â”€â”€ Daily Digest â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class DigestQuestionOfDay(BaseModel):
    frente: str
    verso: str
    fonte: str
    card_type: str
    subject_name: str


class DigestResponse(BaseModel):
    streak: int
    due_total: int
    weak_topic: str | None
    weak_topic_subject: str | None
    question_of_day: DigestQuestionOfDay | None

