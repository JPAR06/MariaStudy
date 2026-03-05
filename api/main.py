import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.auth import require_auth
from api.routes import subjects, files, qa, flashcards, quiz, progress, digest
from api.routes import auth as auth_routes
from src.config import UPLOADS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MariaStudy API starting — warming up embedder…")
    from src.embedder import get_embedder
    get_embedder()
    logger.info("Embedder ready.")
    yield
    logger.info("MariaStudy API shutting down.")


app = FastAPI(title="MariaStudy API", version="1.0.0", lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Restrict to the real frontend origin. Set ALLOWED_ORIGINS in .env for production
# (comma-separated list, e.g. "https://study.example.com,http://localhost:3000").
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Public routes — no auth ────────────────────────────────────────────────────
app.include_router(auth_routes.router, prefix="/api")


def _safe_path(base: Path, *parts: str) -> Path:
    """Resolve a path and raise 400 if it would escape the base directory."""
    resolved = (base / Path(*parts)).resolve()
    if not str(resolved).startswith(str(base.resolve()) + os.sep) and resolved != base.resolve():
        raise HTTPException(400, "Caminho inválido")
    return resolved


@app.get("/api/files/{subject_id}/{filename}")
def serve_file(subject_id: str, filename: str):
    """Serve raw PDF for the viewer iframe (public — iframes can't send auth headers)."""
    path = _safe_path(Path(UPLOADS_DIR), subject_id, filename)
    if not path.exists():
        raise HTTPException(404, "File not found")
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
    return FileResponse(str(path), media_type=media_type, headers={"Content-Disposition": "inline"})


# ── Protected routes — require valid JWT ──────────────────────────────────────
for router in [
    subjects.router,
    files.router,
    qa.router,
    flashcards.router,
    quiz.router,
    progress.router,
    digest.router,
]:
    app.include_router(router, prefix="/api", dependencies=[Depends(require_auth)])
