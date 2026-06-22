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

    def fake_generate_html(outline_arg, colors_arg, output_path):
        calls.html_plain += 1
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
