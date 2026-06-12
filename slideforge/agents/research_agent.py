"""
Research Agent - 使用 MCP 搜索相关内容
"""

import json
from typing import List, Dict
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel


class ResearchResult(BaseModel):
    """研究结果"""
    facts: List[str] = Field(description="核心事实，5-8条")
    data_points: List[str] = Field(description="关键数据点，3-5条")
    sources: List[str] = Field(description="信息来源")


def search_topic_content(topic: str, key_messages: List[str]) -> ResearchResult:
    """通过 MCP 搜索主题相关内容"""
    # TODO: 集成 MCP 工具调用
    # 这里先返回模拟数据，实际应调用 brave_web_search 等 MCP 工具
    
    import subprocess
    import tempfile
    
    # 使用 curl 调用搜索 API（示例）
    query = f"{topic} {' '.join(key_messages[:2])}"
    
    # 模拟返回（实际应调用真实的 MCP 工具）
    return ResearchResult(
        facts=[
            f"关于 {topic} 的核心事实 1",
            f"关于 {topic} 的核心事实 2",
            f"关于 {topic} 的核心事实 3",
        ],
        data_points=[
            "数据点 1",
            "数据点 2",
        ],
        sources=["source1", "source2"]
    )
