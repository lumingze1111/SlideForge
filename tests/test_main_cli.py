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


def test_media_html_dependency_accepts_template_family(monkeypatch, tmp_path):
    calls = {}

    def fake_generate_with_images(outline, colors, images, charts, output_path, theme_family=""):
        calls["theme_family"] = theme_family
        Path(output_path).write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr(main, "generate_slides_html_with_images", fake_generate_with_images)
    monkeypatch.setattr(main, "_open_file", lambda path: None)

    deps = main._create_dependencies(error_tracker=object())
    output_path = tmp_path / "slides.html"

    deps.generate_slides_html_with_images(
        object(),
        {},
        [],
        [],
        output_path=str(output_path),
        theme_family="data",
    )

    assert calls["theme_family"] == "data"
    assert output_path.exists()


def test_plain_html_dependency_accepts_template_family(monkeypatch, tmp_path):
    calls = {}

    def fake_generate_plain(outline, colors, output_path, theme_family=""):
        calls["theme_family"] = theme_family
        Path(output_path).write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr(main, "generate_slides_html", fake_generate_plain)
    monkeypatch.setattr(main, "_open_file", lambda path: None)

    deps = main._create_dependencies(error_tracker=object())
    output_path = tmp_path / "slides.html"

    deps.generate_slides_html(
        object(),
        {},
        output_path=str(output_path),
        theme_family="technical",
    )

    assert calls["theme_family"] == "technical"
    assert output_path.exists()


def test_convert_uses_screenshot_mode_by_default(monkeypatch, tmp_path):
    calls = {}

    def fake_convert(html_path, pptx_path, **kwargs):
        calls["convert"] = {
            "html_path": html_path,
            "pptx_path": pptx_path,
            "kwargs": kwargs,
        }
        Path(pptx_path).write_bytes(b"pptx")

    def fail_if_llm_direct_runs(*args, **kwargs):
        raise AssertionError("LLM direct conversion should not run in the default export path")

    monkeypatch.setattr(main.subprocess, "run", fail_if_llm_direct_runs)
    monkeypatch.setattr("slideforge.pptx_converter.convert_html_to_pptx", fake_convert)
    monkeypatch.setattr(main, "_open_file", lambda path: None)

    html_path = tmp_path / "slides.html"
    pptx_path = tmp_path / "slides.pptx"
    html_path.write_text("<html></html>", encoding="utf-8")

    deps = main._create_dependencies(error_tracker=object())
    result = deps.convert_html_to_pptx(str(html_path), str(pptx_path))

    assert result == 0
    assert calls["convert"]["html_path"] == str(html_path)
    assert calls["convert"]["pptx_path"] == str(pptx_path)
    assert calls["convert"]["kwargs"]["screenshot_mode"] is True
    assert calls["convert"]["kwargs"]["validate_gradients"] is False
