"""Deterministic slide layout template selection.

The selector is intentionally small and side-effect free so rendering can vary
without involving LLM calls, network tools, or PPTX conversion.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutTemplate:
    name: str
    slide_type: str
    supports_image: bool = False
    supports_chart: bool = False
    density: str = "normal"
    theme_tags: tuple[str, ...] = ("minimal",)


@dataclass(frozen=True)
class TemplateContext:
    slide_type: str
    slide_index: int
    total_slides: int
    bullet_count: int = 0
    title_length: int = 0
    has_image: bool = False
    has_chart: bool = False
    theme_family: str = ""


TEMPLATES: dict[str, tuple[LayoutTemplate, ...]] = {
    "cover": (
        LayoutTemplate("cover-centered", "cover", theme_tags=("minimal", "business")),
        LayoutTemplate("cover-split-hero", "cover", supports_image=True, theme_tags=("story", "business")),
        LayoutTemplate("cover-background-hero", "cover", supports_image=True, theme_tags=("story", "technical")),
    ),
    "section": (
        LayoutTemplate("section-left-rail", "section", theme_tags=("business", "technical")),
        LayoutTemplate("section-centered", "section", theme_tags=("minimal",)),
        LayoutTemplate("section-numeral", "section", theme_tags=("story", "data")),
    ),
    "content": (
        LayoutTemplate("content-classic", "content", density="dense", theme_tags=("business", "minimal")),
        LayoutTemplate("content-insight-cards", "content", theme_tags=("data", "business")),
        LayoutTemplate("content-left-rail", "content", theme_tags=("technical", "story")),
        LayoutTemplate(
            "content-right-visual",
            "content",
            supports_image=True,
            supports_chart=True,
            theme_tags=("story", "technical"),
        ),
    ),
    "two_column": (
        LayoutTemplate("two-column-comparison", "two_column", theme_tags=("business", "technical")),
        LayoutTemplate("two-column-pro-con", "two_column", theme_tags=("business",)),
        LayoutTemplate("two-column-asymmetric", "two_column", supports_image=True, theme_tags=("story", "technical")),
    ),
    "data": (
        LayoutTemplate("data-big-stat", "data", theme_tags=("data", "business")),
        LayoutTemplate("data-chart-forward", "data", supports_chart=True, theme_tags=("data",)),
        LayoutTemplate("data-kpi-strip", "data", density="dense", theme_tags=("data", "business")),
    ),
    "closing": (
        LayoutTemplate("closing-centered", "closing", theme_tags=("minimal",)),
        LayoutTemplate("closing-action-list", "closing", theme_tags=("business",)),
        LayoutTemplate("closing-quote", "closing", theme_tags=("story",)),
    ),
}


def _templates_for(slide_type: str) -> tuple[LayoutTemplate, ...]:
    return TEMPLATES.get(slide_type) or TEMPLATES["content"]


def _matches_theme(template: LayoutTemplate, theme_family: str) -> bool:
    return bool(theme_family) and theme_family in template.theme_tags


def select_layout_template(context: TemplateContext) -> LayoutTemplate:
    slide_type = context.slide_type if context.slide_type in TEMPLATES else "content"
    templates = _templates_for(slide_type)

    if context.has_chart:
        for template in templates:
            if template.supports_chart:
                return template

    if context.has_image:
        for template in templates:
            if template.supports_image:
                return template

    if slide_type == "content" and context.bullet_count >= 5:
        return templates[0]

    if context.theme_family:
        themed = [template for template in templates if _matches_theme(template, context.theme_family)]
        if themed:
            return themed[(max(context.slide_index, 1) - 1) % len(themed)]

    index = (max(context.slide_index, 1) - 1) % len(templates)
    template = templates[index]
    if not context.has_image and not context.has_chart and (template.supports_image or template.supports_chart):
        text_templates = [item for item in templates if not item.supports_image and not item.supports_chart]
        return text_templates[(max(context.slide_index, 1) - 1) % len(text_templates)]
    return template
