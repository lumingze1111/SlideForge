# LLM Output Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize LLM invocation, JSON extraction, Pydantic validation, retry behavior, and lightweight telemetry so SlideForge agents stop hand-parsing model responses.

**Architecture:** Add `slideforge/llm/` with a small protocol helper that wraps existing LangChain chat models. Start with JSON extraction and structured model validation, then migrate one existing agent at a time without changing prompts or public data models.

**Tech Stack:** Python 3.11, Pydantic v2, LangChain message objects, existing `BaseChatModel`, pytest with fake LLM responses.

---

## File Map

- Create `slideforge/llm/__init__.py`: public exports for the LLM protocol helpers.
- Create `slideforge/llm/json_protocol.py`: JSON extraction, validation, retries, and metadata.
- Modify `slideforge/agents/html_generator.py`: use the protocol for `PresentationOutline`.
- Modify `slideforge/agents/fact_checker.py`: use the protocol for fact-check result parsing if it currently parses JSON manually.
- Modify `slideforge/agents/speaker_notes.py`: use the protocol for plain text invoke metadata if it does not need JSON.
- Create `tests/test_llm_json_protocol.py`: unit tests for extraction, validation, and retry behavior.
- Create or modify `tests/test_html_generator_protocol.py`: verifies `generate_outline()` uses protocol behavior with a fake LLM.

## Task 1: Add JSON Extraction Helper

**Files:**
- Create: `slideforge/llm/__init__.py`
- Create: `slideforge/llm/json_protocol.py`
- Test: `tests/test_llm_json_protocol.py`

- [ ] **Step 1: Write failing JSON extraction tests**

Create `tests/test_llm_json_protocol.py`:

```python
import pytest

from slideforge.llm.json_protocol import JsonExtractionError, extract_json_text


def test_extract_json_text_accepts_plain_object():
    text = '{"name": "demo", "count": 2}'

    assert extract_json_text(text) == '{"name": "demo", "count": 2}'


def test_extract_json_text_accepts_json_code_block():
    text = 'Here is the result:\\n```json\\n{"name": "demo"}\\n```'

    assert extract_json_text(text) == '{"name": "demo"}'


def test_extract_json_text_finds_first_object_inside_extra_text():
    text = 'prefix {"name": "demo", "items": [1, 2, 3]} suffix'

    assert extract_json_text(text) == '{"name": "demo", "items": [1, 2, 3]}'


def test_extract_json_text_raises_for_missing_object():
    with pytest.raises(JsonExtractionError):
        extract_json_text("no structured data here")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_llm_json_protocol.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'slideforge.llm'`.

- [ ] **Step 3: Implement JSON extraction**

Create `slideforge/llm/__init__.py`:

```python
"""LLM protocol helpers used by SlideForge agents."""

from slideforge.llm.json_protocol import JsonExtractionError, extract_json_text

__all__ = ["JsonExtractionError", "extract_json_text"]
```

Create `slideforge/llm/json_protocol.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
./venv/bin/python -m pytest tests/test_llm_json_protocol.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add slideforge/llm tests/test_llm_json_protocol.py
git commit -m "feat: add shared llm json extraction"
```

## Task 2: Add Pydantic Validation and Retry

**Files:**
- Modify: `slideforge/llm/__init__.py`
- Modify: `slideforge/llm/json_protocol.py`
- Test: `tests/test_llm_json_protocol.py`

- [ ] **Step 1: Append failing validation tests**

Append to `tests/test_llm_json_protocol.py`:

```python
from pydantic import BaseModel

from slideforge.llm.json_protocol import invoke_json_model


class DemoModel(BaseModel):
    name: str
    count: int


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return FakeMessage(self.responses.pop(0))


def test_invoke_json_model_validates_pydantic_model():
    llm = FakeLLM(['{"name": "demo", "count": 2}'])

    result = invoke_json_model(
        llm,
        messages=["prompt"],
        schema=DemoModel,
        retry_prompt="Return valid JSON.",
    )

    assert result.value == DemoModel(name="demo", count=2)
    assert result.attempts == 1


def test_invoke_json_model_retries_after_invalid_json():
    llm = FakeLLM(["not json", '{"name": "demo", "count": 2}'])

    result = invoke_json_model(
        llm,
        messages=["prompt"],
        schema=DemoModel,
        retry_prompt="Return valid JSON.",
        max_attempts=2,
    )

    assert result.value.count == 2
    assert result.attempts == 2
    assert len(llm.calls) == 2
    assert "Return valid JSON." in llm.calls[1][-1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_llm_json_protocol.py -q
```

Expected: FAIL with `ImportError: cannot import name 'invoke_json_model'`.

- [ ] **Step 3: Implement validation and retry**

Modify `slideforge/llm/json_protocol.py`:

```python
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
```

Modify `slideforge/llm/__init__.py`:

```python
"""LLM protocol helpers used by SlideForge agents."""

from slideforge.llm.json_protocol import (
    JsonExtractionError,
    JsonModelResult,
    JsonProtocolError,
    extract_json_text,
    invoke_json_model,
)

__all__ = [
    "JsonExtractionError",
    "JsonModelResult",
    "JsonProtocolError",
    "extract_json_text",
    "invoke_json_model",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
./venv/bin/python -m pytest tests/test_llm_json_protocol.py -q
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add slideforge/llm tests/test_llm_json_protocol.py
git commit -m "feat: validate llm json responses"
```

## Task 3: Migrate Outline Generation to the Protocol

**Files:**
- Modify: `slideforge/agents/html_generator.py`
- Test: `tests/test_html_generator_protocol.py`

- [ ] **Step 1: Write failing outline retry test**

Create `tests/test_html_generator_protocol.py`:

```python
from slideforge.agents.html_generator import generate_outline


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return FakeMessage(self.responses.pop(0))


def test_generate_outline_retries_invalid_json_without_research(monkeypatch):
    monkeypatch.setattr(
        "slideforge.agents.html_generator.generate_speaker_notes",
        lambda llm, title, content, facts: f"notes for {title}",
        raising=False,
    )
    llm = FakeLLM([
        "not json",
        '{"total_pages": 1, "slides": [{"slide_type": "cover", "title": "标题", "subtitle": "副标题"}]}',
    ])

    outline = generate_outline(
        llm,
        topic="测试主题",
        audience="技术团队",
        pages=1,
        key_messages=None,
        research_facts=[],
    )

    assert outline.total_pages == 1
    assert outline.slides[0].title == "标题"
    assert outline.slides[0].notes == "notes for 标题"
    assert len(llm.calls) == 2
```

- [ ] **Step 2: Run test to verify current behavior fails**

Run:

```bash
./venv/bin/python -m pytest tests/test_html_generator_protocol.py -q
```

Expected: FAIL because current `generate_outline()` raises on the first invalid JSON response.

- [ ] **Step 3: Import and use `invoke_json_model` in `html_generator.py`**

Modify imports near the top of `slideforge/agents/html_generator.py`:

```python
from slideforge.llm.json_protocol import invoke_json_model
```

In `generate_outline()`, replace the manual response parsing block:

```python
    response = llm.invoke([
        SystemMessage(content="You are a presentation writer. Output valid JSON only."),
        HumanMessage(content=prompt),
    ])
    content = response.content
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    try:
        data = json.loads(content.strip())
    except json.JSONDecodeError:
        # 尝试从 content 中提取 JSON 对象
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(content[start:end])
        else:
            raise
    outline = PresentationOutline(**data)
```

with:

```python
    result = invoke_json_model(
        llm,
        messages=[
            SystemMessage(content="You are a presentation writer. Output valid JSON only."),
            HumanMessage(content=prompt),
        ],
        schema=PresentationOutline,
        retry_prompt=(
            "Return only valid JSON matching this shape: "
            '{"total_pages": number, "slides": [{"slide_type": "cover|section|content|two_column|data|closing", '
            '"title": "text", "subtitle": "text", "bullets": ["text"], "key_stat": "text", '
            '"key_stat_label": "text", "notes": "text"}]}'
        ),
        max_attempts=2,
    )
    outline = result.value
```

Also remove the unused `import json` at the top of `html_generator.py` if no other functions in that file use it.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_llm_json_protocol.py tests/test_html_generator_protocol.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 5: Run existing tests**

Run:

```bash
./venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add slideforge/agents/html_generator.py slideforge/llm tests/test_html_generator_protocol.py
git commit -m "refactor: use shared llm protocol for outline generation"
```

## Task 4: Add Plain Text Invoke Metadata for Non-JSON Agents

**Files:**
- Modify: `slideforge/llm/__init__.py`
- Modify: `slideforge/llm/json_protocol.py`
- Test: `tests/test_llm_json_protocol.py`

- [ ] **Step 1: Append failing plain text test**

Append to `tests/test_llm_json_protocol.py`:

```python
from slideforge.llm.json_protocol import invoke_text_model


def test_invoke_text_model_returns_content_and_attempt_metadata():
    llm = FakeLLM(["plain speaker notes"])

    result = invoke_text_model(llm, messages=["prompt"])

    assert result.content == "plain speaker notes"
    assert result.attempts == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./venv/bin/python -m pytest tests/test_llm_json_protocol.py::test_invoke_text_model_returns_content_and_attempt_metadata -q
```

Expected: FAIL with `ImportError: cannot import name 'invoke_text_model'`.

- [ ] **Step 3: Add text protocol helper**

Append to `slideforge/llm/json_protocol.py`:

```python
@dataclass(frozen=True)
class TextModelResult:
    content: str
    attempts: int


def invoke_text_model(llm: Any, messages: list[Any]) -> TextModelResult:
    response = llm.invoke(messages)
    return TextModelResult(content=str(getattr(response, "content", response)), attempts=1)
```

Modify `slideforge/llm/__init__.py`:

```python
"""LLM protocol helpers used by SlideForge agents."""

from slideforge.llm.json_protocol import (
    JsonExtractionError,
    JsonModelResult,
    JsonProtocolError,
    TextModelResult,
    extract_json_text,
    invoke_json_model,
    invoke_text_model,
)

__all__ = [
    "JsonExtractionError",
    "JsonModelResult",
    "JsonProtocolError",
    "TextModelResult",
    "extract_json_text",
    "invoke_json_model",
    "invoke_text_model",
]
```

- [ ] **Step 4: Run tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_llm_json_protocol.py -q
```

Expected: all protocol tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add slideforge/llm tests/test_llm_json_protocol.py
git commit -m "feat: add shared llm text invoke helper"
```

## Task 5: Migrate Speaker Notes to the Text Helper

**Files:**
- Modify: `slideforge/agents/speaker_notes.py`
- Test: `tests/test_speaker_notes_protocol.py`

- [ ] **Step 1: Inspect current function names**

Run:

```bash
sed -n '1,220p' slideforge/agents/speaker_notes.py
```

Expected: locate `generate_speaker_notes(llm, slide_title, content, research_facts)`.

- [ ] **Step 2: Write failing test for text helper usage**

Create `tests/test_speaker_notes_protocol.py`:

```python
from slideforge.agents.speaker_notes import generate_speaker_notes


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self):
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return FakeMessage("讲者备注内容")


def test_generate_speaker_notes_returns_text_content():
    llm = FakeLLM()

    notes = generate_speaker_notes(
        llm,
        slide_title="标题",
        content="正文内容",
        research_facts=["事实一"],
    )

    assert notes == "讲者备注内容"
    assert len(llm.calls) == 1
```

- [ ] **Step 3: Run test before migration**

Run:

```bash
./venv/bin/python -m pytest tests/test_speaker_notes_protocol.py -q
```

Expected: PASS before migration; this guards behavior while changing internals.

- [ ] **Step 4: Use `invoke_text_model` in `speaker_notes.py`**

Modify `slideforge/agents/speaker_notes.py` by importing:

```python
from slideforge.llm.json_protocol import invoke_text_model
```

Inside `generate_speaker_notes()`, replace:

```python
response = llm.invoke([...])
return response.content.strip()
```

with:

```python
result = invoke_text_model(llm, messages=[...])
return result.content.strip()
```

Keep the exact existing `SystemMessage` and `HumanMessage` content.

- [ ] **Step 5: Run tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_llm_json_protocol.py tests/test_speaker_notes_protocol.py tests/test_html_generator_protocol.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add slideforge/agents/speaker_notes.py tests/test_speaker_notes_protocol.py
git commit -m "refactor: use shared llm protocol for speaker notes"
```

## Self-Review

- Spec coverage: This plan covers priority 2 by creating a shared JSON/text protocol and migrating outline generation plus speaker notes as the first low-risk agent integrations.
- Placeholder scan: All implementation steps include concrete code or an exact inspection command with expected target.
- Type consistency: `JsonModelResult`, `TextModelResult`, `invoke_json_model`, and `invoke_text_model` are defined before migration tasks use them.
