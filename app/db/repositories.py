from contextlib import contextmanager
import sqlite3
from typing import Any, Dict, Iterator, List, Optional
from app.db.database import get_connection
@contextmanager
def _managed_connection() -> Iterator[sqlite3.Connection]:
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)
def _rows_to_dicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]
def create_document(
    document_id: str,
    filename: str,
    storage_path: str,
    file_hash: str,
    uploaded_at: str,
    status: str = "queued",
) -> str:
    query = """
        INSERT INTO documents (
            id,
            filename,
            storage_path,
            file_hash,
            uploaded_at,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """
    with _managed_connection() as connection:
        connection.execute(
            query,
            (
                document_id,
                filename,
                storage_path,
                file_hash,
                uploaded_at,
                status,
            ),
        )
    return document_id
def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    query = """
        SELECT *
        FROM documents
        WHERE id = ?
    """
    with _managed_connection() as connection:
        row = connection.execute(query, (document_id,)).fetchone()
    return _row_to_dict(row)
def get_document_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    query = """
        SELECT *
        FROM documents
        WHERE file_hash = ?
    """
    with _managed_connection() as connection:
        row = connection.execute(query, (file_hash,)).fetchone()
    return _row_to_dict(row)
def list_documents() -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM documents
        ORDER BY uploaded_at DESC
    """
    with _managed_connection() as connection:
        rows = connection.execute(query).fetchall()
    return _rows_to_dicts(rows)
def update_document_status(
    document_id: str,
    status: str,
    num_pages: Optional[int] = None,
) -> None:
    if num_pages is None:
        query = """
            UPDATE documents
            SET status = ?
            WHERE id = ?
        """
        parameters = (status, document_id)
    else:
        query = """
            UPDATE documents
            SET status = ?, num_pages = ?
            WHERE id = ?
        """
        parameters = (status, num_pages, document_id)
    with _managed_connection() as connection:
        connection.execute(query, parameters)
def create_fact(
    fact_id: str,
    doc_id: str,
    page_start: int,
    page_end: int,
    quote: str,
    subject: str,
    predicate: str,
    value: str,
    unit: Optional[str],
    time_scope: Optional[str],
    raw_statement: str,
    confidence: float,
    embed_key: str,
    embedding: bytes,
    created_at: str,
) -> str:
    query = """
        INSERT INTO facts (
            id,
            doc_id,
            page_start,
            page_end,
            quote,
            subject,
            predicate,
            value,
            unit,
            time_scope,
            raw_statement,
            confidence,
            embed_key,
            embedding,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with _managed_connection() as connection:
        connection.execute(
            query,
            (
                fact_id,
                doc_id,
                page_start,
                page_end,
                quote,
                subject,
                predicate,
                value,
                unit,
                time_scope,
                raw_statement,
                confidence,
                embed_key,
                embedding,
                created_at,
            ),
        )
    return fact_id
def get_fact(fact_id: str) -> Optional[Dict[str, Any]]:
    query = """
        SELECT *
        FROM facts
        WHERE id = ?
    """
    with _managed_connection() as connection:
        row = connection.execute(query, (fact_id,)).fetchone()
    return _row_to_dict(row)
def list_facts_by_document(doc_id: str) -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM facts
        WHERE doc_id = ?
        ORDER BY page_start, created_at
    """
    with _managed_connection() as connection:
        rows = connection.execute(query, (doc_id,)).fetchall()
    return _rows_to_dicts(rows)
def list_all_facts() -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM facts
        ORDER BY created_at
    """
    with _managed_connection() as connection:
        rows = connection.execute(query).fetchall()

    return _rows_to_dicts(rows)
def create_relation(
    relation_id: str,
    fact_a_id: str,
    fact_b_id: str,
    relationship: str,
    explanation: str,
    similarity: float,
    created_at: str,
) -> str:
    query = """
        INSERT INTO relations (
            id,
            fact_a_id,
            fact_b_id,
            relationship,
            explanation,
            similarity,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with _managed_connection() as connection:
        connection.execute(
            query,
            (
                relation_id,
                fact_a_id,
                fact_b_id,
                relationship,
                explanation,
                similarity,
                created_at,
            ),
        )
    return relation_id
def find_relation_between_facts(
    fact_a_id: str,
    fact_b_id: str,
) -> Optional[Dict[str, Any]]:
    query = """
        SELECT *
        FROM relations
        WHERE
            (fact_a_id = ? AND fact_b_id = ?)
            OR
            (fact_a_id = ? AND fact_b_id = ?)
        LIMIT 1
    """
    with _managed_connection() as connection:
        row = connection.execute(
            query,
            (fact_a_id, fact_b_id, fact_b_id, fact_a_id),
        ).fetchone()
    return _row_to_dict(row)
def list_relations_by_document(
    doc_id: str,
) -> List[Dict[str, Any]]:
    query = """
        SELECT
            relations.*,
            fact_a.doc_id AS fact_a_doc_id,
            fact_b.doc_id AS fact_b_doc_id
        FROM relations
        JOIN facts AS fact_a
            ON relations.fact_a_id = fact_a.id
        JOIN facts AS fact_b
            ON relations.fact_b_id = fact_b.id
        WHERE fact_a.doc_id = ?
           OR fact_b.doc_id = ?
        ORDER BY relations.created_at
    """
    with _managed_connection() as connection:
        rows = connection.execute(query, (doc_id, doc_id)).fetchall()

    return _rows_to_dicts(rows)
def create_extraction_issue(
    issue_id: str,
    doc_id: str,
    page: Optional[int],
    issue_type: str,
    detail: str,
    created_at: str,
) -> str:
    query = """
        INSERT INTO extraction_issues (
            id,
            doc_id,
            page,
            issue_type,
            detail,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """
    with _managed_connection() as connection:
        connection.execute(
            query,
            (
                issue_id,
                doc_id,
                page,
                issue_type,
                detail,
                created_at,
            ),
        )
    return issue_id
def list_issues_by_document(
    doc_id: str,
) -> List[Dict[str, Any]]:
    """
    Retrieve all processing issues for a document.
    """
    query = """
        SELECT *
        FROM extraction_issues
        WHERE doc_id = ?
        ORDER BY created_at
    """
    with _managed_connection() as connection:
        rows = connection.execute(query, (doc_id,)).fetchall()
    return _rows_to_dicts(rows)