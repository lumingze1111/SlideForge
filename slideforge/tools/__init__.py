"""
SlideForge 工具模块
"""

from slideforge.tools.image_search import (
    ImageSearchTool,
    ImageResult,
    ImageSource,
    ImageSearchError,
    get_image_search_tool
)
from slideforge.tools.image_matching import (
    ImageQueryContext,
    SelectedImage,
    build_image_query_context,
    build_image_queries,
    choose_best_image,
    score_image_candidate,
    search_best_image,
)
from slideforge.tools.data_fetch import (
    web_search,
    wikipedia_fetch,
    web_scrape,
    execute_python_safe,
    fetch_sports_data,
    DataFetchError
)
from slideforge.tools.chart_generator import (
    ChartGenerator,
    ChartType,
    ChartLayout,
    ChartRenderMethod,
    ChartData,
    ChartConfig,
    get_chart_generator
)

__all__ = [
    # Image search
    "ImageSearchTool",
    "ImageResult",
    "ImageSource",
    "ImageSearchError",
    "get_image_search_tool",
    "ImageQueryContext",
    "SelectedImage",
    "build_image_query_context",
    "build_image_queries",
    "choose_best_image",
    "score_image_candidate",
    "search_best_image",
    # Data fetch
    "web_search",
    "wikipedia_fetch",
    "web_scrape",
    "execute_python_safe",
    "fetch_sports_data",
    "DataFetchError",
    # Chart generator
    "ChartGenerator",
    "ChartType",
    "ChartLayout",
    "ChartRenderMethod",
    "ChartData",
    "ChartConfig",
    "get_chart_generator",
]
