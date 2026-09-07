from typing import List, Literal, Optional
from pydantic import BaseModel, Field
DocumentStatus = Literal[
    "queued",
    "extracting",
    "done",
    "error",
]
RelationshipType = Literal[
    "corroborate",
    "contradict",
    "reconcile",
    "unrelated",
]
class UploadResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    duplicate: bool = False
class DocumentResponse(BaseModel):
    id: str
    filename: str
    uploaded_at: str
    num_pages: Optional[int] = None
    status: DocumentStatus
class FactResponse(BaseModel):
    id: str
    doc_id: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    quote: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: Optional[str] = None
    time_scope: Optional[str] = None
    raw_statement: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
class RelationResponse(BaseModel):
    id: str
    fact_a_id: str
    fact_b_id: str
    relationship: RelationshipType
    explanation: str = Field(min_length=1)
    similarity: float = Field(ge=-1.0, le=1.0)
    created_at: str
class ExtractionIssueResponse(BaseModel):
    id: str
    doc_id: str
    page: Optional[int] = None
    issue_type: str
    detail: str
    created_at: str
class DocumentDetailResponse(DocumentResponse):
    facts: List[FactResponse] = Field(default_factory=list)
    relations: List[RelationResponse] = Field(default_factory=list)
    issues: List[ExtractionIssueResponse] = Field(default_factory=list)