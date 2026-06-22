"""Shared helpers for model JSON output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError


class JsonExtractionError(ValueError):
    """Raised when a model response does not contain a JSON object."""


class JsonProtocolError(RuntimeError):
    """Raised when all attempts to obtain valid model JSON fail."""


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class JsonModelResult:
    value: BaseModel
    attempts: int
    raw_content: str


def extract_json_text(content: str) -> str:
    text = (content or "").strip()
    if not text:
        raise JsonExtractionError("model response is empty")

    fenced = _FENCED_JSON_RE.search(text)
    if fenced:
        return fenced.group(1).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    if start == -1:
        raise JsonExtractionError("model response does not contain a JSON object")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1].strip()

    raise JsonExtractionError("model response contains an incomplete JSON object")


def invoke_json_model(
    llm: Any,
    messages: list[Any],
    schema: type[T],
    retry_prompt: str,
    max_attempts: int = 2,
) -> JsonModelResult:
    last_error: Exception | None = None
    current_messages = list(messages)

    for attempt in range(1, max_attempts + 1):
        response = llm.invoke(current_messages)
        raw_content = str(getattr(response, "content", response))
        try:
            json_text = extract_json_text(raw_content)
            payload = json.loads(json_text)
            return JsonModelResult(
                value=schema.model_validate(payload),
                attempts=attempt,
                raw_content=raw_content,
            )
        except (JsonExtractionError, json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            current_messages = list(messages) + [
                f"{retry_prompt}\nPrevious error: {exc}",
            ]

    raise JsonProtocolError(f"Failed to produce valid {schema.__name__}: {last_error}")
