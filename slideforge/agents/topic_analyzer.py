"""
Topic Analyzer Agent - 分析用户主题和想法，给出演示建议
"""

import json
from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel


class PresentationSuggestion(BaseModel):
    """演示建议"""
    target_audience: str = Field(description="推荐的目标受众")
    key_messages: List[str] = Field(description="核心信息点，3-5个")
    suggested_structure: str = Field(description="建议的演示结构")
    tone: str = Field(description="推荐的语调：专业/轻松/激情/数据驱动等")
    estimated_pages: int = Field(description="建议页数")
    visual_style_hint: str = Field(description="视觉风格建议")
    reasoning: str = Field(description="分析理由，100字以内")


ANALYZER_PROMPT = """你是演示文稿策略专家。分析用户的主题和想法，给出专业建议。

用户输入：
主题：{topic}
想法/目标：{ideas}

请分析：
1. 这个主题最适合哪类受众
2. 核心信息点是什么（3-5个）
3. 什么结构最有效（故事型/数据型/问题解决型等）
4. 应该用什么语调
5. 建议多少页
6. 视觉风格建议（配色倾向、版式风格等）

输出 JSON：
{{
  "target_audience": "目标受众",
  "key_messages": ["核心信息1", "核心信息2", ...],
  "suggested_structure": "建议结构",
  "tone": "语调",
  "estimated_pages": 8,
  "visual_style_hint": "视觉风格建议",
  "reasoning": "分析理由"
}}

只输出 JSON，不加代码块。"""


def analyze_topic(llm: BaseChatModel, topic: str, ideas: str) -> PresentationSuggestion:
    """分析主题并给出建议"""
    prompt = ANALYZER_PROMPT.format(topic=topic, ideas=ideas or "无特定想法")
    
    try:
        structured_llm = llm.with_structured_output(PresentationSuggestion)
        result = structured_llm.invoke(prompt)
        return result
    except Exception:
        schema_str = json.dumps(PresentationSuggestion.model_json_schema(), ensure_ascii=False, indent=2)
        json_prompt = prompt + "\n\n必须严格按照以下 JSON schema 输出：\n" + schema_str
        
        response = llm.invoke([
            SystemMessage(content="You are a presentation strategy expert. Output valid JSON only."),
            HumanMessage(content=json_prompt)
        ])
        
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        data = json.loads(content.strip())
        return PresentationSuggestion(**data)


def print_suggestion(suggestion: PresentationSuggestion, topic: str) -> None:
    """打印分析建议"""
    print("\n" + "═" * 70)
    print(f"  🎯 主题分析：{topic}")
    print("═" * 70)
    print(f"\n  👥 目标受众：{suggestion.target_audience}")
    print(f"  📝 建议页数：{suggestion.estimated_pages} 页")
    print(f"  🎭 语调风格：{suggestion.tone}")
    print(f"  📐 演示结构：{suggestion.suggested_structure}")
    print(f"  🎨 视觉风格：{suggestion.visual_style_hint}")
    
    print(f"\n  💡 核心信息点：")
    for i, msg in enumerate(suggestion.key_messages, 1):
        print(f"     {i}. {msg}")
    
    print(f"\n  📊 分析理由：\n     {suggestion.reasoning}")
    print("\n" + "═" * 70)
