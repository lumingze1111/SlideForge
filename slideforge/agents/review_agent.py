"""
Review Agent — HTML 幻灯片设计质量审查

ReAct 工具集：
- parse_html_structure  解析 HTML 中的元素和 CSS 属性
- check_font_sizes      检查字号是否符合排版规范
- check_spacing         检查间距是否符合 8px 网格
- check_contrast_html   提取 color/background 对并批量验证对比度
- count_inline_styles   统计内联样式数量（越少越好）
"""

import json
import re
from typing import List, Dict
from bs4 import BeautifulSoup

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from slideforge.design_system.typography import TypographyRules

_rules = TypographyRules()

# 允许的标准字号（来自排版规范）
_ALLOWED_SIZES = {
    _rules.scale.h1, _rules.scale.h2, _rules.scale.h3,
    _rules.scale.h4, _rules.scale.h5, _rules.scale.h6,
    _rules.scale.body_large, _rules.scale.body,
    _rules.scale.body_small, _rules.scale.caption,
}

# 允许的间距值（8px 倍数）
_ALLOWED_SPACING = {n * 8 for n in range(1, 17)}


# ── Pydantic 输出结构 ─────────────────────────────────────────────────────────

class ReviewReport(BaseModel):
    passed: bool
    score: int                  # 0–100
    issues: List[str]           # 具体问题列表
    suggestions: List[str]      # 改进建议


# ── 工具辅助函数 ─────────────────────────────────────────────────────────────

def _hex_contrast(fg: str, bg: str) -> float:
    """计算两个 #RRGGBB 颜色的对比度"""
    def lum(hex_color: str) -> float:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        r, g, b = (int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4))
        def lin(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = lin(r), lin(g), lin(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    l1, l2 = lum(fg), lum(bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def _parse_px(value: str) -> int | None:
    """从 CSS 值字符串中提取 px 数值"""
    m = re.match(r"(\d+(?:\.\d+)?)px", value.strip())
    return int(float(m.group(1))) if m else None


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def parse_html_structure(html: str) -> str:
    """
    解析 HTML 幻灯片结构，返回标签层级、元素数量和所有内联 style 属性摘要。
    html: 完整的 HTML 字符串
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        tags: Dict[str, int] = {}
        inline_count = 0
        font_size_values = []
        for tag in soup.find_all(True):
            tags[tag.name] = tags.get(tag.name, 0) + 1
            style = tag.get("style", "")
            if style:
                inline_count += 1
                for m in re.finditer(r"font-size\s*:\s*(\S+)", style):
                    px = _parse_px(m.group(1))
                    if px:
                        font_size_values.append(px)

        tag_summary = ", ".join(f"{k}×{v}" for k, v in sorted(tags.items()))
        sizes_str = ", ".join(map(str, sorted(set(font_size_values)))) or "无"
        return (
            f"标签统计: {tag_summary}\n"
            f"内联 style 属性数: {inline_count}\n"
            f"内联字号（px）: {sizes_str}"
        )
    except Exception as e:
        return f"解析失败: {e}"


@tool
def check_font_sizes(html: str) -> str:
    """
    检查 HTML 中所有 font-size（内联 style + <style> 块）是否符合排版规范。
    返回不规范字号及出现位置。
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        violations = []

        # 检查内联样式
        for tag in soup.find_all(True, style=True):
            style = tag.get("style", "")
            for m in re.finditer(r"font-size\s*:\s*(\S+)", style):
                px = _parse_px(m.group(1))
                if px and px not in _ALLOWED_SIZES:
                    violations.append(f"<{tag.name}> 内联: {px}px（不在规范值中）")

        # 检查 <style> 块
        for style_tag in soup.find_all("style"):
            for m in re.finditer(r"font-size\s*:\s*(\S+)", style_tag.string or ""):
                px = _parse_px(m.group(1))
                if px and px not in _ALLOWED_SIZES:
                    violations.append(f"<style> 块: {px}px（不在规范值中）")

        if not violations:
            allowed = sorted(_ALLOWED_SIZES)
            return f"✅ 所有字号符合规范（规范值: {allowed}）"
        return "❌ 不规范字号:\n" + "\n".join(f"  - {v}" for v in violations[:15])
    except Exception as e:
        return f"检查失败: {e}"


@tool
def check_spacing(html: str) -> str:
    """
    检查 HTML 中 padding / margin / gap 值是否为 8px 的倍数。
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        violations = []
        props = ("padding", "margin", "gap", "padding-top", "padding-bottom",
                 "padding-left", "padding-right", "margin-top", "margin-bottom",
                 "margin-left", "margin-right")

        def check_style_block(css_text: str, source: str):
            for prop in props:
                pattern = rf"{re.escape(prop)}\s*:\s*(\S+)"
                for m in re.finditer(pattern, css_text):
                    px = _parse_px(m.group(1))
                    if px and px not in _ALLOWED_SPACING:
                        violations.append(f"{source} {prop}: {px}px（非 8px 倍数）")

        for tag in soup.find_all(True, style=True):
            check_style_block(tag.get("style", ""), f"<{tag.name}> 内联")

        for style_tag in soup.find_all("style"):
            check_style_block(style_tag.string or "", "<style> 块")

        if not violations:
            return "✅ 所有间距符合 8px 网格规范"
        return "❌ 不规范间距:\n" + "\n".join(f"  - {v}" for v in violations[:15])
    except Exception as e:
        return f"检查失败: {e}"


@tool
def check_contrast_html(html: str) -> str:
    """
    从 HTML 中提取 color + background-color 配对，批量验证 WCAG AA 对比度（≥4.5）。
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        pairs = []

        def extract(style_text: str, context: str):
            color = bg = None
            for m in re.finditer(r"(?<!\w)color\s*:\s*(#[0-9a-fA-F]{3,6})", style_text):
                color = m.group(1)
            for m in re.finditer(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,6})", style_text):
                bg = m.group(1)
            if color and bg:
                pairs.append((color, bg, context))

        for tag in soup.find_all(True, style=True):
            extract(tag.get("style", ""), f"<{tag.name}>")
        for style_tag in soup.find_all("style"):
            extract(style_tag.string or "", "<style>")

        if not pairs:
            return "未找到明确的 color + background-color 配对"

        results = []
        for fg, bg, ctx in pairs[:10]:
            try:
                ratio = _hex_contrast(fg, bg)
                aa = "✅" if ratio >= 4.5 else "❌"
                results.append(f"{aa} {ctx}: {fg}/{bg} → {ratio:.1f}:1")
            except Exception:
                results.append(f"⚠️  {ctx}: {fg}/{bg} → 计算失败")

        return "\n".join(results)
    except Exception as e:
        return f"检查失败: {e}"


@tool
def count_inline_styles(html: str) -> str:
    """
    统计 HTML 中内联 style 属性的数量和比例，内联样式越少代码越规范。
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        total = len(soup.find_all(True))
        inline = len(soup.find_all(True, style=True))
        pct = inline / total * 100 if total else 0
        if pct < 20:
            verdict = "✅ 良好（内联样式占比低）"
        elif pct < 50:
            verdict = "⚠️  一般（建议将内联样式提取到 <style> 块）"
        else:
            verdict = "❌ 过多（内联样式应提取到 CSS 类）"
        return f"总元素: {total}  内联 style: {inline}  占比: {pct:.0f}%  → {verdict}"
    except Exception as e:
        return f"统计失败: {e}"


# ── Agent factory ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是资深设计审查员，负责对幻灯片 HTML 进行设计质量审查。

工作流程（必须按序执行）：
1. 调用 parse_html_structure 了解整体结构
2. 调用 count_inline_styles 评估代码规范性
3. 调用 check_font_sizes 验证字号是否符合规范
4. 调用 check_spacing 验证间距是否符合 8px 网格
5. 调用 check_contrast_html 验证文字可读性
6. 综合以上结果打分并输出 JSON 报告

评分规则（满分 100）：
- 内联样式 < 20%：+20 分；20-50%：+10 分；> 50%：0 分
- 字号 100% 规范：+25 分；有违规每处 -5 分
- 间距 100% 规范：+25 分；有违规每处 -3 分
- 对比度全部 ✅：+30 分；每处 ❌ -10 分

输出 JSON 格式（直接输出，不加代码块标记）：
{
  "passed": true/false,
  "score": 0-100,
  "issues": ["具体问题1", "具体问题2"],
  "suggestions": ["改进建议1", "改进建议2"]
}

passed = score >= 70
"""


def preprocess_html(html: str) -> str:
    """
    在调用 Agent 前，将 HTML 预处理为结构摘要（避免 tool 参数过大导致上下文截断）。
    返回紧凑的文本摘要，而不是原始 HTML。
    """
    structure = parse_html_structure.func(html)
    inline_info = count_inline_styles.func(html)
    font_check = check_font_sizes.func(html)
    spacing_check = check_spacing.func(html)
    contrast_check = check_contrast_html.func(html)
    return (
        f"[结构]\n{structure}\n\n"
        f"[内联样式]\n{inline_info}\n\n"
        f"[字号检查]\n{font_check}\n\n"
        f"[间距检查]\n{spacing_check}\n\n"
        f"[对比度检查]\n{contrast_check}"
    )


REVIEW_SCORE_PROMPT = """你是资深设计审查员。以下是对幻灯片 HTML 的静态分析报告，请根据报告内容综合评分并输出 JSON。

评分规则（满分 100）：
- 内联样式 < 20%：+20 分；20-50%：+10 分；> 50%：0 分
- 字号 100% 规范（✅）：+25 分；有违规每处 -5 分（最低 0）
- 间距 100% 规范（✅）：+25 分；有违规每处 -3 分（最低 0）
- 对比度全部 ✅：+30 分；每处 ❌ -10 分（最低 0）

passed = score >= 70

直接输出 JSON（不加代码块标记）：
{
  "passed": true/false,
  "score": 0-100,
  "issues": ["具体问题1", "具体问题2"],
  "suggestions": ["改进建议1", "改进建议2"]
}
"""


def create_review_agent(llm: ChatOpenAI):
    """创建 Review ReAct Agent（工具接受摘要字符串，避免大参数截断）"""

    @tool
    def analyze_report(report: str) -> str:
        """接收已完成的 HTML 分析摘要，确认内容是否清晰完整。"""
        return f"收到报告，长度={len(report)}字符。\n{report[:500]}..."

    tools = [analyze_report]
    return create_react_agent(llm, tools, prompt=REVIEW_SCORE_PROMPT)


def run_review_agent(llm: ChatOpenAI, html: str) -> ReviewReport:
    """
    运行 Review Agent：
    1. Python 端预处理 HTML，生成分析摘要（不走 LLM）
    2. 将摘要直接交给 Agent 打分，避免 tool 参数过大的问题
    """
    summary = preprocess_html(html)
    agent = create_review_agent(llm)
    user_msg = f"请根据以下 HTML 分析报告进行设计质量评分：\n\n{summary}"

    result = agent.invoke({"messages": [HumanMessage(content=user_msg)]})
    final_text = result["messages"][-1].content

    try:
        if "```" in final_text:
            final_text = final_text.split("```")[1].strip().lstrip("json").strip()
        start = final_text.find("{")
        end = final_text.rfind("}") + 1
        data = json.loads(final_text[start:end])
        return ReviewReport(**data)
    except Exception:
        return ReviewReport(
            passed=False,
            score=0,
            issues=["报告解析失败"],
            suggestions=["请重新运行审查"],
        )
