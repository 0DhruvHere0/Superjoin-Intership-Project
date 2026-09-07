from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Optional
from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from app.config import settings
from app.db import repositories
from app.models.schemas import UploadResponse
from app.pipeline.processor import process_document
router = APIRouter(
    tags=["upload"],
)
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
def _remove_file(path: Optional[Path]) -> None:
    if path is not None and path.exists():
        path.unlink()
@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=202,
)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A filename is required.",
        )
    original_filename = Path(file.filename).name
    if Path(original_filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )
    upload_directory = Path(settings.upload_dir)
    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    temporary_path = upload_directory / (
        f".{uuid4()}.part"
    )
    file_hash = hashlib.sha256()
    bytes_written = 0
    try:
        with temporary_path.open("wb") as output_file:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                output_file.write(chunk)
                file_hash.update(chunk)
                bytes_written += len(chunk)
        if bytes_written == 0:
            _remove_file(temporary_path)
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )
        calculated_hash = file_hash.hexdigest()
        existing_document = (
            repositories.get_document_by_hash(
                calculated_hash
            )
        )
        if existing_document is not None:
            _remove_file(temporary_path)
            return UploadResponse(
                document_id=existing_document["id"],
                status=existing_document["status"],
                duplicate=True,
            )
        document_id = str(uuid4())
        final_path = upload_directory / (
            f"{document_id}.pdf"
        )
        temporary_path.replace(final_path)
        repositories.create_document(
            document_id=document_id,
            filename=original_filename,
            storage_path=str(final_path),
            file_hash=calculated_hash,
            uploaded_at=_now_iso(),
            status="queued",
        )
        background_tasks.add_task(
            process_document,
            document_id,
            final_path,
        )
        return UploadResponse(
            document_id=document_id,
            status="queued",
            duplicate=False,
        )
    except HTTPException:
        raise
    except Exception as error:
        _remove_file(temporary_path)
        raise HTTPException(
            status_code=500,
            detail=f"Could not store the uploaded PDF: {error}",
        ) from error