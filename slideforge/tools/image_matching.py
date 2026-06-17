"""
Deterministic page-level image matching helpers.

This module has no network calls. It turns slide content into search queries
and scores provider metadata before any image is downloaded.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from slideforge.agents.html_generator import SlideContent
from slideforge.tools.image_search import ImageSearchError


@dataclass(frozen=True)
class ImageQueryContext:
    topic: str
    slide_index: int
    slide_type: str
    slide_title: str
    slide_text: str
    requested_keywords: str = ""


@dataclass(frozen=True)
class SelectedImage:
    image: object
    image_path: Path


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
