from functools import lru_cache
from typing import Any, Dict, Literal
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from app.config import settings
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
    """
    Raised when relationship judging fails.
    """
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
        api_key=settings.gemini_api_key
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
You are comparing two extracted facts from documents.
The embedding similarity between them is {similarity:.4f}.
Similarity only means they may be related. It is not the final decision.
Classify the pair using exactly one relationship:
- corroborate:
  The facts describe the same underlying claim and have
  compatible values.
- contradict:
  The facts describe the same relevant context but contain
  genuinely incompatible values.
- reconcile:
  The values appear different, but the difference is explained
  by context such as time period, scope, unit, estimate versus
  actual, subset versus total, or another explicit qualifier.
- unrelated:
  The facts are not actually about the same claim.
Rules:
1. Use only the information provided in the two facts.
2. Do not use outside knowledge.
3. Pay attention to subject, predicate, value, unit, and time scope.
4. The explanation is mandatory.
5. The explanation must reference the specific values or context
   that led to the decision.
6. Do not classify facts as contradicting merely because their
   numbers differ if their time periods or scopes differ.
7. Do not classify facts as corroborating merely because they use
   similar words.
Fact A:
{_format_fact("FACT A", fact_a)}
Fact B:
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
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_json_schema=RELATIONSHIP_JSON_SCHEMA,
            ),
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
            f"Relationship judgment failed: {error}"
        ) from error