"""
图表生成工具 - 支持 python-pptx 原生图表和 matplotlib 图表
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from enum import Enum
import platform
import matplotlib
matplotlib.use('Agg')  # 无 GUI 后端
import matplotlib.pyplot as plt
from matplotlib import font_manager
import seaborn as sns
from pydantic import BaseModel, field_validator


def _setup_chinese_font():
    """配置 matplotlib 支持中文字体"""
    system = platform.system()

    # 按操作系统选择中文字体
    if system == 'Darwin':  # macOS
        chinese_fonts = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Kaiti SC', 'Songti SC']
    elif system == 'Windows':
        chinese_fonts = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi']
    else:  # Linux
        chinese_fonts = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'Noto Sans CJK SC', 'Droid Sans Fallback']

    # 找到第一个可用的中文字体
    available_fonts = {f.name for f in font_manager.fontManager.ttflist}

    for font in chinese_fonts:
        if font in available_fonts:
            # 重要：使用列表形式，确保中文字体在最前面
            plt.rcParams['font.sans-serif'] = [font] + plt.rcParams['font.sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
            # 强制 seaborn 也使用相同的字体配置
            sns.set_style("whitegrid", {'font.sans-serif': [font] + plt.rcParams['font.sans-serif']})
            return font

    # 如果都不可用，尝试使用任何包含 "SC" 的字体
    for f in font_manager.fontManager.ttflist:
        if 'SC' in f.name or 'CJK' in f.name:
            plt.rcParams['font.sans-serif'] = [f.name] + plt.rcParams['font.sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
            return f.name

    plt.rcParams['axes.unicode_minus'] = False
    return None


# 初始化时配置中文字体（必须在 seaborn 导入后）
_setup_chinese_font()


class ChartType(str, Enum):
    """图表类型"""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    TABLE = "table"
    HEATMAP = "heatmap"
    BOX = "box"
    RADAR = "radar"


class ChartLayout(str, Enum):
    """图表布局"""
    FULLPAGE = "fullpage"
    INLINE_LEFT = "inline-left"
    INLINE_RIGHT = "inline-right"
    DASHBOARD = "dashboard"


class ChartRenderMethod(str, Enum):
    """图表渲染方法"""
    NATIVE = "native"  # python-pptx 原生
    MATPLOTLIB = "matplotlib"  # matplotlib 图片


class ChartData(BaseModel):
    """图表数据"""
    title: str
    data: Dict[str, Any]
    data_source: str
    timestamp: Optional[str] = None

    @field_validator("data", mode="before")
    @classmethod
    def normalize_row_list(cls, value):
        if not isinstance(value, list):
            return value
        rows = [row for row in value if isinstance(row, dict)]
        if not rows:
            return {"values": value}

        headers = list(rows[0].keys())
        category_key = next(
            (key for key in ("category", "name", "label", "维度", "指标", "项目", "年份", "year") if key in headers),
            headers[0],
        )

        def number_or_none(raw):
            if isinstance(raw, (int, float)):
                return raw
            if isinstance(raw, str):
                cleaned = raw.replace(",", "").replace("%", "").strip()
                try:
                    return float(cleaned)
                except ValueError:
                    return None
            return None

        numeric_keys = [
            key for key in headers
            if key != category_key and any(number_or_none(row.get(key)) is not None for row in rows)
        ]
        categories = [str(row.get(category_key, "")) for row in rows]
        normalized = {
            "categories": categories,
            "headers": headers,
            "rows": [[row.get(header, "") for header in headers] for row in rows],
        }
        if numeric_keys:
            normalized["series"] = [
                {
                    "name": key,
                    "values": [
                        number_or_none(row.get(key)) if number_or_none(row.get(key)) is not None else 0
                        for row in rows
                    ],
                }
                for key in numeric_keys
            ]
            if len(numeric_keys) == 1:
                normalized["values"] = normalized["series"][0]["values"]
        return normalized


class ChartConfig(BaseModel):
    """图表配置"""
    chart_type: ChartType
    data: ChartData
    layout: ChartLayout
    render_method: ChartRenderMethod
    colors: Optional[List[str]] = None
    width: int = 800
    height: int = 600


class ChartGenerator:
    """图表生成器"""

    def __init__(self, output_dir: Path, color_scheme: Optional[Dict[str, str]] = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.color_scheme = color_scheme or {}

        # 设置默认颜色
        self.default_colors = [
            '#7c3aed',  # primary
            '#f59e0b',  # accent
            '#10b981',  # success
            '#ef4444',  # error
            '#3b82f6',  # info
        ]

    def determine_render_method(self, chart_type: ChartType) -> ChartRenderMethod:
        """
        自动决定渲染方法

        简单图表用 native，复杂图表用 matplotlib
        """
        simple_charts = {ChartType.BAR, ChartType.LINE, ChartType.PIE, ChartType.SCATTER, ChartType.TABLE}

        if chart_type in simple_charts:
            return ChartRenderMethod.NATIVE
        else:
            return ChartRenderMethod.MATPLOTLIB

    def generate_chart(self, config: ChartConfig) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        生成图表

        Args:
            config: 图表配置

        Returns:
            (图表文件路径或 None, 原生图表配置或空字典)
        """
        if config.render_method == ChartRenderMethod.NATIVE:
            return None, self._generate_native_config(config)
        else:
            chart_path = self._generate_matplotlib_chart(config)
            return str(chart_path), {}

    def _generate_native_config(self, config: ChartConfig) -> Dict[str, Any]:
        """生成 python-pptx 原生图表配置"""
        chart_data = config.data.data

        if config.chart_type == ChartType.BAR:
            return {
                "type": "bar",
                "categories": chart_data.get("categories", []),
                "series": chart_data.get("series", []),
                "title": config.data.title
            }

        elif config.chart_type == ChartType.LINE:
            return {
                "type": "line",
                "categories": chart_data.get("categories", []),
                "series": chart_data.get("series", []),
                "title": config.data.title
            }

        elif config.chart_type == ChartType.PIE:
            return {
                "type": "pie",
                "categories": chart_data.get("categories", []),
                "values": chart_data.get("values", []),
                "title": config.data.title
            }

        elif config.chart_type == ChartType.SCATTER:
            return {
                "type": "scatter",
                "x_values": chart_data.get("x", []),
                "y_values": chart_data.get("y", []),
                "title": config.data.title
            }

        elif config.chart_type == ChartType.TABLE:
            return {
                "type": "table",
                "headers": chart_data.get("headers", []),
                "rows": chart_data.get("rows", []),
                "title": config.data.title
            }

        return {}

    def _generate_matplotlib_chart(self, config: ChartConfig) -> Path:
        """使用 matplotlib 生成图表"""
        chart_data = config.data.data
        colors = config.colors or self.default_colors

        # 每次生成图表前重新配置中文字体（因为 seaborn 可能重置）
        _setup_chinese_font()

        # 设置样式
        sns.set_style("whitegrid")

        # 再次确保中文字体配置（seaborn 会重置）
        _setup_chinese_font()

        fig, ax = plt.subplots(figsize=(config.width/100, config.height/100), dpi=100)

        try:
            if config.chart_type == ChartType.BAR:
                self._plot_bar(ax, chart_data, colors)

            elif config.chart_type == ChartType.LINE:
                self._plot_line(ax, chart_data, colors)

            elif config.chart_type == ChartType.PIE:
                self._plot_pie(ax, chart_data, colors)

            elif config.chart_type == ChartType.SCATTER:
                self._plot_scatter(ax, chart_data, colors)

            elif config.chart_type == ChartType.HEATMAP:
                self._plot_heatmap(ax, chart_data, colors)

            elif config.chart_type == ChartType.BOX:
                self._plot_box(ax, chart_data, colors)

            elif config.chart_type == ChartType.RADAR:
                self._plot_radar(chart_data, colors, fig)

            # 设置标题
            if config.chart_type != ChartType.RADAR:  # radar 图有自己的标题处理
                ax.set_title(config.data.title, fontsize=14, fontweight='bold', pad=20)

            # 保存图表
            chart_filename = f"chart_{config.chart_type.value}_{hash(config.data.title)}.png"
            chart_path = self.output_dir / chart_filename

            plt.tight_layout()
            plt.savefig(chart_path, dpi=100, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            return chart_path

        except Exception as e:
            plt.close(fig)
            raise Exception(f"Failed to generate matplotlib chart: {e}")

    def _plot_bar(self, ax, data: Dict, colors: List[str]):
        """绘制条形图"""
        categories = data.get("categories", [])
        series = data.get("series", [])

        x = range(len(categories))
        width = 0.8 / len(series)

        for i, s in enumerate(series):
            values = s.get("values", [])
            offset = (i - len(series)/2 + 0.5) * width
            ax.bar([pos + offset for pos in x], values, width,
                   label=s.get("name", f"Series {i+1}"),
                   color=colors[i % len(colors)])

        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend()

    def _plot_line(self, ax, data: Dict, colors: List[str]):
        """绘制折线图"""
        categories = data.get("categories", [])
        series = data.get("series", [])

        for i, s in enumerate(series):
            values = s.get("values", [])
            ax.plot(categories, values,
                    label=s.get("name", f"Series {i+1}"),
                    color=colors[i % len(colors)],
                    marker='o',
                    linewidth=2)

        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_pie(self, ax, data: Dict, colors: List[str]):
        """绘制饼图"""
        categories = data.get("categories", [])
        values = data.get("values", [])

        ax.pie(values, labels=categories, autopct='%1.1f%%',
               colors=colors[:len(values)],
               startangle=90)

    def _plot_scatter(self, ax, data: Dict, colors: List[str]):
        """绘制散点图"""
        x = data.get("x", [])
        y = data.get("y", [])

        ax.scatter(x, y, c=colors[0], alpha=0.6, s=100)
        ax.grid(True, alpha=0.3)

    def _plot_heatmap(self, ax, data: Dict, colors: List[str]):
        """绘制热图"""
        import numpy as np

        matrix = np.array(data.get("matrix", [[]]))
        row_labels = data.get("row_labels", [f"Row {i+1}" for i in range(len(matrix))])
        col_labels = data.get("col_labels", [f"Col {i+1}" for i in range(len(matrix[0]) if len(matrix) > 0 else 0)])

        sns.heatmap(matrix, annot=True, fmt='.1f', cmap='YlOrRd',
                    xticklabels=col_labels, yticklabels=row_labels,
                    ax=ax)

    def _plot_box(self, ax, data: Dict, colors: List[str]):
        """绘制箱线图"""
        series = data.get("series", [])
        values_list = [s.get("values", []) for s in series]
        labels = [s.get("name", f"Series {i+1}") for i, s in enumerate(series)]

        bp = ax.boxplot(values_list, labels=labels, patch_artist=True)

        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)

    def _plot_radar(self, data: Dict, colors: List[str], fig):
        """绘制雷达图"""
        import numpy as np

        categories = data.get("categories", [])
        series = data.get("series", [])

        N = len(categories)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]  # 闭合

        ax = fig.add_subplot(111, projection='polar')

        for i, s in enumerate(series):
            values = s.get("values", [])
            values += values[:1]  # 闭合
            ax.plot(angles, values, 'o-', linewidth=2,
                    label=s.get("name", f"Series {i+1}"),
                    color=colors[i % len(colors)])
            ax.fill(angles, values, alpha=0.25, color=colors[i % len(colors)])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_ylim(0, 100)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        ax.set_title(data.get("title", "Radar Chart"), pad=20)


# 创建全局实例
_chart_generator = None


def get_chart_generator(output_dir: Path, color_scheme: Optional[Dict[str, str]] = None) -> ChartGenerator:
    """获取图表生成器单例"""
    global _chart_generator
    if _chart_generator is None:
        _chart_generator = ChartGenerator(output_dir, color_scheme)
    return _chart_generator
