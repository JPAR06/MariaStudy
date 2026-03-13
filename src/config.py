from pathlib import Path
from dotenv import load_dotenv

# --- Paths ---
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma_db"
SUBJECTS_FILE = DATA_DIR / "subjects.json"
PROGRESS_FILE = DATA_DIR / "progress.json"
SRS_FILE = DATA_DIR / "srs.json"

# Create dirs on import
for _d in [DATA_DIR, UPLOADS_DIR, CHROMA_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# --- Models ---
EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"
LLM_REASONING = "llama-3.3-70b-versatile"          # Q&A
LLM_QUALITY = "llama-3.3-70b-versatile"            # Flashcards, quiz
LLM_FAST = "llama-3.1-8b-instant"                  # Topics, summaries
LLM_VISION = "llama-3.2-11b-vision-preview"        # Image captions

# --- RAG ---
CHUNK_SIZE = 400    # words per chunk (approx 530 tokens)
CHUNK_OVERLAP = 50  # words overlap between chunks
TOP_K = 6           # chunks to retrieve for RAG

# --- Rate limits (Groq free tier) ---
GROQ_RATE_LIMIT_DELAY = 2   # seconds between 70B generation calls (post-ingest)
GROQ_VISION_DELAY = 0.5     # seconds between vision API calls (image captions)
