from typing import List
from fastapi import APIRouter, HTTPException
from app.db import repositories
from app.models.schemas import (
    DocumentDetailResponse,
    DocumentResponse,
)
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
def get_document_details(
    document_id: str,
) -> DocumentDetailResponse:
    document = repositories.get_document(
        document_id
    )
    if document is None:
        raise HTTPException(
            status_code=404,
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