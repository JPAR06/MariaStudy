import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, Form
from fastapi.responses import FileResponse, StreamingResponse

from api.schemas import FileTypeUpdate
from src.config import UPLOADS_DIR

router = APIRouter()
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
    filename = file.filename or "upload.pdf"

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

        yield f"data: {json.dumps({'done': True, 'chunks': chunks_created, 'filename': filename})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/subjects/{subject_id}/files/{filename}", status_code=204)
def delete_file(subject_id: str, filename: str):
    from src.rag import delete_file as _delete
    _delete(subject_id, filename)


@router.put("/subjects/{subject_id}/files/{filename}/type")
def update_file_type(subject_id: str, filename: str, body: FileTypeUpdate):
    from src.subjects import set_file_type
    set_file_type(subject_id, filename, body.file_type)
    return {"ok": True}


@router.get("/files/{subject_id}/{filename}")
def serve_file(subject_id: str, filename: str):
    """Serve raw uploaded file (used by PDF viewer)."""
    path = Path(UPLOADS_DIR) / subject_id / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
    return FileResponse(str(path), media_type=media_type, filename=filename)
