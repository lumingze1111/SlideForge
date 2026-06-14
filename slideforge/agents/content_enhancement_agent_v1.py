"""
Content Enhancement Agent - 使用 ReAct 机制增强幻灯片内容
"""

from typing import Dict, Any, List, Optional, Annotated
from pathlib import Path
import uuid

from pydantic import BaseModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from slideforge.agents.html_generator import PresentationOutline, SlideContent
from slideforge.agents.propose_agent import ColorProposal
from slideforge.tools.image_search import get_image_search_tool, ImageSearchError, ImageSource
from slideforge.error_tracking import ErrorTracker, ErrorType, ErrorSeverity


class ImageSuggestion(BaseModel):
    """图片建议"""
    slide_index: int
    image_url: str
    description: str
    position: str  # 'background' | 'left' | 'right' | 'center'
    size: tuple[float, float]
    opacity: float = 1.0
    source: str


class EnhancedOutline(BaseModel):
    """增强后的大纲"""
    slides: List[SlideContent]
    images: List[ImageSuggestion]


class ContentEnhancementAgent:
    """内容增强 Agent - 目前仅支持图片搜索"""

    def __init__(
        self,
        llm: ChatOpenAI,
        error_tracker: ErrorTracker,
        output_dir: Path,
        max_iterations: int = 10,
        timeout: int = 60
    ):
        self.llm = llm
        self.error_tracker = error_tracker
        self.output_dir = output_dir
        self.max_iterations = max_iterations
        self.timeout = timeout

        # 图片搜索工具
        self.image_search_tool_instance = get_image_search_tool()

        # 创建 LangGraph Agent
        self.agent = self._create_agent()

    def _create_agent(self):
        """创建 ReAct Agent"""

        @tool
        def search_image(keywords: str, position: str = "background", size_width: float = 1.0, size_height: float = 0.6) -> Dict[str, Any]:
            """
            搜索相关图片

            Args:
                keywords: 搜索关键词
                position: 图片位置 ('background', 'left', 'right', 'center')
                size_width: 图片宽度（相对比例，0-1）
                size_height: 图片高度（相对比例，0-1）

            Returns:
                图片信息字典
            """
            try:
                results = self.image_search_tool_instance.search(
                    query=keywords,
                    limit=1,
                    preferred_source=ImageSource.UNSPLASH
                )

                if not results:
                    self.error_tracker.record_error(
                        error_type=ErrorType.API_ERROR,
                        severity=ErrorSeverity.WARNING,
                        component="search_image_tool",
                        message=f"No images found for keywords: {keywords}",
                        recovery_action="Skip image insertion",
                        recovered=True
                    )
                    return {"success": False, "message": "No images found"}

                image = results[0]

                # 下载图片
                image_filename = f"image_{uuid.uuid4().hex[:8]}.jpg"
                image_path = self.output_dir / image_filename

                try:
                    self.image_search_tool_instance.download_image(image, str(image_path))
                except Exception as e:
                    self.error_tracker.record_error(
                        error_type=ErrorType.API_ERROR,
                        severity=ErrorSeverity.WARNING,
                        component="search_image_tool",
                        message=f"Failed to download image: {e}",
                        recovery_action="Skip image insertion",
                        recovered=True
                    )
                    return {"success": False, "message": f"Failed to download: {e}"}

                return {
                    "success": True,
                    "image_url": str(image_path),
                    "description": image.description,
                    "position": position,
                    "size": (size_width, size_height),
                    "source": image.source.value
                }

            except ImageSearchError as e:
                self.error_tracker.record_error(
                    error_type=ErrorType.API_ERROR,
                    severity=ErrorSeverity.ERROR,
                    component="search_image_tool",
                    message=str(e),
                    recovery_action="Skip image insertion",
                    recovered=True
                )
                return {"success": False, "message": str(e)}

        @tool
        def finish() -> Dict[str, str]:
            """
            完成当前幻灯片的处理

            Returns:
                完成状态
            """
            return {"status": "finished"}

        tools = [search_image, finish]

        # 使用内存保存器
        memory = MemorySaver()

        # 创建 ReAct Agent
        agent = create_react_agent(
            self.llm,
            tools=tools,
            checkpointer=memory
        )

        return agent

    def enhance_outline(
        self,
        outline: PresentationOutline,
        colors: ColorProposal
    ) -> EnhancedOutline:
        """
        增强大纲，为每页幻灯片添加图片

        Args:
            outline: 原始大纲
            colors: 配色方案

        Returns:
            增强后的大纲
        """
        enhanced = EnhancedOutline(slides=outline.slides, images=[])

        for slide_index, slide in enumerate(outline.slides):
            try:
                # 构建提示
                system_prompt = f"""你是一个幻灯片内容增强助手。你的任务是为当前幻灯片决定是否需要插入图片，以及如何插入。

当前幻灯片信息：
- 索引：{slide_index}
- 标题：{slide.title}
- 内容：{slide.content}

配色方案：
- 主色：{colors.colors['primary']}
- 次色：{colors.colors['secondary']}

可用工具：
1. search_image(keywords, position, size_width, size_height) - 搜索并插入图片
   - keywords：搜索关键词（英文）
   - position：位置 ('background' 背景, 'center' 居中, 'left' 左侧, 'right' 右侧)
   - size_width：宽度比例 (0-1)
   - size_height：高度比例 (0-1)

2. finish() - 完成当前幻灯片处理

决策指南：
- 标题页通常需要背景图片
- 内容页可以选择性添加图片
- 图片应与内容相关
- 使用 finish() 结束当前页处理

请分析当前幻灯片，决定是否需要图片，并调用相应的工具。"""

                user_message = f"请为第 {slide_index + 1} 页幻灯片决定是否需要图片。"

                # 调用 Agent
                config = {
                    "configurable": {"thread_id": f"slide_{slide_index}"},
                    "recursion_limit": self.max_iterations
                }

                result = self.agent.invoke(
                    {
                        "messages": [
                            SystemMessage(content=system_prompt),
                            HumanMessage(content=user_message)
                        ]
                    },
                    config=config
                )

                # 解析结果
                messages = result.get("messages", [])
                for msg in messages:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if tool_call['name'] == 'search_image':
                                # 查找对应的工具响应
                                for response_msg in messages:
                                    if (hasattr(response_msg, 'tool_call_id') and
                                        response_msg.tool_call_id == tool_call['id']):
                                        content = response_msg.content
                                        if isinstance(content, str):
                                            import json
                                            try:
                                                content = json.loads(content)
                                            except:
                                                pass

                                        if isinstance(content, dict) and content.get('success'):
                                            enhanced.images.append(ImageSuggestion(
                                                slide_index=slide_index,
                                                image_url=content['image_url'],
                                                description=content['description'],
                                                position=content['position'],
                                                size=tuple(content['size']),
                                                source=content['source']
                                            ))

            except Exception as e:
                self.error_tracker.record_error(
                    error_type=ErrorType.REACT_ERROR,
                    severity=ErrorSeverity.ERROR,
                    component="content_enhancement_agent",
                    slide_index=slide_index,
                    message=f"Failed to enhance slide: {e}",
                    context={"slide_title": slide.title},
                    recovery_action="Skip slide enhancement",
                    recovered=True
                )
                continue

        return enhanced
