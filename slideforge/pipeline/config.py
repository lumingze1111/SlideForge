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
