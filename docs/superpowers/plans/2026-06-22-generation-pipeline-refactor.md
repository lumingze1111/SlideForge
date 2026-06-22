# Generation Pipeline Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the current `main.py` generation flow into a reusable, testable pipeline while preserving the existing CLI behavior.

**Architecture:** Add a small `slideforge.pipeline` package that owns configuration, feature flags, artifact paths, and orchestration. Keep `main.py` as a thin CLI adapter that gathers user input, creates the DeepSeek chat model, and delegates the actual generation work to `GenerationPipeline`.

**Tech Stack:** Python 3.11, dataclasses, pathlib, existing LangChain `ChatOpenAI`, existing SlideForge agents/tools, pytest with mocks.

---

## File Map

- Create `slideforge/pipeline/__init__.py`: export the public pipeline API.
- Create `slideforge/pipeline/config.py`: environment-backed generation configuration and feature flag detection.
- Create `slideforge/pipeline/artifacts.py`: artifact path construction and filename sanitization.
- Create `slideforge/pipeline/generation.py`: reusable `GenerationPipeline` and `GenerationResult`.
- Modify `main.py`: keep CLI prompts and terminal output, delegate core generation to `GenerationPipeline`.
- Create `tests/test_pipeline_config.py`: unit tests for config and feature flags.
- Create `tests/test_pipeline_artifacts.py`: unit tests for output filenames.
- Create `tests/test_generation_pipeline.py`: orchestration tests using fake dependencies.
- Create `tests/test_main_cli.py`: smoke test proving `main.main()` delegates to the pipeline.

## Task 1: Add Environment Configuration

**Files:**
- Create: `slideforge/pipeline/__init__.py`
- Create: `slideforge/pipeline/config.py`
- Test: `tests/test_pipeline_config.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline_config.py`:

```python
import pytest

from slideforge.pipeline.config import GenerationConfig, MissingApiKeyError


def test_generation_config_requires_deepseek_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(MissingApiKeyError) as exc:
        GenerationConfig.from_env()

    assert "DEEPSEEK_API_KEY" in str(exc.value)


def test_generation_config_disables_images_without_provider_keys(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("ENABLE_IMAGE_SEARCH", "true")
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)

    config = GenerationConfig.from_env()

    assert config.api_key == "sk-test"
    assert config.enable_images is False
    assert config.image_disable_reason == "missing image provider API key"


def test_generation_config_respects_feature_flags(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("ENABLE_IMAGE_SEARCH", "false")
    monkeypatch.setenv("ENABLE_CHART_GENERATION", "false")
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "unsplash")

    config = GenerationConfig.from_env()

    assert config.enable_images is False
    assert config.enable_charts is False
    assert config.image_disable_reason == "disabled by ENABLE_IMAGE_SEARCH"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_pipeline_config.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'slideforge.pipeline'`.

- [ ] **Step 3: Add the configuration module**

Create `slideforge/pipeline/__init__.py`:

```python
"""Reusable generation pipeline APIs."""

from slideforge.pipeline.config import GenerationConfig, MissingApiKeyError

__all__ = ["GenerationConfig", "MissingApiKeyError"]
```

Create `slideforge/pipeline/config.py`:

```python
"""Configuration for SlideForge generation runs."""

from __future__ import annotations

import os
from dataclasses import dataclass


class MissingApiKeyError(RuntimeError):
    """Raised when the required DeepSeek API key is not configured."""


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GenerationConfig:
    api_key: str
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.7
    enable_images: bool = True
    enable_charts: bool = True
    image_disable_reason: str = ""

    @classmethod
    def from_env(cls) -> "GenerationConfig":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise MissingApiKeyError("Please set DEEPSEEK_API_KEY before running SlideForge")

        requested_images = _env_flag("ENABLE_IMAGE_SEARCH", True)
        enable_charts = _env_flag("ENABLE_CHART_GENERATION", True)
        has_image_provider = bool(os.getenv("UNSPLASH_ACCESS_KEY") or os.getenv("PEXELS_API_KEY"))

        enable_images = requested_images and has_image_provider
        image_disable_reason = ""
        if not requested_images:
            image_disable_reason = "disabled by ENABLE_IMAGE_SEARCH"
        elif not has_image_provider:
            image_disable_reason = "missing image provider API key"

        return cls(
            api_key=api_key,
            enable_images=enable_images,
            enable_charts=enable_charts,
            image_disable_reason=image_disable_reason,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
./venv/bin/python -m pytest tests/test_pipeline_config.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add slideforge/pipeline/__init__.py slideforge/pipeline/config.py tests/test_pipeline_config.py
git commit -m "refactor: add generation config"
```

## Task 2: Add Artifact Path Builder

**Files:**
- Create: `slideforge/pipeline/artifacts.py`
- Test: `tests/test_pipeline_artifacts.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline_artifacts.py`:

```python
from pathlib import Path

from slideforge.pipeline.artifacts import GenerationArtifacts, sanitize_topic_filename


def test_sanitize_topic_filename_keeps_chinese_and_replaces_spaces():
    assert sanitize_topic_filename("库里 职业 生涯") == "库里_职业_生涯"


def test_sanitize_topic_filename_removes_path_separators():
    assert sanitize_topic_filename("../bad/topic") == "bad_topic"


def test_generation_artifacts_builds_html_and_pptx_paths(tmp_path):
    artifacts = GenerationArtifacts.for_topic(tmp_path, "AI 与 艺术融合：未来趋势")

    assert artifacts.output_dir == tmp_path
    assert artifacts.html_path == tmp_path / "slides_AI_与_艺术融合.html"
    assert artifacts.pptx_path == tmp_path / "slides_AI_与_艺术融合_未来趋势.pptx"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_pipeline_artifacts.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'slideforge.pipeline.artifacts'`.

- [ ] **Step 3: Add the artifact path module**

Create `slideforge/pipeline/artifacts.py`:

```python
"""Output artifact paths for a SlideForge generation run."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


def sanitize_topic_filename(topic: str, max_chars: int = 20) -> str:
    value = topic.strip().replace("/", "_").replace("\\", "_")
    value = value.replace("..", "")
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "", value)
    value = value.strip("_-")
    if not value:
        return "presentation"
    return value[:max_chars]


@dataclass(frozen=True)
class GenerationArtifacts:
    output_dir: Path
    html_path: Path
    pptx_path: Path

    @classmethod
    def for_topic(cls, output_dir: Path, topic: str) -> "GenerationArtifacts":
        output_dir = Path(output_dir)
        html_stem = sanitize_topic_filename(topic, max_chars=10)
        pptx_stem = sanitize_topic_filename(topic, max_chars=20)
        return cls(
            output_dir=output_dir,
            html_path=output_dir / f"slides_{html_stem}.html",
            pptx_path=output_dir / f"slides_{pptx_stem}.pptx",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
./venv/bin/python -m pytest tests/test_pipeline_artifacts.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add slideforge/pipeline/artifacts.py tests/test_pipeline_artifacts.py
git commit -m "refactor: add generation artifact paths"
```

## Task 3: Add Reusable Generation Pipeline

**Files:**
- Create: `slideforge/pipeline/generation.py`
- Modify: `slideforge/pipeline/__init__.py`
- Test: `tests/test_generation_pipeline.py`

- [ ] **Step 1: Write the failing orchestration test**

Create `tests/test_generation_pipeline.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./venv/bin/python -m pytest tests/test_generation_pipeline.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'slideforge.pipeline.generation'`.

- [ ] **Step 3: Add the pipeline module**

Create `slideforge/pipeline/generation.py`:

```python
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
            )
        else:
            self.dependencies.generate_slides_html(
                outline,
                chosen_color.colors,
                output_path=str(self.artifacts.html_path),
            )

        self.dependencies.convert_html_to_pptx(str(self.artifacts.html_path), str(self.artifacts.pptx_path))

        image_count = len(enhanced_outline.images) if enhanced_outline else 0
        chart_count = len(enhanced_outline.charts) if enhanced_outline else 0
        self.dependencies.create_error_report(topic=topic, total_slides=len(outline.slides))

        return GenerationResult(
            topic=topic,
            color_name=chosen_color.name,
            outline_name=chosen_outline.name,
            html_path=self.artifacts.html_path,
            pptx_path=self.artifacts.pptx_path,
            image_count=image_count,
            chart_count=chart_count,
        )
```

Modify `slideforge/pipeline/__init__.py`:

```python
"""Reusable generation pipeline APIs."""

from slideforge.pipeline.artifacts import GenerationArtifacts, sanitize_topic_filename
from slideforge.pipeline.config import GenerationConfig, MissingApiKeyError
from slideforge.pipeline.generation import (
    GenerationDependencies,
    GenerationPipeline,
    GenerationResult,
)

__all__ = [
    "GenerationArtifacts",
    "GenerationConfig",
    "GenerationDependencies",
    "GenerationPipeline",
    "GenerationResult",
    "MissingApiKeyError",
    "sanitize_topic_filename",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
./venv/bin/python -m pytest tests/test_generation_pipeline.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add slideforge/pipeline/__init__.py slideforge/pipeline/generation.py tests/test_generation_pipeline.py
git commit -m "refactor: add reusable generation pipeline"
```

## Task 4: Delegate CLI Main to the Pipeline

**Files:**
- Modify: `main.py`
- Test: `tests/test_main_cli.py`

- [ ] **Step 1: Write the failing CLI delegation test**

Create `tests/test_main_cli.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails before refactor**

Run:

```bash
./venv/bin/python -m pytest tests/test_main_cli.py -q
```

Expected: FAIL because `main.GenerationPipeline` or `main.OUTPUT_DIR` is not available.

- [ ] **Step 3: Refactor `main.py` into a thin CLI adapter**

Modify `main.py` so it imports and uses the new pipeline. Keep existing imports needed by dependency wiring:

```python
from pathlib import Path
import subprocess
import sys

from langchain_openai import ChatOpenAI

from slideforge.agents.content_enhancement_agent import ContentEnhancementAgent
from slideforge.agents.html_generator import (
    generate_outline,
    generate_slides_html,
    generate_slides_html_with_images,
)
from slideforge.agents.outline_proposal import generate_outline_proposals, pick_outline_proposal
from slideforge.agents.propose_agent import pick_proposal, run_propose_agent
from slideforge.agents.topic_analyzer import analyze_topic
from slideforge.error_tracking import ErrorReporter, ErrorTracker, set_error_tracker
from slideforge.pipeline import GenerationArtifacts, GenerationConfig, GenerationDependencies, GenerationPipeline


OUTPUT_DIR = Path(__file__).parent / "output"


def _open_file(path: Path) -> None:
    subprocess.run(["open", str(path)], check=False)


def _create_dependencies(error_tracker: ErrorTracker) -> GenerationDependencies:
    def create_enhancement_agent(**kwargs):
        return ContentEnhancementAgent(error_tracker=error_tracker, **kwargs)

    def convert_with_fallback(html_path: str, pptx_path: str) -> int:
        llm_convert_script = str(Path(__file__).parent / "tools" / "llm_direct_convert.py")
        result = subprocess.run(
            [sys.executable, llm_convert_script, "--html", html_path, "--output", pptx_path],
            capture_output=False,
            text=True,
        )
        if result.returncode != 0:
            from slideforge.pptx_converter import convert_html_to_pptx

            convert_html_to_pptx(html_path, pptx_path, verbose=True)
        return result.returncode

    def create_error_report(topic: str, total_slides: int) -> None:
        reporter = ErrorReporter(error_tracker=error_tracker, topic=topic, total_slides=total_slides)
        reporter.save_report()

    return GenerationDependencies(
        analyze_topic=analyze_topic,
        generate_color_proposals=run_propose_agent,
        pick_color=pick_proposal,
        generate_outline_proposals=generate_outline_proposals,
        pick_outline=pick_outline_proposal,
        generate_outline=generate_outline,
        create_enhancement_agent=create_enhancement_agent,
        generate_slides_html=generate_slides_html,
        generate_slides_html_with_images=generate_slides_html_with_images,
        convert_html_to_pptx=convert_with_fallback,
        open_file=_open_file,
        create_error_report=create_error_report,
    )
```

Replace the body of `main()` with:

```python
def main() -> None:
    try:
        config = GenerationConfig.from_env()
    except RuntimeError as exc:
        print(f"\n  ❌ {exc}\n")
        sys.exit(1)

    llm = ChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        temperature=config.temperature,
    )

    if len(sys.argv) > 1:
        topic = sys.argv[1]
        ideas = sys.argv[2] if len(sys.argv) > 2 else ""
    else:
        topic = input("\n  💭 请输入演示主题：").strip()
        if not topic:
            topic = "AI与艺术的融合：探讨人工智能如何改变创意产业"
        ideas = input("  💡 你的想法/目标（可留空）：").strip()

    OUTPUT_DIR.mkdir(exist_ok=True)
    session_id = "cli"
    error_tracker = ErrorTracker(session_id, OUTPUT_DIR)
    set_error_tracker(error_tracker)

    pipeline = GenerationPipeline(
        llm=llm,
        config=config,
        artifacts=GenerationArtifacts.for_topic(OUTPUT_DIR, topic),
        dependencies=_create_dependencies(error_tracker),
    )
    result = pipeline.run(topic=topic, ideas=ideas)

    print("\n" + "═" * 70)
    print("  🎉 生成完成！")
    print(f"  主题：{result.topic}")
    print(f"  配色方案：{result.color_name}")
    print(f"  大纲结构：{result.outline_name}")
    if result.image_count:
        print(f"  插入图片：{result.image_count} 张")
    if result.chart_count:
        print(f"  生成图表：{result.chart_count} 个")
    print(f"  HTML 预览：{result.html_path}")
    print(f"  PPTX 文件：{result.pptx_path}")
    print("═" * 70 + "\n")
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_pipeline_config.py tests/test_pipeline_artifacts.py tests/test_generation_pipeline.py tests/test_main_cli.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 5: Run full tests**

Run:

```bash
./venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add main.py slideforge/pipeline tests/test_main_cli.py
git commit -m "refactor: delegate cli to generation pipeline"
```

## Self-Review

- Spec coverage: This plan covers priority 1 by extracting config, artifact naming, orchestration, and CLI delegation while keeping existing generation behavior.
- Placeholder scan: No placeholder-only steps remain; each code-changing task includes concrete test and implementation snippets.
- Type consistency: `GenerationConfig`, `GenerationArtifacts`, `GenerationDependencies`, `GenerationPipeline`, and `GenerationResult` are introduced before use and imported through `slideforge.pipeline`.
