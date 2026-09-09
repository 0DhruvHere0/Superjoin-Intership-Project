from dataclasses import dataclass
from typing import Any, Dict, List
import numpy as np
from app.pipeline.embedder import deserialize_embedding
@dataclass
class Candidate:
    fact: Dict[str, Any]
    similarity: float
def _get_fact_value(
    fact: Dict[str, Any],
    field_name: str,
) -> Any:
    return fact.get(field_name)
def _document_id(
    fact: Dict[str, Any],
) -> Any:
    return (
        _get_fact_value(fact, "doc_id")
        or _get_fact_value(fact, "document_id")
    )
def _normalize_text(value: Any) -> str:
    return " ".join(
        str(value or "").casefold().split()
    )
def _same_document(
    fact_a: Dict[str, Any],
    fact_b: Dict[str, Any],
) -> bool:
    document_a = _document_id(fact_a)
    document_b = _document_id(fact_b)
    if not document_a or not document_b:
        return False
    return str(document_a) == str(document_b)
def _is_duplicate_fact(
    fact_a: Dict[str, Any],
    fact_b: Dict[str, Any],
) -> bool:
    return (
        _same_document(fact_a, fact_b)
        and _normalize_text(
            _get_fact_value(fact_a, "quote")
        )
        == _normalize_text(
            _get_fact_value(fact_b, "quote")
        )
        and _normalize_text(
            _get_fact_value(fact_a, "subject")
        )
        == _normalize_text(
            _get_fact_value(fact_b, "subject")
        )
        and _normalize_text(
            _get_fact_value(fact_a, "predicate")
        )
        == _normalize_text(
            _get_fact_value(fact_b, "predicate")
        )
        and _normalize_text(
            _get_fact_value(fact_a, "value")
        )
        == _normalize_text(
            _get_fact_value(fact_b, "value")
        )
    )
def cosine_similarity(
    vector_a: List[float],
    vector_b: List[float],
) -> float:
    array_a = np.array(vector_a, dtype=float)
    array_b = np.array(vector_b, dtype=float)
    norm_a = np.linalg.norm(array_a)
    norm_b = np.linalg.norm(array_b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(
        np.dot(array_a, array_b)
        / (norm_a * norm_b)
    )
def find_candidates(
    new_fact: Dict[str, Any],
    existing_facts: List[Dict[str, Any]],
    similarity_threshold: float = 0.72,
    top_k: int = 8,
) -> List[Candidate]:
    if top_k <= 0:
        return []
    new_embedding_data = new_fact.get("embedding")
    if not new_embedding_data:
        return []
    try:
        new_vector = deserialize_embedding(
            new_embedding_data
        )
    except Exception:
        return []
    candidates: List[Candidate] = []
    for existing_fact in existing_facts:
        if _same_document(new_fact, existing_fact):
            continue
        if _is_duplicate_fact(
            new_fact,
            existing_fact,
        ):
            continue
        existing_embedding_data = (
            existing_fact.get("embedding")
        )
        if not existing_embedding_data:
            continue
        try:
            existing_vector = deserialize_embedding(
                existing_embedding_data
            )
            similarity = cosine_similarity(
                new_vector,
                existing_vector,
            )
        except Exception:
            continue
        if similarity < similarity_threshold:
            continue
        candidates.append(
            Candidate(
                fact=existing_fact,
                similarity=similarity,
            )
        )
    candidates.sort(
        key=lambda candidate: candidate.similarity,
        reverse=True,
    )
    return candidates[:top_k]