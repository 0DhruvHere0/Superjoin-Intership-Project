from pathlib import Path
from typing import List
from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import HTTPException
from fastapi import status
from app.db import repositories
from app.models.schemas import DocumentDetailResponse
from app.models.schemas import DocumentResponse
from app.pipeline.processor import process_document
router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)
@router.get(
    "",
    response_model=List[DocumentResponse],
)
def list_documents() -> List[DocumentResponse]:
    return repositories.list_documents()
@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
def get_document(
    document_id: str,
) -> DocumentDetailResponse:
    document = repositories.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    facts = repositories.list_facts_by_document(
        document_id
    )
    relations = repositories.list_relations_by_document(
        document_id
    )
    issues = repositories.list_issues_by_document(
        document_id
    )
    return DocumentDetailResponse(
        **document,
        facts=facts,
        relations=relations,
        issues=issues,
    )
@router.post(
    "/{document_id}/reprocess",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
) -> DocumentResponse:
    document = repositories.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    if document["status"] == "extracting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is already being processed.",
        )
    storage_path = Path(
        document["storage_path"]
    )
    if not storage_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored PDF file no longer exists.",
        )
    repositories.reset_document_for_reprocessing(
        document_id
    )
    background_tasks.add_task(
        process_document,
        document_id,
        storage_path,
    )
    updated_document = repositories.get_document(
        document_id
    )
    return updated_document