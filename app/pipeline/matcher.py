from dataclasses import dataclass
from typing import Any, Dict, List, Sequence
import numpy as np
from app.pipeline.embedder import deserialize_embedding
@dataclass
class Candidate:
    fact: Dict[str, Any]
    similarity: float
def cosine_similarity(
    vector_a: Sequence[float],
    vector_b: Sequence[float],
) -> float:
    array_a = np.asarray(vector_a, dtype=float)
    array_b = np.asarray(vector_b, dtype=float)
    if array_a.ndim != 1 or array_b.ndim != 1:
        raise ValueError(
            "Embedding vectors must be one-dimensional."
        )
    if array_a.shape != array_b.shape:
        raise ValueError(
            "Embedding vectors must have the same dimensions."
        )
    norm_a = np.linalg.norm(array_a)
    norm_b = np.linalg.norm(array_b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    score = float(
        np.dot(array_a, array_b)
        / (norm_a * norm_b)
    )
    return max(-1.0, min(1.0, score))
def _normalise_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).lower().split())
def _is_near_duplicate(
    fact_a: Dict[str, Any],
    fact_b: Dict[str, Any],
) -> bool:
    if fact_a.get("doc_id") != fact_b.get("doc_id"):
        return False
    same_quote = (
        _normalise_text(fact_a.get("quote"))
        == _normalise_text(fact_b.get("quote"))
    )
    same_meaning = all(
        _normalise_text(fact_a.get(field))
        == _normalise_text(fact_b.get(field))
        for field in (
            "subject",
            "predicate",
            "value",
            "unit",
            "time_scope",
        )
    )
    return same_quote and same_meaning
def _read_embedding(
    raw_embedding: Any,
) -> List[float]:
    if isinstance(raw_embedding, (bytes, str)):
        return deserialize_embedding(raw_embedding)
    if isinstance(raw_embedding, list):
        return [float(value) for value in raw_embedding]
    raise ValueError(
        "Unsupported embedding format."
    )
def find_candidates(
    new_fact: Dict[str, Any],
    existing_facts: List[Dict[str, Any]],
    similarity_threshold: float = 0.72,
    top_k: int = 8,
) -> List[Candidate]:
    if not -1.0 <= similarity_threshold <= 1.0:
        raise ValueError(
            "similarity_threshold must be between -1.0 and 1.0."
        )
    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )
    new_fact_id = new_fact.get("id")
    new_embedding = _read_embedding(
        new_fact["embedding"]
    )
    candidates: List[Candidate] = []
    for existing_fact in existing_facts:
        if existing_fact.get("id") == new_fact_id:
            continue
        if _is_near_duplicate(
            new_fact,
            existing_fact,
        ):
            continue
        try:
            existing_embedding = _read_embedding(
                existing_fact["embedding"]
            )
            similarity = cosine_similarity(
                new_embedding,
                existing_embedding,
            )
        except (KeyError, TypeError, ValueError):
            continue
        if similarity >= similarity_threshold:
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