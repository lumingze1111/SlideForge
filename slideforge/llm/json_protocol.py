"""Shared helpers for model JSON output."""

from __future__ import annotations

import re


class JsonExtractionError(ValueError):
    """Raised when a model response does not contain a JSON object."""


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


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
