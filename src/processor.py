"""PDF and text file processing: extract text, tables, images → chunks."""
import base64
import logging
import time
from pathlib import Path
from typing import Callable

import pdfplumber
import fitz  # PyMuPDF

from src.config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)


def extract_file(
    file_path: str,
    subject_id: str,
    filename: str,
    caption_fn: Callable | None = None,
    progress_cb: Callable | None = None,
    file_type: str = "notes",
) -> list[dict]:
    """Dispatch to the right extractor based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(file_path, subject_id, filename, caption_fn, progress_cb, file_type)
    elif ext in (".txt", ".md"):
        return _extract_text(file_path, subject_id, filename, file_type)
    else:
        return []


# ── PDF ───────────────────────────────────────────────────────────────────────

def _extract_pdf(
    file_path: str,
    subject_id: str,
    filename: str,
    caption_fn: Callable | None,
    progress_cb: Callable | None,
    file_type: str = "notes",
) -> list[dict]:
    chunks = []
    try:
        with pdfplumber.open(file_path) as pdf:
            fitz_doc = fitz.open(file_path)
            n = len(pdf.pages)

            for i, plumber_page in enumerate(pdf.pages):
                if progress_cb:
                    pct = round((i / max(n, 1)) * 45, 1)
                    progress_cb(f"Pág. {i+1}/{n}", pct)

                page_text = _process_page(
                    plumber_page, fitz_doc[i], caption_fn
                )
                if page_text.strip():
                    chunks.extend(
                        _chunk_text(page_text, i + 1, subject_id, filename, file_type)
                    )

            fitz_doc.close()
    except Exception:
        logger.exception("PDF extraction failed for %s", filename)
    return chunks


def _process_page(plumber_page, fitz_page, caption_fn) -> str:
    parts = []

    # 1. Raw text
    text = plumber_page.extract_text() or ""
    if text.strip():
        parts.append(text)

    # 2. Tables → Markdown
    for table in (plumber_page.extract_tables() or []):
        if not table:
            continue
        rows = []
        for j, row in enumerate(table):
            cells = [str(c or "").replace("\n", " ") for c in row]
            rows.append("| " + " | ".join(cells) + " |")
            if j == 0:
                rows.append("|" + "|".join(["---"] * len(cells)) + "|")
        parts.append("[TABELA]\n" + "\n".join(rows))

    # 3. Images → captions (only if caption_fn provided)
    if caption_fn:
        for img_info in fitz_page.get_images(full=False):
            try:
                xref = img_info[0]
                base_img = fitz_page.parent.extract_image(xref)
                b64 = base64.b64encode(base_img["image"]).decode()
                ext = base_img.get("ext", "png")
                caption = caption_fn(b64, ext)
                if caption:
                    parts.append(f"[IMAGEM: {caption}]")
                time.sleep(0.5)  # Groq vision rate limit
            except Exception:
                pass

    return "\n\n".join(parts)


# ── Plain text ────────────────────────────────────────────────────────────────

def _extract_text(file_path: str, subject_id: str, filename: str, file_type: str = "notes") -> list[dict]:
    try:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    return _chunk_text(text, 1, subject_id, filename, file_type)


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, page: int, subject_id: str, filename: str, file_type: str = "notes") -> list[dict]:
    """
    Paragraph-aware chunking:
    1. Split on blank lines to get natural paragraphs.
    2. Merge short paragraphs until they reach CHUNK_SIZE words.
    3. Oversized paragraphs are split with a sliding word-window (CHUNK_OVERLAP).
    """
    # Split on blank lines (handles \n\n and Windows \r\n\r\n)
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not raw_paragraphs:
        return []

    # Merge neighbouring paragraphs until we approach CHUNK_SIZE.
    # Paragraphs are joined with \n\n so the LLM sees structural breaks.
    merged: list[str] = []
    current_paras: list[str] = []
    current_word_count: int = 0

    for para in raw_paragraphs:
        para_wc = len(para.split())
        if current_word_count + para_wc <= CHUNK_SIZE:
            current_paras.append(para)
            current_word_count += para_wc
        else:
            if current_paras:
                merged.append("\n\n".join(current_paras))
            # Start fresh with this paragraph (may itself be oversized)
            current_paras = [para]
            current_word_count = para_wc

    if current_paras:
        merged.append("\n\n".join(current_paras))

    # Now split any oversized merged block with a sliding word-window.
    # We split on whitespace but reconstruct with spaces (paragraph breaks inside
    # an oversized block are already rare — the block was one large paragraph).
    chunks = []
    idx = 0
    for block in merged:
        words = block.split()
        if len(words) <= CHUNK_SIZE:
            chunks.append({
                "text": block,
                "metadata": {
                    "file": filename,
                    "page": page,
                    "chunk_index": idx,
                    "subject_id": subject_id,
                    "file_type": file_type,
                },
            })
            idx += 1
        else:
            start = 0
            while start < len(words):
                end = min(start + CHUNK_SIZE, len(words))
                chunks.append({
                    "text": " ".join(words[start:end]),
                    "metadata": {
                        "file": filename,
                        "page": page,
                        "chunk_index": idx,
                        "subject_id": subject_id,
                        "file_type": file_type,
                    },
                })
                idx += 1
                if end == len(words):
                    break
                start = end - CHUNK_OVERLAP

    return chunks


def extract_toc(file_path: str) -> list[str]:
    """
    Extract chapter/section titles from the PDF's bookmark outline (TOC).
    Returns a clean list of unique topic strings, or [] if the PDF has no outline.

    Strategy:
    - Prefer level-1 entries (chapters); include level-2 if there are few level-1s.
    - Skip entries that look like page numbers, single characters, or pure numbers.
    - Deduplicate while preserving order.
    """
    try:
        doc = fitz.open(file_path)
        toc = doc.get_toc(simple=True)  # [(level, title, page), ...]
        doc.close()
    except Exception:
        return []

    if not toc:
        return []

    def _is_meaningful(title: str) -> bool:
        t = title.strip()
        if not t or len(t) < 3:
            return False
        # Skip pure numbers / roman numerals / single words that are just numbering
        if t.replace(".", "").replace(" ", "").isdigit():
            return False
        # Skip entries that are just whitespace/punctuation
        if not any(c.isalpha() for c in t):
            return False
        return True

    level1 = [title.strip() for level, title, _ in toc if level == 1 and _is_meaningful(title)]
    level2 = [title.strip() for level, title, _ in toc if level == 2 and _is_meaningful(title)]

    # Use level-1 if we have enough; supplement with level-2 if sparse
    if len(level1) >= 5:
        candidates = level1
    elif len(level1) >= 2:
        candidates = level1 + level2
    else:
        candidates = level2  # flat document with no chapters, only sections

    # Deduplicate preserving order, cap at 20 topics
    seen: set[str] = set()
    result: list[str] = []
    for t in candidates:
        lower = t.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(t)
        if len(result) >= 20:
            break

    return result


def count_pages(file_path: str) -> int:
    try:
        with pdfplumber.open(file_path) as pdf:
            return len(pdf.pages)
    except Exception:
        return 0
