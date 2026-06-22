# PPTX Engine Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the maintenance risk of the large PPTX conversion engine by extracting focused, tested modules from `measure.py` and `assemble.py` without changing output behavior.

**Architecture:** Use a strangler-style refactor: create small modules for CSS/color parsing, measurement record filtering, and OOXML shape/text helpers, then update the large files to import those helpers. Each task preserves public entry points `measure()` and `assemble()` and is protected by targeted unit tests plus existing full tests.

**Tech Stack:** Python 3.11, existing Playwright measurement logic, python-pptx, lxml, pytest.

---

## File Map

- Create `slideforge/pptx_engine/css.py`: CSS color, alpha, font-family, and shadow parsing helpers currently embedded in `assemble.py`.
- Create `slideforge/pptx_engine/records.py`: measurement record classification and filtering helpers shared by measure/assemble/layout.
- Create `slideforge/pptx_engine/geometry.py`: slide constants, CSS-px to EMU conversion, center scaling, and bounds helpers.
- Modify `slideforge/pptx_engine/assemble.py`: import helpers from new modules while preserving existing function names as compatibility wrappers where needed.
- Modify `slideforge/pptx_engine/measure.py`: use record helpers for simple predicates; avoid moving browser JavaScript in this phase.
- Modify `slideforge/agents/layout_agent.py`: import geometry constants/functions instead of duplicating them.
- Create `tests/test_pptx_engine_css.py`: unit tests for CSS parsing behavior.
- Create `tests/test_pptx_engine_geometry.py`: unit tests for scaling and clamping behavior.
- Create `tests/test_pptx_engine_records.py`: unit tests for full-screen decoration filtering and text truncation.

## Task 1: Extract Shared Geometry Helpers

**Files:**
- Create: `slideforge/pptx_engine/geometry.py`
- Modify: `slideforge/agents/layout_agent.py`
- Test: `tests/test_pptx_engine_geometry.py`

- [ ] **Step 1: Write failing geometry tests**

Create `tests/test_pptx_engine_geometry.py`:

```python
from slideforge.pptx_engine.geometry import (
    PX_TO_EMU,
    SLIDE_H_EMU,
    SLIDE_H_PX,
    SLIDE_W_EMU,
    SLIDE_W_PX,
    center_scaled_rect,
    clamp_rect_to_slide,
)


def test_slide_constants_match_existing_16_9_mapping():
    assert SLIDE_W_PX == 1920
    assert SLIDE_H_PX == 1080
    assert SLIDE_W_EMU == 12192000
    assert SLIDE_H_EMU == 6858000
    assert PX_TO_EMU == 6350


def test_center_scaled_rect_matches_layout_agent_expectation():
    rect = center_scaled_rect(x=100, y=200, w=300, h=50, scale=1.5)

    assert rect == {"x": 25.0, "y": 187.5, "w": 450.0, "h": 75.0}


def test_clamp_rect_to_slide_keeps_rect_inside_bounds():
    rect = clamp_rect_to_slide({"x": 1850, "y": -20, "w": 600, "h": 100})

    assert rect == {"x": 1320.0, "y": 0.0, "w": 600.0, "h": 100.0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_pptx_engine_geometry.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'slideforge.pptx_engine.geometry'`.

- [ ] **Step 3: Add geometry module**

Create `slideforge/pptx_engine/geometry.py`:

```python
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
```

- [ ] **Step 4: Update layout agent to use geometry helpers**

Modify imports in `slideforge/agents/layout_agent.py`:

```python
from slideforge.pptx_engine.geometry import (
    SIZE_SCALE,
    SLIDE_H_PX,
    SLIDE_W_PX,
    center_scaled_rect,
    clamp_rect_to_slide,
)
```

Replace `_calc_init_rect()` implementation with:

```python
def _calc_init_rect(rx: float, ry: float, rw: float, rh: float) -> dict:
    """计算中心缩放 1.5× 后的初始 rect（与 assemble.py _scaled_rect 逻辑一致）。"""
    return center_scaled_rect(rx, ry, rw, rh, scale=SIZE_SCALE)
```

If `run_layout_agent()` contains local clamp logic, replace the local clamp expression with:

```python
clamped = clamp_rect_to_slide({"x": x, "y": y, "w": w, "h": h})
```

and return values from `clamped`.

- [ ] **Step 5: Run targeted tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_pptx_engine_geometry.py tests/test_layout_agent.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add slideforge/pptx_engine/geometry.py slideforge/agents/layout_agent.py tests/test_pptx_engine_geometry.py
git commit -m "refactor: extract pptx geometry helpers"
```

## Task 2: Extract CSS Parsing Helpers from Assembly

**Files:**
- Create: `slideforge/pptx_engine/css.py`
- Modify: `slideforge/pptx_engine/assemble.py`
- Test: `tests/test_pptx_engine_css.py`

- [ ] **Step 1: Write failing CSS parsing tests**

Create `tests/test_pptx_engine_css.py`:

```python
from slideforge.pptx_engine.css import (
    first_font,
    parse_css_alpha,
    parse_rgb,
    parse_rgba,
    parse_text_shadow,
)


def test_parse_rgba_accepts_hex_and_alpha_hex():
    assert parse_rgba("#336699") == (51, 102, 153, 1.0)
    assert parse_rgba("#33669980") == (51, 102, 153, 128 / 255)


def test_parse_rgba_accepts_modern_space_syntax():
    assert parse_rgba("rgb(10 20 30 / 50%)") == (10, 20, 30, 0.5)


def test_parse_css_alpha_defaults_to_one_for_invalid_values():
    assert parse_css_alpha(None) == 1.0
    assert parse_css_alpha("bad") == 1.0
    assert parse_css_alpha("25%") == 0.25


def test_parse_rgb_discards_alpha():
    assert parse_rgb("rgba(1, 2, 3, 0.4)") == (1, 2, 3)


def test_parse_text_shadow_handles_rgb_commas():
    assert parse_text_shadow("rgb(244, 208, 63) 4px 5px 0px") == (
        4.0,
        5.0,
        0.0,
        (244, 208, 63, 1.0),
    )


def test_first_font_skips_generic_family():
    assert first_font("system-ui, Calibri, sans-serif") == "Calibri"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_pptx_engine_css.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'slideforge.pptx_engine.css'`.

- [ ] **Step 3: Create `css.py` with copied behavior**

Create `slideforge/pptx_engine/css.py` by moving the following helpers from `slideforge/pptx_engine/assemble.py` without behavior changes:

```python
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
```

- [ ] **Step 4: Replace duplicate definitions in `assemble.py` with imports**

Modify the top section of `slideforge/pptx_engine/assemble.py`:

```python
from slideforge.pptx_engine.css import (
    CJK_FONTS,
    FONT_FALLBACKS,
    GENERIC_FONT_KEYWORDS,
    WEIGHTED_FONT_FALLBACKS,
    first_font,
    parse_css_alpha as _parse_css_alpha,
    parse_rgb,
    parse_rgba,
    parse_text_shadow,
    refresh_font_plan_caches,
)
```

Delete the duplicated definitions of these functions/constants from `assemble.py` after confirming all names still resolve:

```bash
rg -n "def parse_text_shadow|def parse_rgb|def _parse_css_alpha|def parse_rgba|def first_font|GENERIC_FONT_KEYWORDS|DEFAULT_LATIN_FALLBACK" slideforge/pptx_engine/assemble.py slideforge/pptx_engine/css.py
```

Expected after deletion: definitions only in `css.py`; imports/usages may remain in `assemble.py`.

- [ ] **Step 5: Run CSS and assembly-adjacent tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_pptx_engine_css.py tests/test_assemble_layout_agent.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 6: Run full tests**

Run:

```bash
./venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add slideforge/pptx_engine/css.py slideforge/pptx_engine/assemble.py tests/test_pptx_engine_css.py
git commit -m "refactor: extract pptx css parsing helpers"
```

## Task 3: Extract Measurement Record Helpers

**Files:**
- Create: `slideforge/pptx_engine/records.py`
- Modify: `slideforge/agents/layout_agent.py`
- Test: `tests/test_pptx_engine_records.py`

- [ ] **Step 1: Write failing record helper tests**

Create `tests/test_pptx_engine_records.py`:

```python
from slideforge.pptx_engine.records import (
    build_layout_element,
    is_fullscreen_deco,
    truncate_text,
)


def test_is_fullscreen_deco_matches_existing_layout_behavior():
    assert is_fullscreen_deco(
        {"kind": "deco_snapshot", "rect": {"x": 0, "y": 0, "w": 1920, "h": 1080}}
    )
    assert not is_fullscreen_deco(
        {"kind": "deco_snapshot", "rect": {"x": 10, "y": 10, "w": 400, "h": 300}}
    )


def test_truncate_text_uses_existing_ellipsis_behavior():
    assert truncate_text("短文本", max_len=40) == "短文本"
    assert truncate_text("A" * 45, max_len=40) == "A" * 40 + "…"


def test_build_layout_element_includes_orig_and_init_rects():
    element = build_layout_element(
        {"id": "7", "kind": "text", "tag": "h1", "text": "标题", "fontSize": 24, "rect": {"x": 100, "y": 200, "w": 300, "h": 50}}
    )

    assert element == {
        "id": "7",
        "kind": "text",
        "tag": "h1",
        "text": "标题",
        "fontSize": 24,
        "orig": {"x": 100, "y": 200, "w": 300, "h": 50},
        "init": {"x": 25.0, "y": 187.5, "w": 450.0, "h": 75.0},
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_pptx_engine_records.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'slideforge.pptx_engine.records'`.

- [ ] **Step 3: Add record helper module**

Create `slideforge/pptx_engine/records.py`:

```python
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
```

- [ ] **Step 4: Update layout agent to use record helpers**

Modify imports in `slideforge/agents/layout_agent.py`:

```python
from slideforge.pptx_engine.records import (
    build_layout_element,
    is_fullscreen_deco,
    truncate_text as _truncate,
)
```

Delete the local `is_fullscreen_deco()` body and keep a compatibility wrapper only if existing tests import it directly:

```python
def is_fullscreen_deco(rec: dict) -> bool:
    """判断是否全屏 deco_snapshot（应跳过）。"""
    from slideforge.pptx_engine.records import is_fullscreen_deco as _is_fullscreen_deco

    return _is_fullscreen_deco(rec)
```

Replace `_build_element_list()` loop body with:

```python
    elements = []
    for rec in records:
        if is_fullscreen_deco(rec):
            continue
        elements.append(build_layout_element(rec))
    return elements
```

- [ ] **Step 5: Run targeted tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_pptx_engine_records.py tests/test_layout_agent.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add slideforge/pptx_engine/records.py slideforge/agents/layout_agent.py tests/test_pptx_engine_records.py
git commit -m "refactor: extract pptx record helpers"
```

## Task 4: Import Geometry Constants into Assembly

**Files:**
- Modify: `slideforge/pptx_engine/assemble.py`
- Test: `tests/test_pptx_engine_geometry.py`
- Test: `tests/test_assemble_layout_agent.py`

- [ ] **Step 1: Add an assembly constant regression test**

Append to `tests/test_pptx_engine_geometry.py`:

```python
def test_assemble_uses_shared_geometry_constants():
    from slideforge.pptx_engine import assemble

    assert assemble.SLIDE_W_PX == SLIDE_W_PX
    assert assemble.SLIDE_H_PX == SLIDE_H_PX
    assert assemble.SLIDE_W_EMU == SLIDE_W_EMU
    assert assemble.SLIDE_H_EMU == SLIDE_H_EMU
    assert assemble.PX_TO_EMU == PX_TO_EMU
```

- [ ] **Step 2: Run test before modification**

Run:

```bash
./venv/bin/python -m pytest tests/test_pptx_engine_geometry.py::test_assemble_uses_shared_geometry_constants -q
```

Expected: PASS before modification; this guards compatibility.

- [ ] **Step 3: Import shared constants in `assemble.py`**

At the top of `slideforge/pptx_engine/assemble.py`, replace local constant assignments:

```python
SLIDE_W_PX = 1920
SLIDE_H_PX = 1080
SLIDE_W_EMU = 12192000
SLIDE_H_EMU = 6858000
PX_TO_EMU = SLIDE_W_EMU / SLIDE_W_PX
SIZE_SCALE = 1.5
```

with:

```python
from slideforge.pptx_engine.geometry import (
    PX_TO_EMU,
    SIZE_SCALE,
    SLIDE_H_EMU,
    SLIDE_H_PX,
    SLIDE_W_EMU,
    SLIDE_W_PX,
    center_scaled_rect,
)
```

If `assemble.py` has a local `_scaled_rect()` helper, update it to delegate:

```python
def _scaled_rect(x, y, w, h):
    rect = center_scaled_rect(x, y, w, h, scale=SIZE_SCALE)
    return rect["x"], rect["y"], rect["w"], rect["h"]
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_pptx_engine_geometry.py tests/test_assemble_layout_agent.py -q
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
git add slideforge/pptx_engine/assemble.py tests/test_pptx_engine_geometry.py
git commit -m "refactor: share pptx geometry constants"
```

## Task 5: Add a Minimal HTML-to-PPTX Smoke Test Fixture

**Files:**
- Create: `tests/fixtures/simple_slides.html`
- Create: `tests/test_pptx_converter_smoke.py`

- [ ] **Step 1: Create simple HTML fixture**

Create `tests/fixtures/simple_slides.html`:

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { margin: 0; }
    .slide {
      width: 1920px;
      height: 1080px;
      position: relative;
      background: #ffffff;
      color: #111827;
      font-family: Arial, sans-serif;
    }
    h1 {
      position: absolute;
      left: 160px;
      top: 180px;
      font-size: 72px;
    }
    p {
      position: absolute;
      left: 160px;
      top: 320px;
      font-size: 34px;
    }
  </style>
</head>
<body>
  <div class="slide" data-pptx-slide data-notes="Speaker notes">
    <h1>Smoke Test</h1>
    <p>SlideForge conversion fixture</p>
  </div>
</body>
</html>
```

- [ ] **Step 2: Write smoke test**

Create `tests/test_pptx_converter_smoke.py`:

```python
import zipfile
from pathlib import Path

from slideforge.pptx_converter import convert_html_to_pptx


def test_convert_simple_html_to_pptx_smoke(tmp_path):
    html = Path("tests/fixtures/simple_slides.html")
    output = tmp_path / "simple.pptx"

    convert_html_to_pptx(
        str(html),
        str(output),
        verbose=False,
        validate_gradients=False,
        audit=False,
    )

    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "ppt/slides/slide1.xml" in names
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "Smoke Test" in slide_xml
```

- [ ] **Step 3: Run smoke test**

Run:

```bash
./venv/bin/python -m pytest tests/test_pptx_converter_smoke.py -q
```

Expected: PASS if Playwright browser dependencies are available. If it fails with a browser installation error, record the exact failure in the commit message body and keep the fixture/test marked with `pytest.importorskip("playwright")` only if Playwright is not importable.

- [ ] **Step 4: Run full tests**

Run:

```bash
./venv/bin/python -m pytest -q
```

Expected: all tests pass in the current environment.

- [ ] **Step 5: Commit**

Run:

```bash
git add tests/fixtures/simple_slides.html tests/test_pptx_converter_smoke.py
git commit -m "test: add html to pptx smoke coverage"
```

## Self-Review

- Spec coverage: This plan covers priority 3 by extracting geometry, CSS parsing, and record helpers first, then protecting the conversion path with a smoke test.
- Placeholder scan: The plan avoids placeholder-only instructions; inspection and migration steps include exact commands and expected outcomes.
- Type consistency: New helper names are defined before being imported into `layout_agent.py` or `assemble.py`, and compatibility wrappers preserve existing function imports during the transition.
