from functools import lru_cache
import time
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings
MAX_RETRIES = 3
RETRYABLE_STATUS_CODES = {
    429,
    500,
    502,
    503,
    504,
}
class LLMClientError(Exception):
    pass
@lru_cache(maxsize=1)
def _get_http_client() -> httpx.Client:
    if not settings.openrouter_api_key:
        raise LLMClientError(
            "OPENROUTER_API_KEY is not configured."
        )
    if not settings.openrouter_model:
        raise LLMClientError(
            "OPENROUTER_MODEL is not configured."
        )
    return httpx.Client(
        base_url=settings.openrouter_base_url.rstrip("/"),
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-OpenRouter-Title": "Fact Knowledge Layer",
        },
        timeout=120.0,
    )
def _extract_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return "".join(text_parts)
    return ""
def _response_details(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
def _retry_delay(
    response: Optional[httpx.Response],
    attempt: int,
) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass
        try:
            response_data = response.json()
        except ValueError:
            response_data = {}
        values: List[Any] = []
        if isinstance(response_data, dict):
            values.extend(
                [
                    response_data.get("retry_after"),
                    response_data.get("retryDelay"),
                ]
            )
            error_data = response_data.get("error")
            if isinstance(error_data, dict):
                values.extend(
                    [
                        error_data.get("retry_after"),
                        error_data.get("retryDelay"),
                    ]
                )
        for value in values:
            if value is not None:
                try:
                    return max(float(value), 0.0)
                except (TypeError, ValueError):
                    pass
    return min(5.0 * (2 ** attempt), 30.0)
def _is_temporary_payload(response_data: Any) -> bool:
    if not isinstance(response_data, dict):
        return False
    error_data = response_data.get("error")
    if isinstance(error_data, dict):
        source = error_data
    else:
        source = response_data
    message = str(source.get("message", "")).lower()
    code = str(source.get("code", ""))
    return (
        code in {"429", "500", "502", "503", "504"}
        or "temporarily overloaded" in message
        or "upstream error" in message
        or "temporarily unavailable" in message
    )
def generate_text(
    prompt: str,
    system_instruction: Optional[str] = None,
    max_tokens: int = 4096,
) -> str:
    if not prompt.strip():
        raise LLMClientError("The LLM prompt cannot be empty.")
    messages: List[Dict[str, str]] = []
    if system_instruction:
        messages.append(
            {
                "role": "system",
                "content": system_instruction,
            }
        )
    messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )
    payload = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "provider": {
            "sort": "throughput",
            "allow_fallbacks": True,
        },
    }
    client = _get_http_client()
    for attempt in range(MAX_RETRIES + 1):
        response: Optional[httpx.Response] = None
        try:
            response = client.post(
                "/chat/completions",
                json=payload,
            )
        except httpx.RequestError as error:
            if attempt >= MAX_RETRIES:
                raise LLMClientError(
                    f"Could not connect to OpenRouter: {error}"
                ) from error
            time.sleep(_retry_delay(None, attempt))
            continue
        if response.status_code in RETRYABLE_STATUS_CODES:
            if attempt >= MAX_RETRIES:
                raise LLMClientError(
                    f"OpenRouter returned HTTP "
                    f"{response.status_code}: "
                    f"{_response_details(response)}"
                )

            time.sleep(_retry_delay(response, attempt))
            continue
        if response.status_code >= 400:
            raise LLMClientError(
                f"OpenRouter returned HTTP "
                f"{response.status_code}: "
                f"{_response_details(response)}"
            )
        try:
            response_data = response.json()
        except ValueError as error:
            raise LLMClientError(
                "OpenRouter returned invalid JSON."
            ) from error
        if _is_temporary_payload(response_data):
            if attempt >= MAX_RETRIES:
                raise LLMClientError(
                    f"OpenRouter provider remained unavailable: "
                    f"{response_data}"
                )
            time.sleep(_retry_delay(response, attempt))
            continue
        break
    else:
        raise LLMClientError(
            "OpenRouter request failed after all retries."
        )
    if not isinstance(response_data, dict):
        raise LLMClientError(
            "OpenRouter returned an invalid response body."
        )
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        provider_error = response_data.get("error")
        if provider_error:
            raise LLMClientError(
                f"OpenRouter returned no choices: {provider_error}"
            )
        raise LLMClientError(
            f"OpenRouter returned no response choices: "
            f"{response_data}"
        )
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMClientError(
            "OpenRouter returned an invalid response choice."
        )
    finish_reason = first_choice.get("finish_reason")
    if finish_reason == "length":
        raise LLMClientError(
            "OpenRouter truncated the response because the "
            "maximum token limit was reached."
        )
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise LLMClientError(
            "OpenRouter response did not contain a message."
        )
    text = _extract_message_text(message.get("content"))
    if not text.strip():
        raise LLMClientError(
            "OpenRouter returned an empty response."
        )
    return text.strip()