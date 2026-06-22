"""Helpers for measured PPTX records."""

from __future__ import annotations

from slideforge.pptx_engine.geometry import SLIDE_H_PX, SLIDE_W_PX, center_scaled_rect


def is_fullscreen_deco(rec: dict, slide_w: int = SLIDE_W_PX, slide_h: int = SLIDE_H_PX) -> bool:
    if rec.get("kind") != "deco_snapshot":
        return False
    rect = rec.get("rect", {})
    return rect.get("w", 0) >= slide_w * 0.99 and rect.get("h", 0) >= slide_h * 0.99


def truncate_text(text: str, max_len: int = 40) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def build_layout_element(rec: dict) -> dict:
    rect = rec.get("rect", {})
    element = {
        "id": str(rec.get("id", "")),
        "kind": rec.get("kind", ""),
        "tag": rec.get("tag", ""),
    }
    text = rec.get("text", "")
    if text:
        element["text"] = truncate_text(text)
    font_size = rec.get("fontSize", 0)
    if font_size:
        element["fontSize"] = font_size
    element["orig"] = {
        "x": rect.get("x", 0),
        "y": rect.get("y", 0),
        "w": rect.get("w", 0),
        "h": rect.get("h", 0),
    }
    element["init"] = center_scaled_rect(
        rect.get("x", 0),
        rect.get("y", 0),
        rect.get("w", 0),
        rect.get("h", 0),
    )
    return element
