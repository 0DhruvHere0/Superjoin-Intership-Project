from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.db import repositories
from app.models.schemas import FactResponse
router = APIRouter(
    prefix="/facts",
    tags=["facts"],
)
@router.get(
    "",
    response_model=List[FactResponse],
)
def list_facts(
    document_id: Optional[str] = Query(
        default=None
    ),
) -> List[FactResponse]:
    if document_id is None:
        return repositories.list_all_facts()
    document = repositories.get_document(
        document_id
    )
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )
    return repositories.list_facts_by_document(
        document_id
    )
@router.get(
    "/{fact_id}",
    response_model=FactResponse,
)
def get_fact(fact_id: str) -> FactResponse:
    fact = repositories.get_fact(fact_id)

    if fact is None:
        raise HTTPException(
            status_code=404,
            detail="Fact not found.",
        )
    return fact