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
        title="标题",
        content="正文内容",
        facts=["事实一"],
    )

    assert notes == "讲者备注内容"
    assert len(llm.calls) == 1
