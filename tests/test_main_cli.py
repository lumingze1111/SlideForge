from pathlib import Path
from types import SimpleNamespace

import main


def test_main_delegates_to_generation_pipeline(monkeypatch, tmp_path):
    calls = {}

    class FakePipeline:
        def __init__(self, llm, config, artifacts, dependencies):
            calls["config"] = config
            calls["artifacts"] = artifacts
            calls["dependencies"] = dependencies

        def run(self, topic, ideas=""):
            calls["topic"] = topic
            calls["ideas"] = ideas
            return SimpleNamespace(
                topic=topic,
                color_name="测试蓝",
                outline_name="两页结构",
                template_family="technical",
                html_path=tmp_path / "slides.html",
                pptx_path=tmp_path / "slides.pptx",
                image_count=0,
                chart_count=0,
            )

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("ENABLE_IMAGE_SEARCH", "false")
    monkeypatch.setenv("ENABLE_CHART_GENERATION", "false")
    monkeypatch.setattr(main, "ChatOpenAI", lambda **kwargs: object())
    monkeypatch.setattr(main, "GenerationPipeline", FakePipeline)
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main.sys, "argv", ["main.py", "测试主题", "测试想法"])

    main.main()

    assert calls["topic"] == "测试主题"
    assert calls["ideas"] == "测试想法"
    assert calls["config"].api_key == "sk-test"
    assert calls["artifacts"].output_dir == Path(tmp_path)
