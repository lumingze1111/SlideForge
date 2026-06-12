"""
Speaker Notes Generator - 生成演讲者备注
"""

from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
import json


NOTES_PROMPT = """为幻灯片生成详细的演讲者备注。

幻灯片标题：{title}
幻灯片内容：{content}
背景事实：{facts}

生成演讲者备注，包括：
1. 开场白（如何引入这一页）
2. 详细解释（扩展幻灯片内容，提供更多细节）
3. 数据支撑（引用具体数据或案例）
4. 过渡语（如何自然过渡到下一页）

要求：
- 口语化，易于演讲
- 200-300字
- 包含具体数据和例子
- 自然流畅

直接输出演讲者备注文本，不加格式标记。"""


def generate_speaker_notes(
    llm: BaseChatModel,
    title: str,
    content: str,
    facts: List[str]
) -> str:
    """生成演讲者备注"""
    prompt = NOTES_PROMPT.format(
        title=title,
        content=content,
        facts="\n".join(facts[:3])
    )
    
    response = llm.invoke([
        SystemMessage(content="You are a professional speech coach. Generate speaker notes in Chinese."),
        HumanMessage(content=prompt)
    ])
    
    return response.content.strip()
