from functools import lru_cache
from typing import Any, Dict, Literal
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from app.config import settings
from app.pipeline.rate_limiter import (
    run_with_gemini_retry,
)
RelationshipType = Literal[
    "corroborate",
    "contradict",
    "reconcile",
    "unrelated",
]
class RelationshipJudgment(BaseModel):
    relationship: RelationshipType
    explanation: str = Field(min_length=1)
class JudgeError(Exception):
    pass
RELATIONSHIP_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "relationship": {
            "type": "string",
            "enum": [
                "corroborate",
                "contradict",
                "reconcile",
                "unrelated",
            ],
        },
        "explanation": {
            "type": "string",
        },
    },
    "required": [
        "relationship",
        "explanation",
    ],
}
@lru_cache(maxsize=1)
def _get_gemini_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise JudgeError(
            "GEMINI_API_KEY is not configured."
        )
    return genai.Client(
        api_key=settings.gemini_api_key,
    )
def _format_fact(
    label: str,
    fact: Dict[str, Any],
) -> str:
    source_name = (
        fact.get("filename")
        or fact.get("source_document")
        or fact.get("doc_id")
        or "unknown document"
    )
    return f"""
{label}
Source document: {source_name}
Subject: {fact.get("subject", "")}
Predicate: {fact.get("predicate", "")}
Value: {fact.get("value", "")}
Unit: {fact.get("unit") or "not specified"}
Time scope: {fact.get("time_scope") or "not specified"}
Raw statement: {fact.get("raw_statement", "")}
Evidence quote: {fact.get("quote", "")}
""".strip()
def _build_judge_prompt(
    fact_a: Dict[str, Any],
    fact_b: Dict[str, Any],
    similarity: float,
) -> str:
    return f"""
Compare two extracted facts from PDF documents.
Embedding similarity: {similarity:.4f}
Classify the relationship as exactly one of:
corroborate:
The facts describe the same underlying claim and contain compatible information.
contradict:
The facts describe the same context but contain genuinely incompatible information.
reconcile:
The facts appear different, but the difference is explained by time, scope, unit,
estimate versus actual, subset versus total, or another explicit qualifier.
unrelated:
The facts are not actually about the same claim.
Rules:
1. Use only the information provided below.
2. Do not use outside knowledge.
3. Pay attention to subject, predicate, value, unit, and time scope.
4. The explanation must mention the specific values or context.
5. Different numbers do not automatically mean contradiction.
6. Similar words do not automatically mean corroboration.
FACT A:
{_format_fact("FACT A", fact_a)}
FACT B:
{_format_fact("FACT B", fact_b)}
""".strip()
def judge_relationship(
    fact_a: Dict[str, Any],
    fact_b: Dict[str, Any],
    similarity: float,
) -> RelationshipJudgment:
    if not settings.gemini_model:
        raise JudgeError(
            "GEMINI_MODEL is not configured."
        )
    prompt = _build_judge_prompt(
        fact_a=fact_a,
        fact_b=fact_b,
        similarity=similarity,
    )
    client = _get_gemini_client()
    def generate_response():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=RELATIONSHIP_JSON_SCHEMA,
            ),
        )
    try:
        response = run_with_gemini_retry(
            generate_response
        )
        if not response.text:
            raise JudgeError(
                "Gemini returned an empty relationship judgment."
            )
        return RelationshipJudgment.model_validate_json(
            response.text
        )
    except JudgeError:
        raise
    except ValidationError as error:
        raise JudgeError(
            f"Gemini returned invalid relationship data: {error}"
        ) from error
    except Exception as error:
        raise JudgeError(
            f"Gemini relationship judgment failed: {error}"
        ) from error