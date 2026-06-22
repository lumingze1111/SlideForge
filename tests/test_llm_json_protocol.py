import pytest
from pydantic import BaseModel

from slideforge.llm.json_protocol import (
    JsonExtractionError,
    extract_json_text,
    invoke_json_model,
)


def test_extract_json_text_accepts_plain_object():
    text = '{"name": "demo", "count": 2}'

    assert extract_json_text(text) == '{"name": "demo", "count": 2}'


def test_extract_json_text_accepts_json_code_block():
    text = 'Here is the result:\n```json\n{"name": "demo"}\n```'

    assert extract_json_text(text) == '{"name": "demo"}'


def test_extract_json_text_finds_first_object_inside_extra_text():
    text = 'prefix {"name": "demo", "items": [1, 2, 3]} suffix'

    assert extract_json_text(text) == '{"name": "demo", "items": [1, 2, 3]}'


def test_extract_json_text_raises_for_missing_object():
    with pytest.raises(JsonExtractionError):
        extract_json_text("no structured data here")


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
