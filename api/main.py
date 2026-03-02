# MUST be first — stubs out streamlit before any src/ import
import api._st_stub  # noqa: F401

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import subjects, files, qa, flashcards, quiz, progress, digest


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the embedding model at startup so the first request isn't slow
    from src.embedder import get_embedder
    get_embedder()
    yield


app = FastAPI(title="MariaStudy API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routes under /api prefix
for router in [
    subjects.router,
    files.router,
    qa.router,
    flashcards.router,
    quiz.router,
    progress.router,
    digest.router,
]:
    app.include_router(router, prefix="/api")
