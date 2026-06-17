"""
Content Enhancement Agent (完整版) - 支持图片、数据和图表
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import json

from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from slideforge.agents.html_generator import PresentationOutline, SlideContent
from slideforge.agents.propose_agent import ColorProposal
from slideforge.tools.image_search import get_image_search_tool, ImageSearchError, ImageSource
from slideforge.tools.image_matching import ImageQueryContext, build_image_query_context, search_best_image
from slideforge.tools.data_fetch import web_search, wikipedia_fetch, web_scrape, DataFetchError
from slideforge.tools.chart_generator import (
    get_chart_generator,
    ChartType,
    ChartLayout,
    ChartData,
    ChartConfig,
    ChartRenderMethod
)
from slideforge.error_tracking import ErrorTracker, ErrorType, ErrorSeverity


class ImageSuggestion(BaseModel):
    """图片建议"""
    slide_index: int
    image_url: str
    description: str
    position: str
    size: tuple[float, float]
    opacity: float = 1.0
    source: str


class ChartSuggestion(BaseModel):
    """图表建议"""
    slide_index: int
    chart_type: str
    data: Dict[str, Any]
    layout: str
    render_method: str
    chart_path: Optional[str] = None
    native_config: Optional[Dict[str, Any]] = None


class EnhancedOutline(BaseModel):
    """增强后的大纲"""
    slides: List[SlideContent]
    images: List[ImageSuggestion]
    charts: List[ChartSuggestion]


class ContentEnhancementAgent:
    """内容增强 Agent - 完整版"""

    def __init__(
        self,
        llm: ChatOpenAI,
        error_tracker: ErrorTracker,
        output_dir: Path,
        max_iterations: int = 10,
        timeout: int = 60,
        enable_images: bool = True,
        enable_charts: bool = True
    ):
        self.llm = llm
        self.error_tracker = error_tracker
        self.output_dir = output_dir
        self.max_iterations = max_iterations
        self.timeout = timeout
        self.enable_images = enable_images
        self.enable_charts = enable_charts

        # 工具实例
        self.image_search_tool_instance = get_image_search_tool()
        self.chart_generator_instance = None  # 延迟初始化

        # 创建 Agent
        self.agent = self._create_agent()

    def _create_agent(self):
        """创建完整的 ReAct Agent"""

        @tool
        def search_image(keywords: str, position: str = "background", size_width: float = 1.0, size_height: float = 0.6) -> Dict[str, Any]:
            """搜索相关图片"""
            if not self.enable_images:
                return {"success": False, "message": "Image search is disabled"}

            try:
                context = getattr(self, "_current_image_context", None)
                if context is None:
                    context = build_image_query_context(
                        topic=keywords,
                        slide_index=0,
                        slide=SlideContent(slide_type="content", title=keywords),
                        requested_keywords=keywords,
                    )
                else:
                    context = ImageQueryContext(
                        topic=context.topic,
                        slide_index=context.slide_index,
                        slide_type=context.slide_type,
                        slide_title=context.slide_title,
                        slide_text=context.slide_text,
                        requested_keywords=keywords,
                    )

                selected = search_best_image(
                    image_tool=self.image_search_tool_instance,
                    context=context,
                    output_dir=self.output_dir,
                    preferred_source=ImageSource.UNSPLASH,
                )

                if selected is None:
                    return {"success": False, "message": "No relevant images found"}

                image = selected.image
                return {
                    "success": True,
                    "image_url": str(selected.image_path),
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
        def fetch_data(query: str, data_type: str = "general") -> Dict[str, Any]:
            """
            获取主题相关数据

            Args:
                query: 搜索查询
                data_type: 数据类型 (general, wikipedia, sports)
            """
            if not self.enable_charts:
                return {"success": False, "message": "Chart generation is disabled"}

            try:
                if data_type == "wikipedia":
                    result = wikipedia_fetch(query)
                    return {
                        "success": True,
                        "data": result,
                        "data_type": "wikipedia"
                    }
                else:
                    result = web_search(query)
                    return {
                        "success": True,
                        "data": result,
                        "data_type": "web_search"
                    }

            except DataFetchError as e:
                self.error_tracker.record_error(
                    error_type=ErrorType.API_ERROR,
                    severity=ErrorSeverity.ERROR,
                    component="fetch_data_tool",
                    message=str(e),
                    recovery_action="Skip data fetch",
                    recovered=True
                )
                return {"success": False, "message": str(e)}

        @tool
        def generate_chart(
            chart_type: str,
            chart_data: str,
            title: str,
            layout: str = "fullpage"
        ) -> Dict[str, Any]:
            """
            生成图表

            Args:
                chart_type: 图表类型 (bar, line, pie, scatter, table)
                chart_data: 图表数据 (JSON字符串)
                title: 图表标题
                layout: 布局方式 (fullpage, inline-left, inline-right, dashboard)
            """
            if not self.enable_charts:
                return {"success": False, "message": "Chart generation is disabled"}

            try:
                # 解析图表数据
                data_dict = json.loads(chart_data)

                # 初始化图表生成器
                if self.chart_generator_instance is None:
                    self.chart_generator_instance = get_chart_generator(self.output_dir)

                # 创建图表配置
                chart_type_enum = ChartType(chart_type)
                layout_enum = ChartLayout(layout)

                # 决定渲染方法
                render_method = self.chart_generator_instance.determine_render_method(chart_type_enum)

                config = ChartConfig(
                    chart_type=chart_type_enum,
                    data=ChartData(
                        title=title,
                        data=data_dict,
                        data_source="LLM Generated"
                    ),
                    layout=layout_enum,
                    render_method=render_method
                )

                # 生成图表
                chart_path, native_config = self.chart_generator_instance.generate_chart(config)

                return {
                    "success": True,
                    "chart_type": chart_type,
                    "chart_path": chart_path,
                    "native_config": native_config,
                    "layout": layout,
                    "render_method": render_method.value
                }

            except Exception as e:
                self.error_tracker.record_error(
                    error_type=ErrorType.CHART_ERROR,
                    severity=ErrorSeverity.ERROR,
                    component="generate_chart_tool",
                    message=str(e),
                    recovery_action="Skip chart generation",
                    recovered=True
                )
                return {"success": False, "message": str(e)}

        @tool
        def finish() -> Dict[str, str]:
            """完成当前幻灯片的处理"""
            return {"status": "finished"}

        tools = [search_image, fetch_data, generate_chart, finish]
        memory = MemorySaver()

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
        """增强大纲"""
        enhanced = EnhancedOutline(slides=outline.slides, images=[], charts=[])

        for slide_index, slide in enumerate(outline.slides):
            try:
                self._current_image_context = build_image_query_context(
                    topic=slide.title,
                    slide_index=slide_index,
                    slide=slide,
                )

                system_prompt = f"""你是一个幻灯片内容增强助手。分析当前幻灯片，决定需要添加什么内容。

当前幻灯片信息：
- 索引：{slide_index}
- 标题：{slide.title}
- 类型：{slide.slide_type}
- 内容：{slide.content if hasattr(slide, 'content') else slide.subtitle}

配色方案：主色 {colors.colors['primary']}，次色 {colors.colors['secondary']}

可用工具：
1. search_image(keywords, position, size_width, size_height) - 搜索图片
2. fetch_data(query, data_type) - 获取数据
3. generate_chart(chart_type, chart_data, title, layout) - 生成图表
4. finish() - 完成处理

决策指南：
- 封面页（cover）：通常需要背景图片
- 数据页（data）：需要图表展示数据
- 内容页（content）：可选择性添加图片或图表
- 如果需要展示统计数据，先用 fetch_data 获取数据，再用 generate_chart 生成图表
- 使用 finish() 结束当前页处理

请分析并决定需要添加什么内容。"""

                user_message = f"请为第 {slide_index + 1} 页幻灯片决定增强内容。"

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
                            # 查找对应的工具响应
                            for response_msg in messages:
                                if (hasattr(response_msg, 'tool_call_id') and
                                    response_msg.tool_call_id == tool_call['id']):
                                    content = response_msg.content
                                    if isinstance(content, str):
                                        try:
                                            content = json.loads(content)
                                        except:
                                            pass

                                    if isinstance(content, dict) and content.get('success'):
                                        # 处理图片
                                        if tool_call['name'] == 'search_image':
                                            enhanced.images.append(ImageSuggestion(
                                                slide_index=slide_index,
                                                image_url=content['image_url'],
                                                description=content['description'],
                                                position=content['position'],
                                                size=tuple(content['size']),
                                                source=content['source']
                                            ))

                                        # 处理图表
                                        elif tool_call['name'] == 'generate_chart':
                                            enhanced.charts.append(ChartSuggestion(
                                                slide_index=slide_index,
                                                chart_type=content['chart_type'],
                                                data=content.get('native_config', {}),
                                                layout=content['layout'],
                                                render_method=content['render_method'],
                                                chart_path=content.get('chart_path'),
                                                native_config=content.get('native_config')
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
