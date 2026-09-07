from typing import List
from fastapi import APIRouter, HTTPException, Query
from app.db import repositories
from app.models.schemas import RelationResponse
router = APIRouter(
    prefix="/relations",
    tags=["relations"],
)
@router.get(
    "",
    response_model=List[RelationResponse],
)
def list_relations(
    document_id: str = Query(...),
) -> List[RelationResponse]:
    document = repositories.get_document(
        document_id
    )
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )
    return repositories.list_relations_by_document(
        document_id
    )