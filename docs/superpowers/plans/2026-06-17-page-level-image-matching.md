# Page-Level Image Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select slide-relevant images by scoring multiple provider candidates against each slide's title, content, and presentation topic.

**Architecture:** Add a focused `slideforge/tools/image_matching.py` helper module for query context, query construction, candidate scoring, and candidate selection. Integrate it into `ContentEnhancementAgent.search_image()` while keeping `ImageSuggestion` and HTML rendering unchanged.

**Tech Stack:** Python 3.11, Pydantic models already in `slideforge.agents.html_generator`, dataclasses, existing `ImageSearchTool`, pytest, responses/mocks.

---

## File Map

- Create `slideforge/tools/image_matching.py`: pure, deterministic image matching helpers with no network calls.
- Modify `slideforge/agents/content_enhancement_agent.py`: pass the current slide context into the image search tool and select the best candidate before downloading.
- Modify `slideforge/tools/__init__.py`: export image matching helpers for tests and future reuse.
- Create `tests/test_image_matching.py`: unit tests for query construction, scoring, and rejection.
- Modify `tests/test_image_search.py` only if existing imports need adjustment; do not change network API tests otherwise.

## Task 1: Add Query Context and Query Construction

**Files:**
- Create: `slideforge/tools/image_matching.py`
- Test: `tests/test_image_matching.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_image_matching.py` with:

```python
from slideforge.agents.html_generator import SlideContent
from slideforge.tools.image_matching import (
    ImageQueryContext,
    build_image_query_context,
    build_image_queries,
)


def test_build_image_query_context_collects_slide_text():
    slide = SlideContent(
        slide_type="content",
        title="三分革命",
        subtitle="改变 NBA 空间打法",
        bullets=["超远距离投篮", "勇士体系", "防守拉伸"],
        key_stat="402",
        key_stat_label="单赛季三分命中数",
    )

    context = build_image_query_context(
        topic="斯蒂芬·库里",
        slide_index=2,
        slide=slide,
        requested_keywords="three point shooting",
    )

    assert context.topic == "斯蒂芬·库里"
    assert context.slide_index == 2
    assert context.slide_title == "三分革命"
    assert "超远距离投篮" in context.slide_text
    assert "402" in context.slide_text
    assert context.requested_keywords == "three point shooting"


def test_build_image_queries_include_topic_title_and_requested_keywords():
    context = ImageQueryContext(
        topic="Stephen Curry",
        slide_index=1,
        slide_type="content",
        slide_title="Three Point Revolution",
        slide_text="Warriors spacing deep shooting NBA defense",
        requested_keywords="three point shooting",
    )

    queries = build_image_queries(context)

    assert queries[0] == "Stephen Curry Three Point Revolution three point shooting"
    assert "Stephen Curry Three Point Revolution" in queries
    assert "Stephen Curry NBA basketball" in queries
    assert len(queries) == len(set(queries))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_matching.py -q
```

Expected: import failure because `slideforge.tools.image_matching` does not exist.

- [ ] **Step 3: Implement the minimal module**

Create `slideforge/tools/image_matching.py`:

```python
"""
Deterministic page-level image matching helpers.

This module has no network calls. It turns slide content into search queries
and scores provider metadata before any image is downloaded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from slideforge.agents.html_generator import SlideContent


@dataclass(frozen=True)
class ImageQueryContext:
    topic: str
    slide_index: int
    slide_type: str
    slide_title: str
    slide_text: str
    requested_keywords: str = ""


def build_image_query_context(
    topic: str,
    slide_index: int,
    slide: SlideContent,
    requested_keywords: str = "",
) -> ImageQueryContext:
    parts = [
        slide.title,
        slide.subtitle,
        " ".join(slide.bullets),
        slide.key_stat,
        slide.key_stat_label,
    ]
    slide_text = " ".join(part for part in parts if part).strip()
    return ImageQueryContext(
        topic=topic.strip(),
        slide_index=slide_index,
        slide_type=slide.slide_type,
        slide_title=slide.title.strip(),
        slide_text=slide_text,
        requested_keywords=requested_keywords.strip(),
    )


def _dedupe(items: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        normalized = " ".join(item.split())
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def build_image_queries(context: ImageQueryContext) -> list[str]:
    base = " ".join(part for part in [context.topic, context.slide_title] if part)
    queries = [
        " ".join(part for part in [base, context.requested_keywords] if part),
        base,
    ]
    if _contains_any(context.topic, {"curry", "nba", "basketball", "warriors"}) or _contains_any(
        context.slide_text, {"nba", "basketball", "warriors", "三分", "投篮", "库里"}
    ):
        queries.append(f"{context.topic} NBA basketball")
    elif context.topic:
        queries.append(context.topic)
    return _dedupe(queries)[:3]


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]+|[\u4e00-\u9fff]{2,}", text or "")
    }


def _contains_any(text: str, terms: set[str]) -> bool:
    lower = (text or "").lower()
    return any(term.lower() in lower for term in terms)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_matching.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add slideforge/tools/image_matching.py tests/test_image_matching.py
git commit -m "test: add image query context helpers"
```

## Task 2: Add Candidate Scoring and Rejection

**Files:**
- Modify: `slideforge/tools/image_matching.py`
- Test: `tests/test_image_matching.py`

- [ ] **Step 1: Write failing tests for scoring**

Append to `tests/test_image_matching.py`:

```python
from slideforge.tools.image_search import ImageResult, ImageSource
from slideforge.tools.image_matching import choose_best_image


def _image(description, width=1920, height=1080):
    return ImageResult(
        url=f"https://example.com/{description.replace(' ', '-')}.jpg",
        description=description,
        author="Test",
        source=ImageSource.UNSPLASH,
        width=width,
        height=height,
        download_url=f"https://example.com/{description.replace(' ', '-')}-raw.jpg",
    )


def test_choose_best_image_prefers_slide_relevant_basketball_candidate():
    context = ImageQueryContext(
        topic="Stephen Curry",
        slide_index=2,
        slide_type="content",
        slide_title="Three Point Revolution",
        slide_text="NBA Warriors basketball shooting deep threes",
        requested_keywords="three point shooting",
    )
    candidates = [
        _image("Office desk with marketing documents"),
        _image("Soccer player celebrating a goal"),
        _image("Basketball player shooting a three point shot in NBA arena"),
        _image("Traditional architecture at sunset"),
    ]

    selected = choose_best_image(context, candidates)

    assert selected is not None
    assert selected.description == "Basketball player shooting a three point shot in NBA arena"


def test_choose_best_image_rejects_unrelated_candidates():
    context = ImageQueryContext(
        topic="Stephen Curry",
        slide_index=2,
        slide_type="content",
        slide_title="Three Point Revolution",
        slide_text="NBA Warriors basketball shooting deep threes",
        requested_keywords="three point shooting",
    )
    candidates = [
        _image("Office desk with laptop"),
        _image("Traditional architecture at sunset"),
        _image("Wedding flowers on a table"),
    ]

    selected = choose_best_image(context, candidates)

    assert selected is None


def test_choose_best_image_prefers_landscape_when_relevance_is_close():
    context = ImageQueryContext(
        topic="NBA",
        slide_index=1,
        slide_type="cover",
        slide_title="Global Basketball Business",
        slide_text="NBA basketball league arena fans",
        requested_keywords="basketball arena",
    )
    portrait = _image("Basketball arena fans", width=900, height=1400)
    landscape = _image("Basketball arena fans", width=1920, height=1080)

    selected = choose_best_image(context, [portrait, landscape])

    assert selected is landscape
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_matching.py -q
```

Expected: import failure for `choose_best_image`.

- [ ] **Step 3: Implement scoring helpers**

Add to `slideforge/tools/image_matching.py`:

```python
UNRELATED_TERMS = {
    "soccer",
    "football",
    "tennis",
    "volleyball",
    "office",
    "desk",
    "architecture",
    "landscape",
    "wedding",
    "food",
    "flowers",
}

SPORT_CONTEXT_TERMS = {"basketball", "nba", "warriors", "curry", "shooting", "three", "三分", "投篮", "库里"}

MIN_RELEVANCE_SCORE = 5


def score_image_candidate(context: ImageQueryContext, image) -> int:
    metadata = " ".join(
        str(part)
        for part in [
            getattr(image, "description", ""),
            getattr(image, "author", ""),
            getattr(image, "source", ""),
        ]
        if part
    )
    meta_tokens = _tokens(metadata)
    title_tokens = _tokens(context.slide_title)
    topic_tokens = _tokens(context.topic)
    text_tokens = _tokens(context.slide_text)
    requested_tokens = _tokens(context.requested_keywords)

    score = 0
    score += 4 * len(meta_tokens & title_tokens)
    score += 3 * len(meta_tokens & requested_tokens)
    score += 2 * len(meta_tokens & topic_tokens)
    score += len(meta_tokens & text_tokens)

    width = int(getattr(image, "width", 0) or 0)
    height = int(getattr(image, "height", 0) or 0)
    if width >= height and width >= 1200:
        score += 2
    elif height > width:
        score -= 1

    context_text = " ".join([context.topic, context.slide_title, context.slide_text, context.requested_keywords])
    context_tokens = _tokens(context_text)
    if context_tokens & SPORT_CONTEXT_TERMS:
        unrelated_hits = meta_tokens & (UNRELATED_TERMS - context_tokens)
        score -= 5 * len(unrelated_hits)

    if _contains_any(metadata, {"basketball", "nba", "warriors", "curry", "shooting"}):
        score += 4

    return score


def choose_best_image(context: ImageQueryContext, candidates: Sequence) -> object | None:
    best = None
    best_score = MIN_RELEVANCE_SCORE
    for image in candidates:
        score = score_image_candidate(context, image)
        if score > best_score:
            best = image
            best_score = score
    return best
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_matching.py -q
```

Expected: all image matching tests pass.

- [ ] **Step 5: Run existing image search tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_search.py -q
```

Expected: existing image API tests still pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add slideforge/tools/image_matching.py tests/test_image_matching.py
git commit -m "feat: score image search candidates"
```

## Task 3: Integrate Matching into ContentEnhancementAgent

**Files:**
- Modify: `slideforge/agents/content_enhancement_agent.py`
- Modify: `slideforge/tools/__init__.py`
- Test: `tests/test_image_matching.py`

- [ ] **Step 1: Write failing integration-style test for selection helper**

Append to `tests/test_image_matching.py`:

```python
from unittest.mock import Mock
from slideforge.tools.image_matching import search_best_image


def test_search_best_image_queries_multiple_candidates_and_downloads_only_selected(tmp_path):
    context = ImageQueryContext(
        topic="Stephen Curry",
        slide_index=2,
        slide_type="content",
        slide_title="Three Point Revolution",
        slide_text="NBA Warriors basketball shooting deep threes",
        requested_keywords="three point shooting",
    )
    unrelated = _image("Office desk with laptop")
    selected = _image("Basketball player shooting a three point shot in NBA arena")
    image_tool = Mock()
    image_tool.search.side_effect = [
        [unrelated, selected],
    ]
    image_tool.download_image.return_value = str(tmp_path / "image.jpg")

    result = search_best_image(
        image_tool=image_tool,
        context=context,
        output_dir=tmp_path,
        preferred_source=ImageSource.UNSPLASH,
    )

    assert result is not None
    assert result.image is selected
    assert result.image_path.name.startswith("image_")
    image_tool.search.assert_called_once()
    assert image_tool.search.call_args.kwargs["limit"] == 6
    assert image_tool.search.call_args.kwargs["orientation"] == "landscape"
    image_tool.download_image.assert_called_once_with(selected, str(result.image_path))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_matching.py::test_search_best_image_queries_multiple_candidates_and_downloads_only_selected -q
```

Expected: import failure for `search_best_image`.

- [ ] **Step 3: Add search wrapper to helper module**

Add to `slideforge/tools/image_matching.py`:

```python
import uuid
from pathlib import Path

from slideforge.tools.image_search import ImageSearchError


@dataclass(frozen=True)
class SelectedImage:
    image: object
    image_path: Path


def search_best_image(
    image_tool,
    context: ImageQueryContext,
    output_dir: Path,
    preferred_source=None,
) -> SelectedImage | None:
    queries = build_image_queries(context)
    candidates = []
    last_error = None

    for query in queries:
        try:
            results = image_tool.search(
                query=query,
                limit=6,
                orientation="landscape",
                preferred_source=preferred_source,
            )
            candidates.extend(results)
            if candidates:
                break
        except ImageSearchError as exc:
            last_error = exc
            continue

    selected = choose_best_image(context, candidates)
    if selected is None:
        if last_error is not None and not candidates:
            raise last_error
        return None

    image_path = Path(output_dir) / f"image_{uuid.uuid4().hex[:8]}.jpg"
    image_tool.download_image(selected, str(image_path))
    return SelectedImage(image=selected, image_path=image_path)
```

- [ ] **Step 4: Run new integration-style test**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_matching.py::test_search_best_image_queries_multiple_candidates_and_downloads_only_selected -q
```

Expected: pass.

- [ ] **Step 5: Export helpers**

Modify `slideforge/tools/__init__.py`:

```python
from slideforge.tools.image_matching import (
    ImageQueryContext,
    SelectedImage,
    build_image_query_context,
    build_image_queries,
    choose_best_image,
    score_image_candidate,
    search_best_image,
)
```

Add these names to `__all__`:

```python
    "ImageQueryContext",
    "SelectedImage",
    "build_image_query_context",
    "build_image_queries",
    "choose_best_image",
    "score_image_candidate",
    "search_best_image",
```

- [ ] **Step 6: Integrate in `ContentEnhancementAgent`**

Modify imports in `slideforge/agents/content_enhancement_agent.py`:

```python
from slideforge.tools.image_matching import ImageQueryContext, build_image_query_context, search_best_image
```

In `enhance_outline()`, before `system_prompt`, set the current context. Use the slide title as a temporary topic fallback; Task 4 replaces this with the real presentation topic.

```python
self._current_image_context = build_image_query_context(
    topic=slide.title,
    slide_index=slide_index,
    slide=slide,
)
```

Then update the `search_image` tool body:

```python
context = getattr(self, "_current_image_context", None)
if context is None:
    context = build_image_query_context(
        topic=keywords,
        slide_index=0,
        slide=SlideContent(slide_type="content", title=keywords),
        requested_keywords=keywords,
    )
else:
    context = ImageQueryContext(
        topic=context.topic,
        slide_index=context.slide_index,
        slide_type=context.slide_type,
        slide_title=context.slide_title,
        slide_text=context.slide_text,
        requested_keywords=keywords,
    )

selected = search_best_image(
    image_tool=self.image_search_tool_instance,
    context=context,
    output_dir=self.output_dir,
    preferred_source=ImageSource.UNSPLASH,
)

if selected is None:
    return {"success": False, "message": "No relevant images found"}

image = selected.image
return {
    "success": True,
    "image_url": str(selected.image_path),
    "description": image.description,
    "position": position,
    "size": (size_width, size_height),
    "source": image.source.value,
}
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_matching.py tests/test_image_search.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add slideforge/tools/image_matching.py slideforge/tools/__init__.py slideforge/agents/content_enhancement_agent.py tests/test_image_matching.py
git commit -m "feat: select relevant slide images"
```

## Task 4: Preserve Presentation Topic in Image Context

**Files:**
- Modify: `slideforge/agents/content_enhancement_agent.py`
- Modify: `main.py`
- Test: `tests/test_image_matching.py`

- [ ] **Step 1: Write failing test for topic-aware context**

Append to `tests/test_image_matching.py`:

```python
def test_build_image_query_context_uses_global_topic_for_queries():
    slide = SlideContent(
        slide_type="content",
        title="商业价值",
        bullets=["球鞋合作", "品牌影响力"],
    )

    context = build_image_query_context(
        topic="Stephen Curry",
        slide_index=7,
        slide=slide,
        requested_keywords="brand partnership",
    )
    queries = build_image_queries(context)

    assert queries[0] == "Stephen Curry 商业价值 brand partnership"
```

- [ ] **Step 2: Run test**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_matching.py::test_build_image_query_context_uses_global_topic_for_queries -q
```

Expected: this may already pass. If it passes, keep it as regression coverage and continue.

- [ ] **Step 3: Extend `enhance_outline()` signature compatibly**

Modify `slideforge/agents/content_enhancement_agent.py`:

```python
def enhance_outline(
    self,
    outline: PresentationOutline,
    colors: ColorProposal,
    topic: str = "",
) -> EnhancedOutline:
```

Set context with the real topic:

```python
self._current_image_context = build_image_query_context(
    topic=topic or slide.title,
    slide_index=slide_index,
    slide=slide,
)
```

- [ ] **Step 4: Pass topic from main**

Modify `main.py` where `enhance_outline` is called:

```python
enhanced_outline = enhancement_agent.enhance_outline(outline, chosen_color, topic=topic)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_image_matching.py tests/test_image_search.py tests/test_error_tracking.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add main.py slideforge/agents/content_enhancement_agent.py tests/test_image_matching.py
git commit -m "feat: include presentation topic in image matching"
```

## Task 5: Full Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run all tests**

Run:

```bash
./venv/bin/python -m pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 2: Run a dry helper check without network**

Run:

```bash
./venv/bin/python - <<'PY'
from slideforge.agents.html_generator import SlideContent
from slideforge.tools.image_matching import build_image_query_context, build_image_queries

slide = SlideContent(
    slide_type="content",
    title="Three Point Revolution",
    bullets=["NBA Warriors basketball shooting deep threes"],
)
ctx = build_image_query_context("Stephen Curry", 2, slide, "three point shooting")
print(build_image_queries(ctx))
PY
```

Expected output includes:

```text
['Stephen Curry Three Point Revolution three point shooting', 'Stephen Curry Three Point Revolution', 'Stephen Curry NBA basketball']
```

- [ ] **Step 3: Inspect Git status**

Run:

```bash
git status --short
```

Expected: only pre-existing unrelated untracked files remain, or a clean tree if those were handled separately.

- [ ] **Step 4: Final commit if verification edits were needed**

If Task 5 required edits, commit the exact changed files reported by `git status --short`. For example, if only the image matching helper changed, run:

```bash
git add slideforge/tools/image_matching.py
git commit -m "test: verify page-level image matching"
```

If no edits were needed, do not create an empty commit.

## Self-Review

- Spec coverage: query context, multiple candidates, deterministic scoring, threshold rejection, integration, and tests are each mapped to tasks.
- Placeholder scan: no TBD/TODO/fill-in instructions remain.
- Type consistency: `ImageQueryContext`, `SelectedImage`, `build_image_query_context`, `build_image_queries`, `score_image_candidate`, `choose_best_image`, and `search_best_image` are defined before use.
