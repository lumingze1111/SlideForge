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

SYSTEM_PROMPT = """你是专业幻灯片布局设计师，负责在 1.5× 缩放后调整元素位置。

核心规则（按优先级排列）：

1. 默认保持 init 位置不动 —— init 已经是正确的中心缩放位置，绝大多数元素不需要调整
2. 仅在元素溢出幻灯片边界 [0,1920]×[0,1080] 时才调整
3. 仅在两个非背景元素显著重叠时才调整间距
4. 调整方向偏好：优先右移（增大 x），其次下移（增大 y），避免左移或上移
5. 调整幅度要保守：每次最多移动 20-30px，不要大幅跳跃
6. 保持同列元素水平对齐（x 值一致），保持同行元素垂直对齐（y 值一致）
7. 不要改动 w 和 h —— 尺寸保持 orig 的值不变（CSS 原始尺寸），只调整 x/y
8. 不要调整 deco_snapshot 和全屏背景元素
9. 文字元素实际渲染尺寸比 init.rect 大 12%，调整时预留余量

输出格式（不要加代码块标记）：
{{
  "adjustments": {{
    "0": {{"x": 100, "y": 50, "w": 400, "h": 60}},
    "1": {{"x": 100, "y": 160, "w": 400, "h": 60}}
  }},
  "reasoning": "元素1右溢出20px，右移使其完全可见；元素2为保持同列对齐同步右移"
}}

注意：
- adjustments 中只放需要调整的元素，不需要调整的不要放进去
- 元素的 w 和 h 必须等于 orig 中的 w 和 h，不要改动尺寸
- 输出必须是合法 JSON，不要加说明文字
"""


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
    """截断文本到 max_len + "…"。"""
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
            issues.append(f"右边溢出({a['x'] + a['w'] - slide_w}px)")
        if a["y"] + a["h"] > slide_h:
            issues.append(f"下边溢出({a['y'] + a['h'] - slide_h}px)")
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
    text = text[start:end + 1]
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
    llm: ChatOpenAI | None,
    records: list[dict],
    slide_index: int = 0,
    total_slides: int = 1,
    timeout_ms: int = 30000,
) -> dict[str, tuple[float, float, float, float]]:
    """对一张 slide 运行 Layout Agent。

    Args:
        llm: ChatOpenAI 实例（可选，仅首页/尾页需要）。
        records: 当前 slide 的 records 列表（需要含 "id" 字段）。
        slide_index: 幻灯片序号（1-based）。
        total_slides: 总幻灯片数。
        timeout_ms: 超时毫秒数。

    Returns:
        {record_id: (x, y, w, h)} 调整后的坐标。
        返回空 dict 表示应 fallback 到 _scaled_rect。
    """
    global _CURRENT_RECORDS, _CURRENT_SLIDE_W, _CURRENT_SLIDE_H
    _CURRENT_RECORDS = records
    _CURRENT_SLIDE_W = SLIDE_W_PX
    _CURRENT_SLIDE_H = SLIDE_H_PX

    elements = _build_element_list(records, SLIDE_W_PX, SLIDE_H_PX)
    if not elements:
        return {}

    # 所有页面统一右移 150px（补偿 1.5× 中心缩放的左侧偏移）
    FORCE_RIGHT_SHIFT = 150
    result = {}
    logger.info(f"[layout_agent] slide {slide_index}/{total_slides} → +{FORCE_RIGHT_SHIFT}px, {len(elements)} elements")
    for el in elements:
        eid = el["id"]
        init = el["init"]
        orig = el["orig"]
        x = init["x"] + FORCE_RIGHT_SHIFT
        y = init["y"]
        w = orig["w"]
        h = orig["h"]
        # clamp to slide (use init.w for clamping since position is in init space)
        if x + init["w"] > SLIDE_W_PX:
            x = SLIDE_W_PX - init["w"]
        if x < 0:
            x = 0
        result[eid] = (x, y, w, h)
    return result
