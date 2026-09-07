from functools import lru_cache
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from app.config import settings
from app.pipeline.chunker import TextChunk
class ExtractedFact(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: Optional[str] = None
    time_scope: Optional[str] = None
    quote: str = Field(min_length=1)
    raw_statement: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
class FactExtractionResponse(BaseModel):
    facts: List[ExtractedFact] = Field(default_factory=list)
class FactExtractionError(Exception):
    """
    Raised when Gemini fact extraction fails.
    """
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
                        "type": "string",
                    },
                    "time_scope": {
                        "type": "string",
                    },
                    "quote": {
                        "type": "string",
                    },
                    "raw_statement": {
                        "type": "string",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                },
                "required": [
                    "subject",
                    "predicate",
                    "value",
                    "quote",
                    "raw_statement",
                    "confidence",
                ],
            },
        }
    },
    "required": ["facts"],
}
@lru_cache(maxsize=1)
def _get_gemini_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise FactExtractionError(
            "GEMINI_API_KEY is not configured."
        )
    return genai.Client(
        api_key=settings.gemini_api_key
    )
def _build_extraction_prompt(chunk: TextChunk) -> str:
    return f"""
You extract atomic, evidence-grounded facts from documents.

The document text below comes from pages
{chunk.page_start} through {chunk.page_end}.
Rules:
1. Extract only facts explicitly supported by the text.
2. Do not invent, infer, or speculate.
3. Break compound sentences into separate atomic facts.
4. Facts may be numerical or semantic.
5. Preserve important context such as dates, periods, scope,
   estimates, actual values, units, and ownership.
6. The quote must be copied exactly from the source text.
7. The value must be returned as text, even when it is numeric.
8. Use null for unit or time_scope when the source does not provide it.
9. Confidence must be a number between 0.0 and 1.0.
10. Return no fact when the text does not support a clear claim.
{chunk.text}
--- END SOURCE TEXT ---
""".strip()
def extract_facts_from_chunk(
    chunk: TextChunk,
) -> List[ExtractedFact]:
    if not settings.gemini_model:
        raise FactExtractionError(
            "GEMINI_MODEL is not configured."
        )
    prompt = _build_extraction_prompt(chunk)
    client = _get_gemini_client()
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_json_schema=FACT_EXTRACTION_JSON_SCHEMA,
            ),
        )
        if not response.text:
            raise FactExtractionError(
                "Gemini returned an empty response."
            )
        parsed_response = FactExtractionResponse.model_validate_json(
            response.text
        )
        return parsed_response.facts
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