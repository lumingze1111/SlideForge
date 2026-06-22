"""CSS parsing helpers used by the PPTX assembly engine."""

from __future__ import annotations

import re

from slideforge.pptx_engine.embed_fonts import (
    cjk_typefaces,
    family_alias_map,
    weighted_family_map,
)

FONT_FALLBACKS: dict[str, str] = {}
WEIGHTED_FONT_FALLBACKS: dict[tuple[str, int, bool], str] = {}
CJK_FONTS: set[str] = set()
_CJK_ALIAS_SET: set[str] = set()


GENERIC_FONT_KEYWORDS = {
    "serif", "sans-serif", "monospace", "cursive", "fantasy",
    "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace",
    "math", "emoji", "fangsong",
    "-apple-system", "blinkmacsystemfont", "-webkit-system-font",
}
DEFAULT_LATIN_FALLBACK = "Calibri"


def refresh_font_plan_caches():
    global FONT_FALLBACKS, WEIGHTED_FONT_FALLBACKS, CJK_FONTS, _CJK_ALIAS_SET
    FONT_FALLBACKS = family_alias_map()
    WEIGHTED_FONT_FALLBACKS = weighted_family_map()
    CJK_FONTS = cjk_typefaces()
    _CJK_ALIAS_SET = {name.lower() for name, tf in FONT_FALLBACKS.items() if tf in CJK_FONTS}


refresh_font_plan_caches()


def parse_text_shadow(value: str):
    if not value or value == "none":
        return None
    first = ""
    depth = 0
    for ch in value:
        if ch == "(":
            depth += 1
            first += ch
        elif ch == ")":
            depth -= 1
            first += ch
        elif ch == "," and depth == 0:
            break
        else:
            first += ch
    rgba_m = re.search(r"rgba?\(([^)]+)\)", first)
    color_rgba = (0, 0, 0, 1.0)
    if rgba_m:
        parts = [p.strip() for p in rgba_m.group(1).split(",")]
        if len(parts) >= 3:
            color_rgba = (
                int(float(parts[0])),
                int(float(parts[1])),
                int(float(parts[2])),
                float(parts[3]) if len(parts) >= 4 else 1.0,
            )
        first = re.sub(r"rgba?\([^)]+\)", "", first)
    nums = [float(m.group(1)) for m in re.finditer(r"(-?\d+\.?\d*)px", first)]
    if len(nums) < 2:
        return None
    dx, dy = nums[0], nums[1]
    blur = nums[2] if len(nums) >= 3 else 0.0
    return (dx, dy, blur, color_rgba)


def parse_rgb(s: str):
    return parse_rgba(s)[:3]


def _clamp_byte(value: float) -> int:
    return max(0, min(255, int(round(value))))


def parse_css_alpha(value: str | None) -> float:
    if value is None or value == "":
        return 1.0
    v = str(value).strip()
    try:
        if v.endswith("%"):
            return max(0.0, min(1.0, float(v[:-1]) / 100.0))
        return max(0.0, min(1.0, float(v)))
    except ValueError:
        return 1.0


def _parse_css_rgb_component(value: str, srgb_unit: bool = False) -> int:
    v = str(value).strip()
    if v.lower() == "none":
        return 0
    try:
        if v.endswith("%"):
            return _clamp_byte(float(v[:-1]) * 2.55)
        n = float(v)
    except ValueError:
        return 0
    if srgb_unit:
        return _clamp_byte(n * 255.0)
    return _clamp_byte(n)


def parse_rgba(s: str):
    if not s:
        return (0, 0, 0, 1.0)
    value = str(s).strip()
    if value in ("transparent", "rgba(0, 0, 0, 0)"):
        return (0, 0, 0, 0.0)
    if value.startswith("#"):
        hex_v = value[1:]
        if len(hex_v) in (3, 4):
            hex_v = "".join(ch * 2 for ch in hex_v)
        if len(hex_v) in (6, 8):
            try:
                r = int(hex_v[0:2], 16)
                g = int(hex_v[2:4], 16)
                b = int(hex_v[4:6], 16)
                a = int(hex_v[6:8], 16) / 255.0 if len(hex_v) == 8 else 1.0
                return (r, g, b, a)
            except ValueError:
                return (0, 0, 0, 1.0)

    m = re.match(r"rgba?\(([^)]+)\)", value)
    if m:
        body = m.group(1).strip()
        if "," in body:
            parts = [p.strip() for p in body.split(",")]
            rgb_parts = parts[:3]
            alpha_part = parts[3] if len(parts) >= 4 else None
        else:
            left, sep, right = body.partition("/")
            rgb_parts = [p for p in left.split() if p]
            alpha_part = right.strip() if sep else None
        if len(rgb_parts) >= 3:
            return (
                _parse_css_rgb_component(rgb_parts[0]),
                _parse_css_rgb_component(rgb_parts[1]),
                _parse_css_rgb_component(rgb_parts[2]),
                parse_css_alpha(alpha_part),
            )

    m = re.match(r"color\(\s*srgb\s+([^)]+)\)", value)
    if m:
        body = m.group(1).strip()
        left, sep, right = body.partition("/")
        parts = [p for p in left.split() if p]
        if len(parts) >= 3:
            return (
                _parse_css_rgb_component(parts[0], srgb_unit=True),
                _parse_css_rgb_component(parts[1], srgb_unit=True),
                _parse_css_rgb_component(parts[2], srgb_unit=True),
                parse_css_alpha(right.strip() if sep else None),
            )

    return (0, 0, 0, 1.0)


def first_font(font_family: str) -> str:
    items = [x.strip().strip('"').strip("'") for x in font_family.split(",")]
    for it in items:
        if not it or it.lower() in GENERIC_FONT_KEYWORDS:
            continue
        if it in FONT_FALLBACKS:
            return FONT_FALLBACKS[it]
        if it.lower() in FONT_FALLBACKS:
            return FONT_FALLBACKS[it.lower()]
        return it
    return DEFAULT_LATIN_FALLBACK
