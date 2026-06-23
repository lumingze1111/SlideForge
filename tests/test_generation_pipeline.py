from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from slideforge.agents.html_generator import PresentationOutline, SlideContent
from slideforge.agents.propose_agent import ColorProposal
from slideforge.pipeline.artifacts import GenerationArtifacts
from slideforge.pipeline.config import GenerationConfig
from slideforge.pipeline.generation import GenerationDependencies, GenerationPipeline


@dataclass
class Calls:
    html_with_images: int = 0
    html_plain: int = 0
    converted: int = 0
    picked_template: int = 0


def test_generation_pipeline_runs_core_flow_with_plain_html(tmp_path):
    calls = Calls()
    suggestion = SimpleNamespace(
        target_audience="技术团队",
        estimated_pages=2,
        key_messages=["清晰", "可靠"],
    )
    color = ColorProposal(
        name="测试蓝",
        colors={"primary": "#2563eb", "secondary": "#0f172a", "background": "#ffffff"},
        visual_style="corporate",
        reasoning="适合技术主题",
    )
    chosen_outline = SimpleNamespace(name="两页结构", slide_count=2)
    outline = PresentationOutline(
        total_pages=2,
        slides=[
            SlideContent(slide_type="cover", title="标题", subtitle="副标题"),
            SlideContent(slide_type="content", title="正文", bullets=["要点"]),
        ],
    )

    def fake_pick_template_family(topic, suggestion_arg, color_arg, outline_arg):
        calls.picked_template += 1
        assert topic == "测试主题"
        assert suggestion_arg is suggestion
        assert color_arg is color
        assert outline_arg is chosen_outline
        return "technical"

    def fake_generate_html(outline_arg, colors_arg, output_path, theme_family=""):
        calls.html_plain += 1
        assert theme_family == "technical"
        Path(output_path).write_text("<html></html>", encoding="utf-8")

    def fake_convert(html_path, pptx_path):
        calls.converted += 1
        Path(pptx_path).write_bytes(b"pptx")
        return 0

    deps = GenerationDependencies(
        analyze_topic=lambda llm, topic, ideas: suggestion,
        generate_color_proposals=lambda llm, topic, audience: SimpleNamespace(proposals=[color]),
        pick_color=lambda proposals, topic: color,
        generate_outline_proposals=lambda llm, topic, audience, pages: SimpleNamespace(proposals=[chosen_outline]),
        pick_outline=lambda proposals, topic: chosen_outline,
        pick_template_family=fake_pick_template_family,
        generate_outline=lambda llm, topic, audience, pages, key_messages, research_facts: outline,
        create_enhancement_agent=lambda **kwargs: None,
        generate_slides_html=fake_generate_html,
        generate_slides_html_with_images=lambda *args, **kwargs: calls.__setattr__("html_with_images", calls.html_with_images + 1),
        convert_html_to_pptx=fake_convert,
        open_file=lambda path: None,
        create_error_report=lambda **kwargs: None,
    )
    config = GenerationConfig(api_key="sk-test", enable_images=False, enable_charts=False)
    artifacts = GenerationArtifacts.for_topic(tmp_path, "测试主题")
    pipeline = GenerationPipeline(llm=object(), config=config, artifacts=artifacts, dependencies=deps)

    result = pipeline.run(topic="测试主题", ideas="")

    assert result.topic == "测试主题"
    assert result.color_name == "测试蓝"
    assert result.outline_name == "两页结构"
    assert result.html_path.exists()
    assert result.pptx_path.exists()
    assert calls.html_plain == 1
    assert calls.html_with_images == 0
    assert calls.converted == 1
    assert calls.picked_template == 1
    assert result.template_family == "technical"


def test_generation_pipeline_passes_template_family_to_media_html(tmp_path):
    calls = Calls()
    suggestion = SimpleNamespace(
        target_audience="技术团队",
        estimated_pages=2,
        key_messages=["清晰", "可靠"],
    )
    color = ColorProposal(
        name="测试蓝",
        colors={"primary": "#2563eb", "secondary": "#0f172a", "background": "#ffffff"},
        visual_style="corporate",
        reasoning="适合技术主题",
    )
    chosen_outline = SimpleNamespace(name="两页结构", slide_count=2)
    outline = PresentationOutline(
        total_pages=2,
        slides=[
            SlideContent(slide_type="cover", title="标题", subtitle="副标题"),
            SlideContent(slide_type="content", title="正文", bullets=["要点"]),
        ],
    )
    enhanced_outline = SimpleNamespace(images=[object()], charts=[object()])

    def fake_generate_html_with_images(outline_arg, colors_arg, images_arg, charts_arg, output_path, theme_family=""):
        calls.html_with_images += 1
        assert outline_arg is outline
        assert images_arg == enhanced_outline.images
        assert charts_arg == enhanced_outline.charts
        assert theme_family == "data"
        Path(output_path).write_text("<html></html>", encoding="utf-8")

    def fake_convert(html_path, pptx_path):
        calls.converted += 1
        Path(pptx_path).write_bytes(b"pptx")
        return 0

    deps = GenerationDependencies(
        analyze_topic=lambda llm, topic, ideas: suggestion,
        generate_color_proposals=lambda llm, topic, audience: SimpleNamespace(proposals=[color]),
        pick_color=lambda proposals, topic: color,
        generate_outline_proposals=lambda llm, topic, audience, pages: SimpleNamespace(proposals=[chosen_outline]),
        pick_outline=lambda proposals, topic: chosen_outline,
        pick_template_family=lambda topic, suggestion_arg, color_arg, outline_arg: "data",
        generate_outline=lambda llm, topic, audience, pages, key_messages, research_facts: outline,
        create_enhancement_agent=lambda **kwargs: SimpleNamespace(
            enhance_outline=lambda outline_arg, color_arg, topic: enhanced_outline
        ),
        generate_slides_html=lambda *args, **kwargs: calls.__setattr__("html_plain", calls.html_plain + 1),
        generate_slides_html_with_images=fake_generate_html_with_images,
        convert_html_to_pptx=fake_convert,
        open_file=lambda path: None,
        create_error_report=lambda **kwargs: None,
    )
    config = GenerationConfig(api_key="sk-test", enable_images=True, enable_charts=True)
    artifacts = GenerationArtifacts.for_topic(tmp_path, "测试主题")
    pipeline = GenerationPipeline(llm=object(), config=config, artifacts=artifacts, dependencies=deps)

    result = pipeline.run(topic="测试主题", ideas="")

    assert result.template_family == "data"
    assert result.image_count == 1
    assert result.chart_count == 1
    assert calls.html_plain == 0
    assert calls.html_with_images == 1
    assert calls.converted == 1
