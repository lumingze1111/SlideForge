"""
Propose Agent - 根据主题生成多套定制设计方案

不使用固定模版，而是让 LLM 根据主题和受众动态创造配色+视觉风格。
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel


class ColorProposal(BaseModel):
    """单套配色方案提案"""
    name: str = Field(description="方案名称，体现主题特点，如'深海探索蓝'")
    primary: str = Field(description="主色，十六进制色值")
    secondary: str = Field(description="辅色")
    accent: str = Field(description="强调色")
    background: str = Field(description="背景色")
    surface: str = Field(description="表面色")
    text_primary: str = Field(description="主要文本色")
    text_secondary: str = Field(description="次要文本色")
    text_disabled: str = Field(description="禁用文本色")
    border: str = Field(description="边框色")
    visual_style: str = Field(description="推荐视觉风格：minimalist/bold/elegant/corporate/playful")
    reasoning: str = Field(description="为什么这套配色适合该主题，50字以内")


class DesignProposals(BaseModel):
    """多套设计方案提案集合"""
    proposals: List[ColorProposal] = Field(description="3-5套方案，按推荐度排序")
    recommended_index: int = Field(description="最推荐方案的索引（0-based）")


SYSTEM_PROMPT = """你是专业的视觉设计师，根据主题和受众生成定制配色方案。

要求：
1. 生成 3-5 套**完全不同**的配色方案，不要套用固定模版
2. 每套方案需包含完整色彩系统（主色/辅色/强调/背景/文字等）
3. 所有色值必须是十六进制格式（如 #1976D2）
4. 确保文字色与背景色有足够对比度（WCAG AA 标准，对比度 ≥ 4.5:1）
5. 配色需紧扣主题特点，而非通用商务色
6. 为每套方案匹配合适的视觉风格
7. 方案名称要有创意，体现主题（如"量子紫光科技风"而非"紫色方案"）

主题：{topic}
受众：{audience}

直接输出 JSON 结构化数据，不要有其他文字。"""


def run_propose_agent(
    llm: BaseChatModel,
    topic: str,
    audience: str = ""
) -> DesignProposals:
    """
    让 LLM 根据主题生成多套定制设计方案

    Args:
        llm: LangChain 聊天模型
        topic: 幻灯片主题
        audience: 目标受众（可选）

    Returns:
        DesignProposals，包含 3-5 套配色+风格方案
    """
    prompt = SYSTEM_PROMPT.format(topic=topic, audience=audience or "通用受众")

    structured_llm = llm.with_structured_output(DesignProposals)
    result = structured_llm.invoke(prompt)

    return result


def print_proposals(proposals: DesignProposals) -> None:
    """打印方案列表，供用户选择"""
    print("\n" + "═" * 70)
    print("  🎨 定制设计方案（根据主题生成）")
    print("═" * 70)

    for i, p in enumerate(proposals.proposals, 1):
        marker = "⭐ 推荐" if i - 1 == proposals.recommended_index else ""
        print(f"\n  [{i}] {p.name} {marker}")
        print(f"      风格: {p.visual_style}")
        print(f"      配色: 主色 {p.primary}  辅色 {p.secondary}  强调 {p.accent}")
        print(f"      背景: {p.background}  文字 {p.text_primary}")
        print(f"      理由: {p.reasoning}")

    print("\n" + "═" * 70)


def pick_proposal(proposals: DesignProposals) -> ColorProposal:
    """让用户选择一套方案"""
    print_proposals(proposals)

    while True:
        raw = input(f"\n请选择方案编号（1-{len(proposals.proposals)}，直接回车选推荐方案）: ").strip()

        if raw == "":
            idx = proposals.recommended_index
            print(f"  ✓ 已选择推荐方案：{proposals.proposals[idx].name}")
            return proposals.proposals[idx]

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(proposals.proposals):
                print(f"  ✓ 已选择：{proposals.proposals[idx].name}")
                return proposals.proposals[idx]

        print("  ✗ 无效输入，请重试")
