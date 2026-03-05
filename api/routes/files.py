import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, Form
from fastapi.responses import FileResponse, StreamingResponse

from api.schemas import FileTypeUpdate
from src.config import UPLOADS_DIR

router = APIRouter()
logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


@router.post("/subjects/{subject_id}/files")
async def upload_file(
    subject_id: str,
    file: UploadFile,
    enable_images: bool = Form(False),
    file_type: str = Form("notes"),
):
    """Upload + ingest a file. Returns SSE stream with progress events."""
    from src.subjects import get_subject
    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")

    file_bytes = await file.read()
    if len(file_bytes) > 200 * 1024 * 1024:  # 200 MB hard cap
        raise HTTPException(413, "Ficheiro demasiado grande (máx 200 MB)")

    # Strip path components to prevent directory traversal
    from pathlib import PurePosixPath
    raw_name = file.filename or "upload.pdf"
    filename = PurePosixPath(raw_name).name or "upload.pdf"

    logger.info("Upload started: subject=%s file=%s size=%d type=%s", subject_id, filename, len(file_bytes), file_type)

    # Shared queue for progress callbacks → SSE
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def progress_cb(step: str, pct: float):
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"step": step, "pct": pct}
        )

    async def event_stream():
        from src.rag import ingest_file
        # run blocking ingest in thread pool
        future = loop.run_in_executor(
            _executor,
            lambda: ingest_file(
                subject_id, file_bytes, filename,
                enable_images=enable_images,
                progress_cb=progress_cb,
                file_type=file_type,
            ),
        )

        chunks_created = 0
        while True:
            # drain queue or wait 100ms
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield f"data: {json.dumps(item)}\n\n"
            except asyncio.TimeoutError:
                if future.done():
                    chunks_created = future.result()
                    break

        logger.info("Upload done: subject=%s file=%s chunks=%d", subject_id, filename, chunks_created)
        yield f"data: {json.dumps({'done': True, 'chunks': chunks_created, 'filename': filename})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/subjects/{subject_id}/files/{filename}", status_code=204)
def delete_file(subject_id: str, filename: str):
    try:
        from src.rag import delete_file as _delete
        _delete(subject_id, filename)
        logger.info("Deleted file: subject=%s file=%s", subject_id, filename)
    except Exception as e:
        logger.error("Delete file failed: subject=%s file=%s error=%s", subject_id, filename, e)
        raise HTTPException(500, detail=str(e))


@router.put("/subjects/{subject_id}/files/{filename}/type")
def update_file_type(subject_id: str, filename: str, body: FileTypeUpdate):
    from src.subjects import set_file_type
    set_file_type(subject_id, filename, body.file_type)
    return {"ok": True}


