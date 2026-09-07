from typing import List
from fastapi import APIRouter, HTTPException, Query
from app.db import repositories
from app.models.schemas import ExtractionIssueResponse
router = APIRouter(
    prefix="/issues",
    tags=["issues"],
)
@router.get(
    "",
    response_model=List[ExtractionIssueResponse],
)
def list_issues(
    document_id: str = Query(...),
) -> List[ExtractionIssueResponse]:
    document = repositories.get_document(
        document_id
    )
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )
    return repositories.list_issues_by_document(
        document_id
    )