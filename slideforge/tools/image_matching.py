"""
Deterministic page-level image matching helpers.

This module has no network calls. It turns slide content into search queries
and scores provider metadata before any image is downloaded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

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
