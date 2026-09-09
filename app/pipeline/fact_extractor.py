from functools import lru_cache
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from app.config import settings
from app.pipeline.chunker import TextChunk
from app.pipeline.rate_limiter import (
    run_with_gemini_retry,
)
MAX_FACTS_PER_CHUNK = 6
class ExtractedFact(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: Optional[str] = None
    time_scope: Optional[str] = None
    raw_statement: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
class FactExtractionResponse(BaseModel):
    facts: List[ExtractedFact]
class FactExtractionError(Exception):
    pass
FACT_EXTRACTION_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                    },
                    "predicate": {
                        "type": "string",
                    },
                    "value": {
                        "type": "string",
                    },
                    "unit": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "time_scope": {
                        "type": [
                            "string",
                            "null",
                        ],
                    },
                    "raw_statement": {
                        "type": "string",
                    },
                    "quote": {
                        "type": "string",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
                "required": [
                    "subject",
                    "predicate",
                    "value",
                    "raw_statement",
                    "quote",
                    "confidence",
                ],
            },
        },
    },
    "required": [
        "facts",
    ],
}
@lru_cache(maxsize=1)
def _get_gemini_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise FactExtractionError(
            "GEMINI_API_KEY is not configured."
        )
    return genai.Client(
        api_key=settings.gemini_api_key,
    )
def _build_extraction_prompt(
    chunk: TextChunk,
) -> str:
    return f"""
Extract up to {MAX_FACTS_PER_CHUNK} atomic facts from this PDF text.
The text comes from pages {chunk.page_start} to {chunk.page_end}.
Rules:
1. Extract only facts directly supported by the text.
2. Do not use outside knowledge.
3. Extract no more than {MAX_FACTS_PER_CHUNK} facts.
4. Each fact must contain one main claim.
5. Preserve numbers, dates, and units.
6. Use null when unit or time scope is not stated.
7. The quote must be copied exactly from the text.
8. Keep raw_statement short.
9. Confidence must be between 0 and 1.
10. Return an empty facts list if there are no meaningful facts.
PDF text:
{chunk.text}
""".strip()
def extract_facts_from_chunk(
    chunk: TextChunk,
) -> List[ExtractedFact]:
    if not chunk.text.strip():
        return []
    if not settings.gemini_model:
        raise FactExtractionError(
            "GEMINI_MODEL is not configured."
        )
    prompt = _build_extraction_prompt(chunk)
    client = _get_gemini_client()
    def generate_response():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=FACT_EXTRACTION_JSON_SCHEMA,
            ),
        )
    try:
        response = run_with_gemini_retry(
            generate_response
        )
        if not response.text:
            raise FactExtractionError(
                "Gemini returned an empty fact extraction response."
            )
        extraction_response = (
            FactExtractionResponse.model_validate_json(
                response.text
            )
        )
        return extraction_response.facts[
            :MAX_FACTS_PER_CHUNK
        ]
    except FactExtractionError:
        raise
    except ValidationError as error:
        raise FactExtractionError(
            f"Gemini returned invalid fact data: {error}"
        ) from error
    except Exception as error:
        raise FactExtractionError(
            f"Gemini fact extraction failed: {error}"
        ) from error