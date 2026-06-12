"""
Fact Checker Agent - 评估内容真实性
"""

from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
import json


class FactCheckResult(BaseModel):
    """事实核查结果"""
    verified_count: int = Field(description="已验证条目数")
    questionable_count: int = Field(description="存疑条目数")
    issues: List[str] = Field(description="发现的问题")
    confidence_score: float = Field(description="整体可信度 0-1")


FACT_CHECK_PROMPT = """你是事实核查专家。评估以下幻灯片内容的真实性。

主题：{topic}
内容：
{content}

已知事实：
{facts}

评估：
1. 内容与已知事实是否一致
2. 是否有夸大或不准确表述
3. 数据引用是否合理
4. 整体可信度评分（0-1）

输出 JSON：
{{
  "verified_count": 5,
  "questionable_count": 1,
  "issues": ["问题描述"],
  "confidence_score": 0.85
}}"""


def check_facts(llm: BaseChatModel, topic: str, content: str, facts: List[str]) -> FactCheckResult:
    """核查内容真实性"""
    prompt = FACT_CHECK_PROMPT.format(
        topic=topic,
        content=content[:1000],
        facts="\n".join(f"- {f}" for f in facts)
    )
    
    try:
        structured_llm = llm.with_structured_output(FactCheckResult)
        return structured_llm.invoke(prompt)
    except Exception:
        response = llm.invoke([
            SystemMessage(content="You are a fact checker. Output valid JSON only."),
            HumanMessage(content=prompt)
        ])
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return FactCheckResult(**json.loads(content.strip()))
