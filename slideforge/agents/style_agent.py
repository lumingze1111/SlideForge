"""
Style Agent — 配色方案与视觉风格选择

使用 LangGraph create_react_agent 实现真正的 ReAct 循环：
- 工具调用：list_schemes / get_scheme_detail / check_contrast
- Agent 自主决策：查询 → 对比 → 选择 → 解释
"""

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from slideforge.design_system.colors import COLOR_SCHEMES, ColorScheme


# ── Pydantic 输出结构 ─────────────────────────────────────────────────────────

class StyleDecision(BaseModel):
    scheme_name: str
    visual_style: str   # minimalist / bold / elegant / corporate / playful
    heading_font: str
    body_font: str
    reasoning: str


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def list_schemes(mood: str = "") -> str:
    """列出可用配色方案。mood 可选：professional / creative / academic / modern / warm / tech"""
    rows = []
    for name, s in COLOR_SCHEMES.items():
        if mood and s.mood.value != mood:
            continue
        rows.append(
            f"{name} | {s.mood.value} | {s.description}\n"
            f"  primary={s.primary}  secondary={s.secondary}  accent={s.accent}  bg={s.background}"
        )
    return "\n\n".join(rows) if rows else "无匹配方案"


@tool
def get_scheme_detail(name: str) -> str:
    """获取指定配色方案的完整色值。name 必须是 list_schemes 返回的方案标识。"""
    s = COLOR_SCHEMES.get(name)
    if not s:
        return f"未找到方案: {name}，请先调用 list_schemes 查看可用名称"
    return (
        f"name={name}\n"
        f"primary={s.primary}  secondary={s.secondary}  accent={s.accent}\n"
        f"background={s.background}  surface={s.surface}\n"
        f"text_primary={s.text_primary}  text_secondary={s.text_secondary}\n"
        f"border={s.border}  success={s.success}  warning={s.warning}  error={s.error}"
    )


@tool
def check_contrast(fg: str, bg: str) -> str:
    """
    计算前景色与背景色的对比度（相对亮度比），判断是否满足 WCAG AA（≥4.5）。
    fg / bg 格式为 #RRGGBB。
    """
    def relative_luminance(hex_color: str) -> float:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4))
        def linearize(c: float) -> float:
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = linearize(r), linearize(g), linearize(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    try:
        l1 = relative_luminance(fg)
        l2 = relative_luminance(bg)
        lighter, darker = max(l1, l2), min(l1, l2)
        ratio = (lighter + 0.05) / (darker + 0.05)
        aa_pass = ratio >= 4.5
        aaa_pass = ratio >= 7.0
        return (
            f"对比度: {ratio:.2f}:1\n"
            f"WCAG AA（≥4.5）: {'✅ 通过' if aa_pass else '❌ 不通过'}\n"
            f"WCAG AAA（≥7.0）: {'✅ 通过' if aaa_pass else '❌ 不通过'}"
        )
    except Exception as e:
        return f"计算失败: {e}"


# ── Agent factory ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是专业视觉设计师，负责为演示文稿选择配色方案和视觉风格。

工作流程（必须按序执行）：
1. 调用 list_schemes 查看所有可用方案（如有 mood 倾向可按 mood 筛选）
2. 对候选方案调用 get_scheme_detail 获取完整色值
3. 对主文字色与背景色调用 check_contrast，确认对比度 ≥ 4.5（WCAG AA）
4. 综合主题、受众、对比度结果，选出最合适的方案
5. 以 JSON 格式输出最终决策

输出 JSON 格式（不要加代码块标记，直接输出）：
{
  "scheme_name": "方案标识",
  "visual_style": "minimalist|bold|elegant|corporate|playful",
  "heading_font": "标题字体",
  "body_font": "正文字体",
  "reasoning": "选择理由（不超过80字）"
}

设计原则：
- 对比度必须通过 WCAG AA（≥4.5），不通过需换方案
- 科技/研究主题 → tech/academic 方向
- 商务/汇报主题 → professional 方向
- 创意/营销主题 → creative 方向
- 教育/温暖主题 → warm 方向
"""


def create_style_agent(llm: ChatOpenAI):
    """创建 Style ReAct Agent"""
    tools = [list_schemes, get_scheme_detail, check_contrast]
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


def run_style_agent(llm: ChatOpenAI, topic: str, audience: str) -> StyleDecision:
    """运行 Style Agent，返回结构化风格决策"""
    agent = create_style_agent(llm)
    user_msg = f"演示主题：{topic}\n目标受众：{audience}\n\n请为该演示文稿推荐最合适的配色方案和视觉风格。"

    result = agent.invoke({"messages": [HumanMessage(content=user_msg)]})
    final_text = result["messages"][-1].content

    # 解析 JSON
    import json
    try:
        if "```" in final_text:
            final_text = final_text.split("```")[1].strip().lstrip("json").strip()
        start = final_text.find("{")
        end = final_text.rfind("}") + 1
        data = json.loads(final_text[start:end])
        return StyleDecision(**data)
    except Exception:
        return StyleDecision(
            scheme_name="blue_professional",
            visual_style="minimalist",
            heading_font="Inter",
            body_font="PingFang SC",
            reasoning="解析失败，使用默认方案",
        )
