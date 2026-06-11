"""
Design Agent — 幻灯片布局与排版规划

ReAct 工具集：
- get_layout_spec      查询布局类型的具体坐标和尺寸
- get_typography_spec  查询字体尺寸体系和间距规范
- suggest_element_size 根据内容类型建议字号和权重
"""

import json
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel
from typing import Dict

from slideforge.design_system.typography import TypographyRules

_rules = TypographyRules()


# ── Pydantic 输出结构 ─────────────────────────────────────────────────────────

class LayoutDecision(BaseModel):
    layout_type: str               # single / two_column / sidebar_left / sidebar_right / header_content
    regions: Dict[str, Dict]       # {"region_name": {"x":..,"y":..,"w":..,"h":..}}
    font_sizes: Dict[str, int]     # {"title": 36, "body": 16, ...}
    spacing: Dict[str, int]        # {"section_gap": 24, "item_gap": 12, ...}
    reasoning: str


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def get_layout_spec(layout_type: str) -> str:
    """
    返回指定布局类型的区域坐标和尺寸。
    layout_type 可选：single / two_column / sidebar_left / sidebar_right / header_content
    """
    try:
        regions = _rules.calculate_layout(layout_type)
    except Exception:
        return f"未知布局类型: {layout_type}"

    lines = [f"布局: {layout_type}  （幻灯片 1280×720px，安全边距 H=60px V=40px）"]
    for name, (x, y, w, h) in regions.items():
        lines.append(f"  {name}: x={x} y={y} w={w} h={h}")
    return "\n".join(lines)


@tool
def get_typography_spec() -> str:
    """返回完整的字体尺寸体系和 8px 间距规范。"""
    sc = _rules.scale
    sp = _rules.spacing
    return f"""字体尺寸体系（基于专业排版系统）:
  H1={sc.h1}px  H2={sc.h2}px  H3={sc.h3}px  H4={sc.h4}px  H5={sc.h5}px  H6={sc.h6}px
  body_large={sc.body_large}px  body={sc.body}px  body_small={sc.body_small}px  caption={sc.caption}px
  heading_line_height={sc.heading_line_height}  body_line_height={sc.body_line_height}

间距体系（8px 网格）:
  xs={sp.xs}px  sm={sp.sm}px  md={sp.md}px  lg={sp.lg}px  xl={sp.xl}px  xxl={sp.xxl}px

12 列网格:
  列宽(1col)≈{_rules.grid.get_column_width(1)}px  4col={_rules.grid.get_column_width(4)}px  8col={_rules.grid.get_column_width(8)}px"""


@tool
def suggest_element_size(content_type: str, priority: str = "normal") -> str:
    """
    根据内容类型和优先级建议字号与字重。
    content_type: title / subtitle / body / caption / label / number / quote
    priority: primary / normal / secondary
    """
    sc = _rules.scale
    table = {
        "title":    {"primary": (sc.h2, "700"), "normal": (sc.h3, "600"), "secondary": (sc.h4, "600")},
        "subtitle": {"primary": (sc.h4, "500"), "normal": (sc.h5, "500"), "secondary": (sc.h6, "400")},
        "body":     {"primary": (sc.body_large, "400"), "normal": (sc.body, "400"), "secondary": (sc.body_small, "400")},
        "caption":  {"primary": (sc.body_small, "400"), "normal": (sc.caption, "400"), "secondary": (sc.caption, "300")},
        "label":    {"primary": (sc.body_small, "600"), "normal": (sc.caption, "600"), "secondary": (sc.caption, "500")},
        "number":   {"primary": (sc.h1, "700"), "normal": (sc.h2, "700"), "secondary": (sc.h3, "600")},
        "quote":    {"primary": (sc.body_large, "400"), "normal": (sc.body, "400"), "secondary": (sc.body_small, "300")},
    }
    entry = table.get(content_type, {}).get(priority)
    if not entry:
        return f"未知类型或优先级: {content_type}/{priority}"
    size, weight = entry
    return f"{content_type}（{priority}）→ font-size: {size}px  font-weight: {weight}"


# ── Agent factory ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是专业排版设计师，负责为幻灯片规划精确的布局和排版方案。

工作流程（必须按序执行）：
1. 调用 get_typography_spec 了解尺寸和间距规范
2. 分析幻灯片内容结构，判断需要哪些区域（标题/图表/列表/说明等）
3. 调用 get_layout_spec 查询候选布局的坐标（逐个查询后对比）
4. 调用 suggest_element_size 确认每类内容的字号和字重
5. 以 JSON 格式输出完整布局方案

输出 JSON 格式（直接输出，不加代码块标记）：
{
  "layout_type": "布局类型",
  "regions": {
    "region_name": {"x": int, "y": int, "w": int, "h": int}
  },
  "font_sizes": {"元素名": 字号},
  "spacing": {"section_gap": int, "item_gap": int, "padding": int},
  "reasoning": "设计说明（不超过80字）"
}

设计原则：
- 标题页 → single 布局，大字号居中，大量留白
- 内容页（1个主题）→ header_content，顶部标题 + 下方内容
- 左右对比内容 → two_column，各占50%
- 详情+注释 → sidebar_right（主8列+注释4列）
- 列表+图表 → sidebar_left（图表4列+列表8列）
- 间距必须是 8px 的倍数
- 字号必须来自排版规范，不得随意指定
"""


def create_design_agent(llm: ChatOpenAI):
    """创建 Design ReAct Agent"""
    tools = [get_layout_spec, get_typography_spec, suggest_element_size]
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


def run_design_agent(llm: ChatOpenAI, slide_description: str, slide_type: str) -> LayoutDecision:
    """运行 Design Agent，返回结构化布局决策"""
    agent = create_design_agent(llm)
    user_msg = (
        f"幻灯片类型：{slide_type}\n"
        f"内容描述：\n{slide_description}\n\n"
        "请为该幻灯片规划完整的布局和排版方案。"
    )

    result = agent.invoke({"messages": [HumanMessage(content=user_msg)]})
    final_text = result["messages"][-1].content

    try:
        if "```" in final_text:
            final_text = final_text.split("```")[1].strip().lstrip("json").strip()
        start = final_text.find("{")
        end = final_text.rfind("}") + 1
        data = json.loads(final_text[start:end])
        return LayoutDecision(**data)
    except Exception:
        return LayoutDecision(
            layout_type="header_content",
            regions={},
            font_sizes={"title": 28, "body": 16},
            spacing={"section_gap": 24, "item_gap": 12, "padding": 16},
            reasoning="解析失败，使用默认布局",
        )
