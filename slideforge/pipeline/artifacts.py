"""Output artifact paths for a SlideForge generation run."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


def sanitize_topic_filename(topic: str, max_chars: int = 20) -> str:
    value = topic.strip().replace("/", "_").replace("\\", "_")
    value = value.replace("..", "")
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value)
    value = re.sub(r"_+", "_", value)
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
        html_stem = sanitize_topic_filename(topic, max_chars=9)
        pptx_stem = sanitize_topic_filename(topic, max_chars=20)
        return cls(
            output_dir=output_dir,
            html_path=output_dir / f"slides_{html_stem}.html",
            pptx_path=output_dir / f"slides_{pptx_stem}.pptx",
        )
