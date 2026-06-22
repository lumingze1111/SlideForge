# Layout Template Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic layout template pool so SlideForge decks can vary page composition now and evolve toward theme-driven template families later.

**Architecture:** Create a focused `slideforge/agents/layout_templates.py` module for template metadata and selection. Keep HTML rendering inside `html_generator.py`, but route each slide through a selected template variant before existing PPTX conversion consumes the HTML.

**Tech Stack:** Python 3.11, Pydantic outline models, pytest, existing inline-style HTML rendering, existing image/chart insertion helpers.

---

## File Structure

- Create `slideforge/agents/layout_templates.py`: template dataclasses, context builder, deterministic selector.
- Modify `slideforge/agents/html_generator.py`: render multiple layout variants and pass template context from plain and media-aware HTML generation paths.
- Create `tests/test_layout_templates.py`: selector behavior tests.
- Modify `tests/test_html_generator_templates.py`: HTML variation and compatibility tests.

## Task 1: Template Selector

**Files:**
- Create: `slideforge/agents/layout_templates.py`
- Test: `tests/test_layout_templates.py`

- [ ] **Step 1: Write failing selector tests**

```python
from slideforge.agents.layout_templates import TemplateContext, select_layout_template


def test_content_slides_rotate_through_text_templates():
    first = select_layout_template(TemplateContext(slide_type="content", slide_index=1, total_slides=5))
    second = select_layout_template(TemplateContext(slide_type="content", slide_index=2, total_slides=5))
    third = select_layout_template(TemplateContext(slide_type="content", slide_index=3, total_slides=5))

    assert [first.name, second.name, third.name] == [
        "content-classic",
        "content-insight-cards",
        "content-left-rail",
    ]


def test_media_context_prefers_visual_templates():
    image_template = select_layout_template(
        TemplateContext(slide_type="content", slide_index=2, total_slides=5, has_image=True)
    )
    chart_template = select_layout_template(
        TemplateContext(slide_type="data", slide_index=3, total_slides=5, has_chart=True)
    )

    assert image_template.name == "content-right-visual"
    assert chart_template.name == "data-chart-forward"


def test_dense_content_uses_wide_text_template():
    template = select_layout_template(
        TemplateContext(slide_type="content", slide_index=3, total_slides=6, bullet_count=6)
    )

    assert template.name == "content-classic"


def test_unknown_slide_type_falls_back_to_content_default():
    template = select_layout_template(TemplateContext(slide_type="unknown", slide_index=1, total_slides=3))

    assert template.slide_type == "content"
    assert template.name == "content-classic"
```

- [ ] **Step 2: Run selector tests to verify RED**

Run: `/Users/lumingze/Desktop/SlideForge/venv/bin/python -m pytest tests/test_layout_templates.py -v`

Expected: FAIL because `slideforge.agents.layout_templates` does not exist.

- [ ] **Step 3: Implement selector**

Create `slideforge/agents/layout_templates.py` with:

```python
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
        LayoutTemplate("content-right-visual", "content", supports_image=True, supports_chart=True, theme_tags=("story", "technical")),
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
```

- [ ] **Step 4: Run selector tests to verify GREEN**

Run: `/Users/lumingze/Desktop/SlideForge/venv/bin/python -m pytest tests/test_layout_templates.py -v`

Expected: PASS.

- [ ] **Step 5: Commit selector**

```bash
git add slideforge/agents/layout_templates.py tests/test_layout_templates.py
git commit -m "feat: add layout template selector"
```

## Task 2: HTML Rendering Variants

**Files:**
- Modify: `slideforge/agents/html_generator.py`
- Test: `tests/test_html_generator_templates.py`

- [ ] **Step 1: Write failing HTML tests**

```python
from pathlib import Path

from slideforge.agents.html_generator import PresentationOutline, SlideContent, generate_slides_html


COLORS = {
    "background": "#0f172a",
    "primary": "#38bdf8",
    "accent": "#f59e0b",
    "text_primary": "#ffffff",
    "text_secondary": "#cbd5e1",
    "surface": "#1e293b",
    "border": "#475569",
}


def test_generate_slides_html_uses_multiple_content_templates(tmp_path):
    outline = PresentationOutline(
        total_pages=3,
        slides=[
            SlideContent(slide_type="content", title="One", bullets=["A", "B"]),
            SlideContent(slide_type="content", title="Two", bullets=["A", "B"]),
            SlideContent(slide_type="content", title="Three", bullets=["A", "B"]),
        ],
    )

    path = generate_slides_html(outline, COLORS, output_path=str(tmp_path / "slides.html"))
    html = Path(path).read_text(encoding="utf-8")

    assert 'data-layout-template="content-classic"' in html
    assert 'data-layout-template="content-insight-cards"' in html
    assert 'data-layout-template="content-left-rail"' in html
    assert html.count("data-pptx-slide") == 3


def test_dense_content_keeps_classic_template(tmp_path):
    outline = PresentationOutline(
        total_pages=1,
        slides=[
            SlideContent(slide_type="content", title="Dense", bullets=["A", "B", "C", "D", "E", "F"]),
        ],
    )

    path = generate_slides_html(outline, COLORS, output_path=str(tmp_path / "slides.html"))
    html = Path(path).read_text(encoding="utf-8")

    assert 'data-layout-template="content-classic"' in html
    assert 'data-layout-template="content-insight-cards"' not in html
```

- [ ] **Step 2: Run HTML tests to verify RED**

Run: `/Users/lumingze/Desktop/SlideForge/venv/bin/python -m pytest tests/test_html_generator_templates.py -v`

Expected: FAIL because rendered slides do not include template attributes or variants.

- [ ] **Step 3: Implement template-aware rendering**

Modify `html_generator.py` to:

- import `TemplateContext` and `select_layout_template`;
- add optional `template_name` parameter to `render_slide_html`;
- add helper render branches for `content-insight-cards`, `content-left-rail`, and enough variants for other slide types to produce meaningful diversity;
- add `data-layout-template="<name>"` to the root slide element;
- create template context in `generate_slides_html` and `generate_slides_html_with_images`.

- [ ] **Step 4: Run HTML tests to verify GREEN**

Run: `/Users/lumingze/Desktop/SlideForge/venv/bin/python -m pytest tests/test_html_generator_templates.py -v`

Expected: PASS.

- [ ] **Step 5: Run focused existing tests**

Run: `/Users/lumingze/Desktop/SlideForge/venv/bin/python -m pytest tests/test_generation_pipeline.py tests/test_main_cli.py tests/test_image_matching.py -v`

Expected: PASS.

- [ ] **Step 6: Commit renderer**

```bash
git add slideforge/agents/html_generator.py tests/test_html_generator_templates.py
git commit -m "feat: render varied slide layout templates"
```

## Task 3: Full Verification

**Files:**
- Modify only if verification exposes a bug.

- [ ] **Step 1: Run full test suite**

Run: `/Users/lumingze/Desktop/SlideForge/venv/bin/python -m pytest`

Expected: PASS with all collected tests passing.

- [ ] **Step 2: Inspect git status**

Run: `git status --short --branch`

Expected: branch `codex/layout-template-pool` has no unstaged implementation changes.

- [ ] **Step 3: Summarize implementation evidence**

Record the passing test command and changed files in the final response.
