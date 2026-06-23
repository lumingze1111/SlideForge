"""Reusable SlideForge generation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from slideforge.pipeline.artifacts import GenerationArtifacts
from slideforge.pipeline.config import GenerationConfig


@dataclass(frozen=True)
class GenerationResult:
    topic: str
    color_name: str
    outline_name: str
    template_family: str
    html_path: Path
    pptx_path: Path
    image_count: int = 0
    chart_count: int = 0


@dataclass(frozen=True)
class GenerationDependencies:
    analyze_topic: Callable[..., Any]
    generate_color_proposals: Callable[..., Any]
    pick_color: Callable[..., Any]
    generate_outline_proposals: Callable[..., Any]
    pick_outline: Callable[..., Any]
    pick_template_family: Callable[..., str]
    generate_outline: Callable[..., Any]
    create_enhancement_agent: Callable[..., Any]
    generate_slides_html: Callable[..., Any]
    generate_slides_html_with_images: Callable[..., Any]
    convert_html_to_pptx: Callable[..., Any]
    open_file: Callable[[Path], None]
    create_error_report: Callable[..., Any]


class GenerationPipeline:
    def __init__(
        self,
        llm: Any,
        config: GenerationConfig,
        artifacts: GenerationArtifacts,
        dependencies: GenerationDependencies,
    ) -> None:
        self.llm = llm
        self.config = config
        self.artifacts = artifacts
        self.dependencies = dependencies

    def run(self, topic: str, ideas: str = "") -> GenerationResult:
        self.artifacts.output_dir.mkdir(parents=True, exist_ok=True)

        suggestion = self.dependencies.analyze_topic(self.llm, topic=topic, ideas=ideas)
        color_proposals = self.dependencies.generate_color_proposals(
            self.llm,
            topic=topic,
            audience=suggestion.target_audience,
        )
        chosen_color = self.dependencies.pick_color(color_proposals, topic=topic)

        outline_proposals = self.dependencies.generate_outline_proposals(
            self.llm,
            topic=topic,
            audience=suggestion.target_audience,
            pages=suggestion.estimated_pages,
        )
        chosen_outline = self.dependencies.pick_outline(outline_proposals, topic=topic)
        template_family = self.dependencies.pick_template_family(
            topic,
            suggestion,
            chosen_color,
            chosen_outline,
        )

        outline = self.dependencies.generate_outline(
            self.llm,
            topic=topic,
            audience=suggestion.target_audience,
            pages=chosen_outline.slide_count,
            key_messages=suggestion.key_messages,
            research_facts=None,
        )

        enhanced_outline = None
        if self.config.enable_images or self.config.enable_charts:
            enhancement_agent = self.dependencies.create_enhancement_agent(
                llm=self.llm,
                output_dir=self.artifacts.output_dir,
                enable_images=self.config.enable_images,
                enable_charts=self.config.enable_charts,
            )
            if enhancement_agent is not None:
                enhanced_outline = enhancement_agent.enhance_outline(outline, chosen_color, topic=topic)

        has_visual_assets = bool(
            enhanced_outline and (enhanced_outline.images or enhanced_outline.charts)
        )
        if has_visual_assets:
            self.dependencies.generate_slides_html_with_images(
                outline,
                chosen_color.colors,
                enhanced_outline.images,
                enhanced_outline.charts,
                output_path=str(self.artifacts.html_path),
                theme_family=template_family,
            )
        else:
            self.dependencies.generate_slides_html(
                outline,
                chosen_color.colors,
                output_path=str(self.artifacts.html_path),
                theme_family=template_family,
            )

        self.dependencies.convert_html_to_pptx(str(self.artifacts.html_path), str(self.artifacts.pptx_path))

        image_count = len(enhanced_outline.images) if enhanced_outline else 0
        chart_count = len(enhanced_outline.charts) if enhanced_outline else 0
        self.dependencies.create_error_report(topic=topic, total_slides=len(outline.slides))

        return GenerationResult(
            topic=topic,
            color_name=chosen_color.name,
            outline_name=chosen_outline.name,
            template_family=template_family,
            html_path=self.artifacts.html_path,
            pptx_path=self.artifacts.pptx_path,
            image_count=image_count,
            chart_count=chart_count,
        )
