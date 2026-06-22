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
        "slideforge.agents.speaker_notes.generate_speaker_notes",
        lambda llm, title, content, facts: f"notes for {title}",
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
