from dataclasses import dataclass
from functools import lru_cache
import json
from typing import List, Union
from google import genai
from app.config import settings
from app.pipeline.fact_extractor import ExtractedFact
class EmbeddingError(Exception):
    pass
@dataclass
class EmbeddingResult:
    embed_key: str
    vector: List[float]
@lru_cache(maxsize=1)
def _get_gemini_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise EmbeddingError(
            "GEMINI_API_KEY is not configured."
        )
    return genai.Client(
        api_key=settings.gemini_api_key
    )
def build_embedding_key(fact: ExtractedFact) -> str:
    subject = fact.subject.strip()
    predicate = fact.predicate.strip()
    time_scope = (fact.time_scope or "").strip()
    return " | ".join(
        [subject, predicate, time_scope]
    )
def generate_embedding(
    fact: ExtractedFact,
) -> EmbeddingResult:
    if not settings.gemini_embedding_model:
        raise EmbeddingError(
            "GEMINI_EMBEDDING_MODEL is not configured."
        )
    embed_key = build_embedding_key(fact)
    if not embed_key.strip():
        raise EmbeddingError(
            "Cannot create an embedding key from an empty fact."
        )
    client = _get_gemini_client()
    try:
        response = client.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=embed_key,
        )
        if not response.embeddings:
            raise EmbeddingError(
                "Gemini returned no embeddings."
            )
        values = response.embeddings[0].values
        if not values:
            raise EmbeddingError(
                "Gemini returned an empty embedding vector."
            )
        vector = [float(value) for value in values]
        return EmbeddingResult(
            embed_key=embed_key,
            vector=vector,
        )
    except EmbeddingError:
        raise
    except Exception as error:
        raise EmbeddingError(
            f"Embedding generation failed: {error}"
        ) from error
def serialize_embedding(
    vector: List[float],
) -> bytes:
    if not vector:
        raise ValueError(
            "Cannot serialize an empty embedding."
        )
    json_value = json.dumps(
        vector,
        allow_nan=False,
    )
    return json_value.encode("utf-8")
def deserialize_embedding(
    data: Union[bytes, str],
) -> List[float]:
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    values = json.loads(data)
    if not isinstance(values, list) or not values:
        raise ValueError(
            "Stored embedding is not a non-empty list."
        )
    return [float(value) for value in values]