"""Shared slide geometry helpers for measurement, layout, and assembly."""

from __future__ import annotations

SLIDE_W_PX = 1920
SLIDE_H_PX = 1080
SLIDE_W_EMU = 12192000
SLIDE_H_EMU = 6858000
PX_TO_EMU = SLIDE_W_EMU / SLIDE_W_PX
SIZE_SCALE = 1.5


def center_scaled_rect(x: float, y: float, w: float, h: float, scale: float = SIZE_SCALE) -> dict[str, float]:
    offset = (scale - 1.0) / 2.0
    return {
        "x": round(float(x) - float(w) * offset, 1),
        "y": round(float(y) - float(h) * offset, 1),
        "w": round(float(w) * scale, 1),
        "h": round(float(h) * scale, 1),
    }


def clamp_rect_to_slide(
    rect: dict[str, float],
    slide_w: int = SLIDE_W_PX,
    slide_h: int = SLIDE_H_PX,
) -> dict[str, float]:
    w = float(rect.get("w", 0))
    h = float(rect.get("h", 0))
    max_x = max(0.0, float(slide_w) - w)
    max_y = max(0.0, float(slide_h) - h)
    return {
        "x": max(0.0, min(float(rect.get("x", 0)), max_x)),
        "y": max(0.0, min(float(rect.get("y", 0)), max_y)),
        "w": w,
        "h": h,
    }
