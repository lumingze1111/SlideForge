# Layout Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an LLM-powered Layout Agent that intelligently adjusts element positions after 1.5× center scaling, replacing the current mechanical `_clamp_to_slide` that causes overlaps and broken column relationships.

**Architecture:** LangGraph `create_react_agent` with two tools (`get_slide_elements`, `check_layout`). Called once per slide in `assemble_slide()`, after `_prepare_text_layouts()`. Falls back to `_scaled_rect` on agent failure.

**Tech Stack:** `langgraph` + `ChatOpenAI` + Pydantic (existing project pattern), Fallback uses existing `_scaled_rect` + `_clamp_to_slide`.

---

### Task 1: Create the Layout Agent module

**Files:**
- Create: `slideforge/agents/layout_agent.py`

- [ ] **Step 1: Write the failing tests**

Create test file for the Layout Agent:

```python
# tests/test_layout_agent.py
"""Tests for Layout Agent module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from slideforge.agents.layout_agent import (
    LayoutAdjustment,
    SlideElement,
    get_slide_elements,
    check_layout,
    create_layout_agent,
    run_layout_agent,
)


class TestSlideElement:
    def test_skip_deco_fullscreen(self):
        """Full-screen deco_snapshot should be excluded from elements list."""
        records = [
            {"id": "0", "kind": "deco_snapshot", "rect": {"x": 0, "y": 0, "w": 1920, "h": 1080}},
            {"id": "1", "kind": "text", "rect": {"x": 100, "y": 100, "w": 200, "h": 50},
             "text": "Hello", "tag": "h1", "fontSize": 24},
        ]
        elements = get_slide_elements(records, 1920, 1080)
        # deco_snapshot should be filtered out
        assert len(elements) == 1
        assert elements[0]["id"] == "1"

    def test_rect_format(self):
        """Each element should have id, kind, orig, init fields."""
        records = [
            {"id": "0", "kind": "text", "rect": {"x": 100, "y": 200, "w": 300, "h": 50},
             "text": "Title", "tag": "h1", "fontSize": 24},
        ]
        elements = get_slide_elements(records, 1920, 1080)
        el = elements[0]
        assert "id" in el
        assert "orig" in el
        assert "init" in el
        # init should be the center-scaled version
        # orig: (100, 200, 300, 50)
        # offset = (1.5-1)/2 = 0.25
        # init_x = 100 - 300*0.25 = 25
        # init_y = 200 - 50*0.25 = 187.5
        # init_w = 300*1.5 = 450
        # init_h = 50*1.5 = 75
        assert el["init"]["x"] == 25
        assert el["init"]["y"] == 187.5
        assert el["init"]["w"] == 450
        assert el["init"]["h"] == 75


class TestCheckLayout:
    def test_clean_layout(self):
        """All elements within slide bounds and no overlap → score 100."""
        adjustments = {
            "0": {"x": 0, "y": 0, "w": 100, "h": 100},
            "1": {"x": 200, "y": 0, "w": 100, "h": 100},
        }
        result = check_layout(adjustments, 1920, 1080)
        assert result["overflow_count"] == 0
        assert result["overlap_count"] == 0
        assert result["score"] == 100

    def test_overflow_detected(self):
        """Element past right edge should count as overflow."""
        adjustments = {
            "0": {"x": 1900, "y": 0, "w": 100, "h": 50},
        }
        result = check_layout(adjustments, 1920, 1080)
        assert result["overflow_count"] == 1
        assert result["score"] == 90  # 100 - 1*10

    def test_overlap_detected(self):
        """Two overlapping elements should be detected."""
        adjustments = {
            "0": {"x": 0, "y": 0, "w": 200, "h": 100},
            "1": {"x": 50, "y": 0, "w": 200, "h": 100},
        }
        result = check_layout(adjustments, 1920, 1080)
        assert result["overlap_count"] == 1
        assert result["score"] == 95  # 100 - 1*5

    def test_text_truncation(self):
        """Text longer than 40 chars should be truncated in elements."""
        records = [
            {"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 20},
             "text": "A" * 100, "tag": "p", "fontSize": 16},
        ]
        elements = get_slide_elements(records, 1920, 1080)
        assert len(elements[0]["text"]) <= 42  # 40 + "..."

    def test_invalid_adjustments_still_checked(self):
        """check_layout should handle elements partly outside slide."""
        adjustments = {
            "0": {"x": -10, "y": 0, "w": 100, "h": 50},
        }
        result = check_layout(adjustments, 1920, 1080)
        assert result["overflow_count"] >= 1


class TestRunLayoutAgent:
    def test_agent_returns_adjustments(self):
        """run_layout_agent should return a dict mapping id -> (x,y,w,h)."""
        mock_llm = MagicMock()
        mock_agent = MagicMock()

        # Mock the agent invoke to return a valid response
        mock_result = {
            "messages": [
                HumanMessage(content=""),
                MagicMock(content=json.dumps({
                    "adjustments": {
                        "0": {"x": 0, "y": 0, "w": 100, "h": 50},
                        "1": {"x": 150, "y": 0, "w": 200, "h": 100},
                    },
                    "reasoning": "Left justified, no overlap."
                })),
            ]
        }
        mock_agent.invoke.return_value = mock_result

        records = [
            {"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
             "text": "Hello", "tag": "h1", "fontSize": 24},
            {"id": "1", "kind": "shape", "rect": {"x": 100, "y": 0, "w": 200, "h": 100},
             "tag": "div"},
        ]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1)
            assert "0" in result
            assert "1" in result
            assert result["0"] == (0, 0, 100, 50)

    def test_empty_result_fallback(self):
        """Empty adjustments dict should trigger fallback (return empty)."""
        mock_llm = MagicMock()
        mock_agent = MagicMock()

        mock_result = {
            "messages": [MagicMock(content="{}")],
        }
        mock_agent.invoke.return_value = mock_result

        records = [{"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
                     "text": "Hi", "tag": "p", "fontSize": 16}]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1)
            assert result == {}  # empty = use _scaled_rect

    def test_exception_fallback(self):
        """LLM exception should return empty dict (fallback)."""
        mock_llm = MagicMock()
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = Exception("API error")

        records = [{"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
                     "text": "Hi", "tag": "p", "fontSize": 16}]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1)
            assert result == {}

    def test_no_improvement_fallback(self):
        """Stagnant score should trigger early exit (return empty)."""
        mock_llm = MagicMock()
        mock_agent = MagicMock()

        # Always return the same low-score layout
        responses = iter([
            {"messages": [MagicMock(content=json.dumps({
                "adjustments": {"0": {"x": 0, "y": 0, "w": 1920, "h": 1080}},
                "reasoning": "full slide",
            }))]},
            {"messages": [MagicMock(content=json.dumps({
                "adjustments": {"0": {"x": 0, "y": 0, "w": 1920, "h": 1080}},
                "reasoning": "still full slide",
            }))]},
        ])
        mock_agent.invoke.side_effect = lambda x: next(responses)

        records = [{"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
                     "text": "Hi", "tag": "p", "fontSize": 16}]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1)
            assert result == {}  # no improvement → fallback

    def test_timeout_fallback(self):
        """Response exceeding time limit should return empty."""
        import time
        mock_llm = MagicMock()
        mock_agent = MagicMock()

        real_sleep = time.sleep
        def delayed_invoke(x):
            real_sleep(0.05)
            return {"messages": [MagicMock(content=json.dumps({
                "adjustments": {"0": {"x": 0, "y": 0, "w": 50, "h": 25}},
            }))]}

        mock_agent.invoke.side_effect = delayed_invoke

        records = [{"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
                     "text": "Hi", "tag": "p", "fontSize": 16}]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1, timeout_ms=30)
            # With 30ms timeout and 50ms invoke, should time out and return empty
            assert result == {}
```

Run tests to confirm they fail:

```bash
cd /Users/lumingze/Desktop/SlideForge
python -m pytest tests/test_layout_agent.py -v
```
Expected: FAIL with `ModuleNotFoundError` (no module yet).

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/lumingze/Desktop/SlideForge
python -m pytest tests/test_layout_agent.py -v 2>&1 | head -20
```
Expected: Module not found error for `slideforge.agents.layout_agent`.

- [ ] **Step 3: Write the Layout Agent module**

```python
# slideforge/agents/layout_agent.py
"""Layout Agent — 逐页分析幻灯片元素布局，智能调整 1.5× 缩放后的位置。

LLM Agent（LangGraph ReAct 循环）：
1. get_slide_elements() → 查看当前布局
2. 自主分析分组 / 列 / 行结构
3. 输出 adjustments → 调整方案
4. check_layout() → 验证是否还有溢出/重叠
5. 如有问题 → 回退重新调整

输出：{record_id: {x, y, w, h}} 绝对坐标（CSS px）
Assembly 阶段再转 EMU。
"""

import json
import logging
import time
from typing import Any

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SIZE_SCALE = 1.5
SLIDE_W_PX = 1920
SLIDE_H_PX = 1080

SYSTEM_PROMPT = """你是专业幻灯片布局设计师，负责在 1.5× 缩放后调整元素位置，避免溢出和重叠。

工作流程：
1. 调用 get_slide_elements() 查看当前页面所有元素及其布局信息
2. 分析元素的分组、列、行关系
3. 输出调整方案（绝对坐标 x/y/w/h，CSS px 单位）
4. 如果后续需要查看结果可用 check_layout() 验证

关键设计原则：
- 保持原有视觉节奏（对齐、间距、分组关系）
- 同类元素（同列/同行）保持对齐
- 元素不应超出幻灯片边界 [0,{SLIDE_W_PX}] × [0,{SLIDE_H_PX}]
- 全屏覆盖的 deco_snapshot 已在输入中跳过
- 文字留 12% 余量（textbox 已比 rect 宽 12%）

输出 JSON 格式（不要加代码块标记，直接输出）：
{{
  "adjustments": {{
    "0": {{"x": 0, "y": 0, "w": 100, "h": 50}},
    "1": {{"x": 200, "y": 0, "w": 400, "h": 100}}
  }},
  "reasoning": "左栏3个元素等距排列，右栏保持水平对齐..."
}}

注意：
- adjustments 中不出现的元素保持原位置
- 输出必须是合法 JSON，不要包含额外说明文字
""".format(SLIDE_W_PX=SLIDE_W_PX, SLIDE_H_PX=SLIDE_H_PX)


def _calc_init_rect(rx: float, ry: float, rw: float, rh: float) -> dict:
    """计算中心缩放 1.5× 后的初始 rect（与 assemble.py _scaled_rect 逻辑一致）。"""
    offset = (SIZE_SCALE - 1.0) / 2.0  # 0.25
    return {
        "x": round(rx - rw * offset, 1),
        "y": round(ry - rh * offset, 1),
        "w": round(rw * SIZE_SCALE, 1),
        "h": round(rh * SIZE_SCALE, 1),
    }


def _truncate(text: str, max_len: int = 40) -> str:
    """截断文本到 max_len + "..."。"""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def is_fullscreen_deco(rec: dict) -> bool:
    """判断是否全屏 deco_snapshot（应跳过）。"""
    if rec.get("kind") != "deco_snapshot":
        return False
    r = rec.get("rect", {})
    return r.get("w", 0) >= SLIDE_W_PX * 0.99 and r.get("h", 0) >= SLIDE_H_PX * 0.99


# ── Tools ─────────────────────────────────────────────────────────────────────

# Module-level state for tools (set by run_layout_agent)
_CURRENT_RECORDS: list[dict] = []
_CURRENT_SLIDE_W: int = SLIDE_W_PX
_CURRENT_SLIDE_H: int = SLIDE_H_PX


@tool
def get_slide_elements() -> str:
    """查看当前幻灯片所有元素的结构化列表（id, kind, 位置rect, 文本等）。"""
    elements = _build_element_list(_CURRENT_RECORDS, _CURRENT_SLIDE_W, _CURRENT_SLIDE_H)
    if not elements:
        return "当前幻灯片无可见元素。"
    lines = [json.dumps(el, ensure_ascii=False) for el in elements]
    return "[\n" + ",\n".join(lines) + "\n]"


@tool
def check_layout(adjustments_json: str) -> str:
    """验证调整后的布局是否有溢出或重叠。接收 adjustments JSON 字符串。"""
    try:
        adjustments = json.loads(adjustments_json)
    except json.JSONDecodeError as e:
        return f"JSON 解析失败: {e}"
    result = _check_layout_core(adjustments, _CURRENT_SLIDE_W, _CURRENT_SLIDE_H)
    return json.dumps(result, ensure_ascii=False)


def _build_element_list(records: list[dict], slide_w: int, slide_h: int) -> list[dict]:
    """从 records 构建 LLM 可见的元素列表（跳过全屏 deco_snapshot）。"""
    elements = []
    for rec in records:
        if is_fullscreen_deco(rec):
            continue
        r = rec.get("rect", {})
        init_rect = _calc_init_rect(r.get("x", 0), r.get("y", 0),
                                     r.get("w", 0), r.get("h", 0))
        el = {
            "id": str(rec.get("id", "")),
            "kind": rec.get("kind", ""),
            "tag": rec.get("tag", ""),
        }
        text = rec.get("text", "")
        if text:
            el["text"] = _truncate(text)
        fs = rec.get("fontSize", 0)
        if fs:
            el["fontSize"] = fs
        el["orig"] = {"x": r.get("x", 0), "y": r.get("y", 0),
                       "w": r.get("w", 0), "h": r.get("h", 0)}
        el["init"] = init_rect
        elements.append(el)
    return elements


def _check_layout_core(adjustments: dict, slide_w: int, slide_h: int) -> dict:
    """检查调整后的布局是否有溢出或重叠。

    返回：
    {
        "overflow_count": int,
        "overflow_elements": [str, ...],
        "overlap_count": int,
        "overlap_pairs": [[id1, id2], ...],
        "score": int  # 100 - overflow*10 - overlap*5
    }
    """
    overflow_count = 0
    overflow_elements = []
    overlap_count = 0
    overlap_pairs = []
    ids = sorted(adjustments.keys())

    # 检查溢出
    for eid in ids:
        a = adjustments[eid]
        issues = []
        if a["x"] < 0:
            issues.append(f"左边溢出({a['x']}px)")
        if a["y"] < 0:
            issues.append(f"上边溢出({a['y']}px)")
        if a["x"] + a["w"] > slide_w:
            issues.append(f"右边溢出({a['x']+a['w']-slide_w}px)")
        if a["y"] + a["h"] > slide_h:
            issues.append(f"下边溢出({a['y']+a['h']-slide_h}px)")
        if issues:
            overflow_count += 1
            overflow_elements.append(f"元素{eid}: {'; '.join(issues)}")

    # 检查重叠（AABB 相交检测）
    boxes = {}
    for eid in ids:
        a = adjustments[eid]
        boxes[eid] = (a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"])

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            id1, id2 = ids[i], ids[j]
            x1, y1, x1r, y1b = boxes[id1]
            x2, y2, x2r, y2b = boxes[id2]
            # AABB overlap
            if x1 < x2r and x1r > x2 and y1 < y2b and y1b > y2:
                overlap_count += 1
                overlap_pairs.append([id1, id2])

    score = max(0, 100 - overflow_count * 10 - overlap_count * 5)
    return {
        "overflow_count": overflow_count,
        "overflow_elements": overflow_elements,
        "overlap_count": overlap_count,
        "overlap_pairs": overlap_pairs,
        "score": score,
    }


def _parse_agent_response(content: str) -> dict | None:
    """从 LLM 响应中提取 adjustments JSON。"""
    if not content:
        return None
    text = content.strip()
    # 去除可能的代码块标记
    if "```" in text:
        for chunk in text.split("```"):
            chunk = chunk.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{"):
                text = chunk
                break
    # 找第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    text = text[start:end+1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    adjustments = data.get("adjustments")
    if not adjustments or not isinstance(adjustments, dict):
        return None
    # 校验每个 adjustment
    validated = {}
    for eid, adj in adjustments.items():
        if not isinstance(adj, dict):
            continue
        x, y, w, h = adj.get("x"), adj.get("y"), adj.get("w"), adj.get("h")
        if None in (x, y, w, h):
            continue
        validated[eid] = {"x": float(x), "y": float(y),
                          "w": float(w), "h": float(h)}
    return validated if validated else None


def create_layout_agent(llm: ChatOpenAI):
    """创建 Layout ReAct Agent。"""
    tools = [get_slide_elements, check_layout]
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


def run_layout_agent(
    llm: ChatOpenAI,
    records: list[dict],
    slide_index: int = 0,
    timeout_ms: int = 30000,
) -> dict[str, tuple[float, float, float, float]]:
    """对一张 slide 运行 Layout Agent。

    Args:
        llm: ChatOpenAI 实例。
        records: 当前 slide 的 records 列表（需要含 "id" 字段）。
        slide_index: 幻灯片序号（仅用于日志）。
        timeout_ms: 超时毫秒数。

    Returns:
        {record_id: (x, y, w, h)} 调整后的坐标。
        返回空 dict 表示应 fallback 到 _scaled_rect。
    """
    global _CURRENT_RECORDS, _CURRENT_SLIDE_W, _CURRENT_SLIDE_H
    _CURRENT_RECORDS = records
    _CURRENT_SLIDE_W = SLIDE_W_PX
    _CURRENT_SLIDE_H = SLIDE_H_PX

    # 构造元素摘要（让 LLM 在第一步就看全貌）
    elements = _build_element_list(records, SLIDE_W_PX, SLIDE_H_PX)
    if not elements:
        return {}

    agent = create_layout_agent(llm)
    elements_json = json.dumps(elements, ensure_ascii=False)

    user_msg = (
        f"当前页面 {SLIDE_W_PX}×{SLIDE_H_PX}，共 {len(elements)} 个可见元素。\n\n"
        f"请先调用 get_slide_elements() 查看完整元素列表，然后输出调整方案。\n\n"
        f"元素摘要：\n{elements_json}"
    )

    start_time = time.perf_counter()
    best_adjustments: dict | None = None
    best_score = -1
    stagnant_rounds = 0
    max_rounds = 3

    for round_idx in range(max_rounds):
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if elapsed_ms > timeout_ms:
            logger.warning(f"[layout_agent] slide {slide_index} 超时 ({elapsed_ms:.0f}ms)，fallback")
            return {}

        try:
            result = agent.invoke({"messages": [HumanMessage(content=user_msg)]})
        except Exception as e:
            logger.warning(f"[layout_agent] slide {slide_index} LLM 调用异常: {e}，fallback")
            return {}

        final_text = result["messages"][-1].content
        parsed = _parse_agent_response(final_text)

        if not parsed:
            logger.warning(f"[layout_agent] slide {slide_index} 第{round_idx+1}轮响应非法，fallback")
            return {}

        # 用 check_layout 验证当前方案
        check = _check_layout_core(parsed, SLIDE_W_PX, SLIDE_H_PX)
        score = check["score"]

        if score > best_score:
            best_adjustments = parsed
            best_score = score
            stagnant_rounds = 0
        else:
            stagnant_rounds += 1

        if score >= 90:
            # 足够好了
            break

        if stagnant_rounds >= 2:
            # 连续 2 轮无提升
            if best_adjustments:
                break
            return {}

        # 给 agent 反馈，继续迭代
        user_msg = (
            f"第{round_idx+2}轮调整。当前方案检查结果：\n"
            f"{json.dumps(check, ensure_ascii=False)}\n\n"
            f"请根据以上反馈精调位置。"
        )

    if best_adjustments is None:
        return {}

    # 转换为 {id: (x, y, w, h)} tuple 格式
    result = {}
    for eid, adj in best_adjustments.items():
        result[eid] = (adj["x"], adj["y"], adj["w"], adj["h"])
    return result
```

- [ ] **Step 4: Verify the module parses correctly**

```bash
cd /Users/lumingze/Desktop/SlideForge
python -c "import ast; ast.parse(open('slideforge/agents/layout_agent.py').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/lumingze/Desktop/SlideForge
python -m pytest tests/test_layout_agent.py -v
```
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add slideforge/agents/layout_agent.py tests/test_layout_agent.py
git commit -m "feat: add Layout Agent module for intelligent 1.5x scaling position adjustment

LLM-powered per-slide layout optimization using LangGraph ReAct pattern.
Replaces mechanical _clamp_to_slide with context-aware repositioning.
Falls back to _scaled_rect on failure."
```

---

### Task 2: Integrate Layout Agent into assemble.py

**Files:**
- Modify: `slideforge/pptx_engine/assemble.py` (around `assemble_slide()`)

- [ ] **Step 1: Write the integration tests**

Add to the test file:

```python
# tests/test_assemble_layout_agent.py
"""Tests for Layout Agent integration in assemble.py."""

from unittest.mock import MagicMock, patch

import pytest

from slideforge.pptx_engine.assemble import assemble_slide


class FakeSlide:
    """Minimal slide mock for integration testing."""
    def __init__(self):
        self.shapes = FakeShapes()
        self.background = FakeFill()
        self._element = FakeElement()

    @property
    def notes_slide(self):
        raise AttributeError("no notes")


class FakeShapes:
    def __init__(self):
        self._shapes = []

    def add_shape(self, mso_type, x, y, w, h):
        s = FakeShape(x, y, w, h)
        self._shapes.append(s)
        return s

    def add_textbox(self, x, y, w, h):
        tb = FakeTextbox(x, y, w, h)
        self._shapes.append(tb)
        return tb

    def add_picture(self, path, x, y, w, h):
        return FakePicture(x, y, w, h)

    def add_connector(self, typ, x1, y1, x2, y2):
        return FakeConnector()

    def __iter__(self):
        return iter(self._shapes)

    def __len__(self):
        return len(self._shapes)


class FakeFill:
    def solid(self):
        pass
    def background(self):
        pass


class FakeForeColor:
    rgb = None


class FakeElement:
    tag = "p:sp"
    def find(self, *a):
        return None
    def findall(self, *a):
        return []


class FakeShape:
    def __init__(self, x, y, w, h):
        self.left = x
        self.top = y
        self.width = w
        self.height = h
        self.fill = FakeFill()
        self.line = FakeLine()
        self._element = FakeElement()
        self.adjustments = []

    @property
    def fill(self):
        return FakeFill()


class FakeLine:
    def __init__(self):
        self.fill = FakeFill()
        self.color = FakeForeColor()
        self.width = 0


class FakeTextbox(FakeShape):
    def __init__(self, x, y, w, h):
        super().__init__(x, y, w, h)
        self.text_frame = FakeTextFrame()


class FakeTextFrame:
    def __init__(self):
        self.paragraphs = [FakeParagraph()]
        self.word_wrap = True
        self.margin_left = 0
        self.margin_right = 0
        self.margin_top = 0
        self.margin_bottom = 0
        self._txBody = FakeTxBody()


class FakeTxBody:
    def find(self, *a):
        return FakeElement()


class FakeParagraph:
    def __init__(self):
        self._p = FakeP()
        self._pPr = None


class FakeP:
    def find(self, *a):
        return None
    def findall(self, *a):
        return []
    def remove(self, *a):
        pass
    def get_or_add_pPr(self):
        el = FakeElement()
        self._pPr = el
        return el


class FakeConnector:
    pass


class FakePicture:
    def __init__(self, x, y, w, h):
        self.left = x
        self.top = y
        self.width = w
        self.height = h


def test_assemble_with_layout_agent():
    """assemble_slide should use _adjusted_rect when agent provides adjustments."""
    slide = FakeSlide()
    data = {
        "slide": {"background": "rgb(255,255,255)", "backgroundImage": "", "theme": "light"},
        "records": [
            {
                "id": "0",
                "kind": "text", "tag": "h1",
                "rect": {"x": 100, "y": 50, "w": 400, "h": 60},
                "text": "Hello World", "fontSize": 24,
                "_adjusted_rect": (50, 30, 500, 80),  # Agent-adjusted
            },
        ],
    }

    # Mock add_background to do nothing
    with patch("slideforge.pptx_engine.assemble.add_background"):
        assemble_slide(slide, data)

    # The agent-adjusted rect should be used: (50, 30, 500, 80) in px
    # Convert to EMU: 50*6350=317500, 30*6350=190500, 500*6350*1.5=4762500, 80*6350*1.5=762000
    expected_x = int(50 * 6350)
    expected_y = int(30 * 6350)
    expected_w = int(500 * 6350 * 1.5)
    expected_h = int(80 * 6350 * 1.5)

    # Check that the textbox used the adjusted values (approximately)
    for shape in slide.shapes._shapes:
        if hasattr(shape, 'text_frame'):
            assert abs(shape.left - expected_x) < 1000, f"Expected x~{expected_x}, got {shape.left}"
            assert abs(shape.top - expected_y) < 1000, f"Expected y~{expected_y}, got {shape.top}"
            break


def test_assemble_fallback_without_adjustment():
    """Without _adjusted_rect, assemble_slide falls back to _scaled_rect."""
    slide = FakeSlide()
    data = {
        "slide": {"background": "rgb(255,255,255)", "backgroundImage": "", "theme": "light"},
        "records": [
            {
                "id": "0",
                "kind": "text", "tag": "h1",
                "rect": {"x": 100, "y": 50, "w": 400, "h": 60},
                "text": "Hello World", "fontSize": 24,
                # No _adjusted_rect → uses _scaled_rect
            },
        ],
    }

    with patch("slideforge.pptx_engine.assemble.add_background"):
        assemble_slide(slide, data)

    # Should produce at least one shape (no crash = fallback works)
    assert len(slide.shapes._shapes) >= 1
```

Run to verify they fail:

```bash
cd /Users/lumingze/Desktop/SlideForge
python -m pytest tests/test_assemble_layout_agent.py -v
```
Expected: FAIL (integration code not yet in assemble.py)

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/lumingze/Desktop/SlideForge
python -m pytest tests/test_assemble_layout_agent.py -v 2>&1 | head -20
```
Expected: FAIL — likely test set-up issues or the assemble.py hasn't been modified yet.

- [ ] **Step 3: Modify `assemble_slide()` to integrate Layout Agent**

In `slideforge/pptx_engine/assemble.py`, modify `assemble_slide()` between `_prepare_text_layouts()` and the render loop:

```python
def assemble_slide(slide, data):
    """装配一张 slide。"""
    bg_rgb = parse_rgb(data["slide"]["background"])
    bg_image = data["slide"].get("backgroundImage", "")
    add_background(slide, bg_rgb, bg_image)
    has_native_gradient = bool(
        bg_image and bg_image != "none" and "gradient" in bg_image.lower()
    )
    _prepare_text_layouts(data["records"])

    # ── Layout Agent 调优 ───────────────────────────────────────────
    try:
        from slideforge.agents.layout_agent import run_layout_agent
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        adjustments = run_layout_agent(llm, data["records"], slide_index=len(slide._element) if hasattr(slide, '_element') else 0)
        for rec in data["records"]:
            eid = str(rec.get("id", ""))
            if eid in adjustments:
                x, y, w, h = adjustments[eid]
                # Record _adjusted_rect as tuple (x, y, w, h) in CSS px
                rec["_adjusted_rect"] = (x, y, w, h)
    except ImportError:
        pass  # Layout Agent 模块未安装，使用 _scaled_rect
    except Exception:
        pass  # 任何异常 fallback 到 _scaled_rect

    text_records = []
    for rec in data["records"]:
        # ... rest of render loop unchanged
```

- [ ] **Step 4: Modify render functions to use `_adjusted_rect`**

Each render function (`add_text_box`, `add_shape_box`, `add_deco_snapshot`, etc.) needs to check `_adjusted_rect` first.

For `add_text_box` (around line 981), change `_scaled_rect` call:

```python
    # ── Use _adjusted_rect if available, else _scaled_rect ──
    adjusted = rec.get("_adjusted_rect")
    if adjusted:
        # _adjusted_rect is (x, y, w, h) in CSS px → convert to EMU
        # Position uses scale=1.0, size uses scale=SIZE_SCALE
        x = px_to_emu(adjusted[0])
        y = px_to_emu(adjusted[1])
        w = px_to_emu(adjusted[2], SIZE_SCALE)
        h = px_to_emu(adjusted[3], SIZE_SCALE)
        x, y, w, h = _clamp_to_slide(x, y, w, h)
    else:
        x, y, w, h = _scaled_rect(r["x"], r["y"], w_px, h_px)
```

Apply the same pattern to:

**`add_shape_box`** — around line 682, change:
```python
    adjusted = rec.get("_adjusted_rect")
    if adjusted:
        x = px_to_emu(adjusted[0])
        y = px_to_emu(adjusted[1])
        w = px_to_emu(adjusted[2], SIZE_SCALE)
        h = px_to_emu(adjusted[3], SIZE_SCALE)
        x, y, w, h = _clamp_to_slide(x, y, w, h)
    else:
        x, y, w, h = _scaled_rect(r["x"], r["y"], r["w"], r["h"])
```

**`add_svg_picture`** — around line 1313, same pattern:
```python
    adjusted = rec.get("_adjusted_rect")
    if adjusted:
        x = px_to_emu(adjusted[0])
        y = px_to_emu(adjusted[1])
        w = px_to_emu(adjusted[2], SIZE_SCALE)
        h = px_to_emu(adjusted[3], SIZE_SCALE)
        x, y, w, h = _clamp_to_slide(x, y, w, h)
    else:
        x, y, w, h = _scaled_rect(r["x"], r["y"], r["w"], r["h"])
```

**`add_img_picture`** / **`add_canvas_picture`** / **`add_deco_snapshot`** — same pattern.

- [ ] **Step 5: Verify the file parses correctly**

```bash
cd /Users/lumingze/Desktop/SlideForge
python -c "import ast; ast.parse(open('slideforge/pptx_engine/assemble.py').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Run integration tests**

```bash
cd /Users/lumingze/Desktop/SlideForge
python -m pytest tests/test_assemble_layout_agent.py -v
```
Expected: All tests PASS

- [ ] **Step 7: Run existing tests to verify no regression**

```bash
cd /Users/lumingze/Desktop/SlideForge
python -m pytest tests/ -v 2>&1 | tail -30
```
Expected: No regressions (same pass/fail count as before changes).

- [ ] **Step 8: Commit**

```bash
git add slideforge/pptx_engine/assemble.py tests/test_assemble_layout_agent.py
git commit -m "feat: integrate Layout Agent into assemble.py render pipeline

Render functions check _adjusted_rect first, fall back to _scaled_rect.
Agent runs once per slide after _prepare_text_layouts(), before rendering."
```

---

### Task 3: End-to-end verification

- [ ] **Step 1: Run the full HTML → PPTX pipeline on a test file**

```bash
cd /Users/lumingze/Desktop/SlideForge
python -c "
from slideforge.pptx_converter import convert_html_to_pptx
result = convert_html_to_pptx('slideforge_preview.html', '/tmp/layout_agent_test.pptx', verbose=True)
print(f'Output: {result}')
"
```
Expected: PPTX generated without errors (may have layout agent log messages).

- [ ] **Step 2: Run structural diff to check element match rate**

```bash
cd /Users/lumingze/Desktop/SlideForge
python tools/structural_diff.py measurements.json /tmp/layout_agent_test.pptx
```
Expected: No significant drop in match rate vs current baseline (should be comparable or better).

- [ ] **Step 3: Commit the plan document**

```bash
git add docs/superpowers/plans/2026-06-12-layout-agent.md
git commit -m "docs: implementation plan for Layout Agent"
```

---

## Spec Coverage Checklist

| Spec requirement | Task(s) |
|---|---|
| `get_slide_elements()` ReAct tool | Task 1 (layout_agent.py) |
| `check_layout()` ReAct tool | Task 1 (_check_layout_core) |
| Per-slide agent processing | Task 1 (run_layout_agent) |
| Fallback on failure | Task 1 (stagnant/timeout/exception) |
| Full-screen deco_snapshot skip | Task 1 (is_fullscreen_deco) |
| Agent integration in assemble_slide() | Task 2 (integrate + render changes) |
| Adjustments via _adjusted_rect | Task 2 (all render functions) |
| gpt-4o, temperature=0, 30s timeout | Task 1 (defaults in run_layout_agent) |
| Text truncation to 40 chars | Task 1 (_truncate) |

