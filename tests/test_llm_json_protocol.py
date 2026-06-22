import pytest

from slideforge.llm.json_protocol import JsonExtractionError, extract_json_text


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
