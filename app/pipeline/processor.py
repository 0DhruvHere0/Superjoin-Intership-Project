from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from uuid import uuid4
from app import config
from app.db import repositories
from app.pipeline.chunker import TextChunk, chunk_pages
from app.pipeline.embedder import (
    EmbeddingError,
    generate_embedding,
    serialize_embedding,
)
from app.pipeline.fact_extractor import (
    ExtractedFact,
    FactExtractionError,
    extract_facts_from_chunk,
)
from app.pipeline.judge import (
    JudgeError,
    judge_relationship,
)
from app.pipeline.matcher import find_candidates
from app.pipeline.pdf_extractor import (
    PDFExtractionError,
    extract_pdf_text,
)
@dataclass
class ProcessingSummary:
    document_id: str
    pages_processed: int = 0
    chunks_processed: int = 0
    facts_stored: int = 0
    relations_stored: int = 0
    issues_recorded: int = 0
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
def _record_issue(
    summary: ProcessingSummary,
    document_id: str,
    page: Optional[int],
    issue_type: str,
    detail: str,
) -> None:
    repositories.create_extraction_issue(
        issue_id=str(uuid4()),
        doc_id=document_id,
        page=page,
        issue_type=issue_type,
        detail=detail,
        created_at=_now_iso(),
    )
    summary.issues_recorded += 1
def _normalize_evidence_text(value: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\u200b": "",
    }
    for old_value, new_value in replacements.items():
        value = value.replace(old_value, new_value)
    return " ".join(value.split()).casefold().strip()
def _validate_fact_evidence(
    fact: ExtractedFact,
    chunk: TextChunk,
) -> bool:
    source_text = _normalize_evidence_text(chunk.text)
    quote_text = _normalize_evidence_text(fact.quote)
    quote_text = quote_text.strip("\"'")

    return bool(quote_text) and quote_text in source_text
def _store_fact_and_relationships(
    document_id: str,
    fact: ExtractedFact,
    chunk: TextChunk,
    summary: ProcessingSummary,
) -> None:
    try:
        _validate_fact_evidence(fact, chunk)
    except ValueError as error:
        _record_issue(
            summary=summary,
            document_id=document_id,
            page=chunk.page_start,
            issue_type="incomplete_fact",
            detail=str(error),
        )
        return
    try:
        embedding_result = generate_embedding(fact)
        serialized_embedding = serialize_embedding(
            embedding_result.vector
        )
    except EmbeddingError as error:
        _record_issue(
            summary=summary,
            document_id=document_id,
            page=chunk.page_start,
            issue_type="embedding_failed",
            detail=str(error),
        )
        return
    fact_id = str(uuid4())
    repositories.create_fact(
        fact_id=fact_id,
        doc_id=document_id,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        quote=fact.quote,
        subject=fact.subject,
        predicate=fact.predicate,
        value=fact.value,
        unit=fact.unit,
        time_scope=fact.time_scope,
        raw_statement=fact.raw_statement,
        confidence=fact.confidence,
        embed_key=embedding_result.embed_key,
        embedding=serialized_embedding,
        created_at=_now_iso(),
    )
    summary.facts_stored += 1
    stored_fact = repositories.get_fact(fact_id)
    if stored_fact is None:
        raise RuntimeError(
            f"Stored fact could not be retrieved: {fact_id}"
        )
    existing_facts = repositories.list_all_facts()
    candidates = find_candidates(
        new_fact=stored_fact,
        existing_facts=existing_facts,
        similarity_threshold=config.settings.similarity_threshold,
        top_k=config.settings.top_k,
    )
    for candidate in candidates:
        candidate_fact = candidate.fact
        existing_relation = (
            repositories.find_relation_between_facts(
                fact_a_id=fact_id,
                fact_b_id=candidate_fact["id"],
            )
        )
        if existing_relation is not None:
            continue
        try:
            judgment = judge_relationship(
                fact_a=stored_fact,
                fact_b=candidate_fact,
                similarity=candidate.similarity,
            )
        except JudgeError as error:
            _record_issue(
                summary=summary,
                document_id=document_id,
                page=chunk.page_start,
                issue_type="judge_call_failed",
                detail=str(error),
            )
            continue
        repositories.create_relation(
            relation_id=str(uuid4()),
            fact_a_id=fact_id,
            fact_b_id=candidate_fact["id"],
            relationship=judgment.relationship,
            explanation=judgment.explanation,
            similarity=candidate.similarity,
            created_at=_now_iso(),
        )
        summary.relations_stored += 1
def _process_chunk(
    document_id: str,
    chunk: TextChunk,
    summary: ProcessingSummary,
) -> None:
    try:
        facts = extract_facts_from_chunk(chunk)
    except FactExtractionError as error:
        _record_issue(
            summary=summary,
            document_id=document_id,
            page=chunk.page_start,
            issue_type="extraction_call_failed",
            detail=str(error),
        )
        return
    for fact in facts:
        _store_fact_and_relationships(
            document_id=document_id,
            fact=fact,
            chunk=chunk,
            summary=summary,
        )
def process_document(
    document_id: str,
    pdf_path: Union[str, Path],
) -> ProcessingSummary:
    summary = ProcessingSummary(
        document_id=document_id
    )
    repositories.update_document_status(
        document_id=document_id,
        status="extracting",
    )
    try:
        pages = extract_pdf_text(pdf_path)
        summary.pages_processed = len(pages)
        repositories.update_document_status(
            document_id=document_id,
            status="extracting",
            num_pages=len(pages),
        )
        chunks = chunk_pages(
            pages=pages,
            max_characters=config.settings.chunk_size,
        )
        summary.chunks_processed = len(chunks)
        if not chunks:
            _record_issue(
                summary=summary,
                document_id=document_id,
                page=None,
                issue_type="no_extractable_text",
                detail="The PDF produced no usable text chunks.",
            )
            repositories.update_document_status(
                document_id=document_id,
                status="error",
            )
            return summary
        for chunk in chunks:
            _process_chunk(
                document_id=document_id,
                chunk=chunk,
                summary=summary,
            )
        if summary.facts_stored == 0:
            _record_issue(
                summary=summary,
                document_id=document_id,
                page=None,
                issue_type="no_facts_extracted",
                detail=(
                    "Document processing completed, but no valid "
                    "facts were stored."
                ),
            )
            repositories.update_document_status(
                document_id=document_id,
                status="error",
            )
        else:
            repositories.update_document_status(
                document_id=document_id,
                status="done",
            )
        return summary
    except PDFExtractionError as error:
        _record_issue(
            summary=summary,
            document_id=document_id,
            page=None,
            issue_type="pdf_extraction_failed",
            detail=str(error),
        )
        repositories.update_document_status(
            document_id=document_id,
            status="error",
        )
        return summary
    except Exception as error:
        _record_issue(
            summary=summary,
            document_id=document_id,
            page=None,
            issue_type="unexpected_processing_error",
            detail=str(error),
        )
        repositories.update_document_status(
            document_id=document_id,
            status="error",
        )
        return summary