"""
设计系统 - 排版规则
基于专业设计原则的排版规范
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class TypographyScale:
    """排版尺寸体系"""
    # 标题层级 (px)
    h1: int = 48
    h2: int = 36
    h3: int = 28
    h4: int = 22
    h5: int = 18
    h6: int = 16

    # 正文
    body_large: int = 18
    body: int = 16
    body_small: int = 14
    caption: int = 12

    # 行高比例
    heading_line_height: float = 1.2
    body_line_height: float = 1.6
    caption_line_height: float = 1.4


@dataclass
class SpacingScale:
    """间距体系（基于 8px 网格）"""
    xs: int = 4
    sm: int = 8
    md: int = 16
    lg: int = 24
    xl: int = 32
    xxl: int = 48
    xxxl: int = 64


@dataclass
class LayoutGrid:
    """布局网格系统"""
    # 16:9 幻灯片标准尺寸
    width: int = 1280
    height: int = 720

    # 安全边距（避免内容被裁切）
    safe_margin_horizontal: int = 60
    safe_margin_vertical: int = 40

    # 栅格列数
    columns: int = 12
    gutter: int = 20  # 列间距

    @property
    def content_width(self) -> int:
        """可用内容宽度"""
        return self.width - 2 * self.safe_margin_horizontal

    @property
    def content_height(self) -> int:
        """可用内容高度"""
        return self.height - 2 * self.safe_margin_vertical

    def get_column_width(self, span: int = 1) -> int:
        """计算指定列跨度的宽度"""
        total_gutter = self.gutter * (self.columns - 1)
        column_width = (self.content_width - total_gutter) / self.columns
        return int(column_width * span + self.gutter * (span - 1))


@dataclass
class FontFamily:
    """字体族"""
    # 中文字体栈
    chinese_primary: str = "'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', sans-serif"
    chinese_secondary: str = "'Source Han Sans CN', 'Noto Sans CJK SC', sans-serif"

    # 英文字体栈
    english_primary: str = "'Inter', 'Roboto', 'Helvetica Neue', Arial, sans-serif"
    english_secondary: str = "'Georgia', 'Times New Roman', serif"

    # 等宽字体（代码）
    monospace: str = "'Fira Code', 'Consolas', 'Monaco', monospace"


class TypographyRules:
    """排版规则引擎"""

    def __init__(self):
        self.scale = TypographyScale()
        self.spacing = SpacingScale()
        self.grid = LayoutGrid()
        self.fonts = FontFamily()

    def get_heading_style(self, level: int = 1) -> Dict[str, str]:
        """
        获取标题样式

        Args:
            level: 标题级别 1-6

        Returns:
            CSS 样式字典
        """
        sizes = {
            1: self.scale.h1,
            2: self.scale.h2,
            3: self.scale.h3,
            4: self.scale.h4,
            5: self.scale.h5,
            6: self.scale.h6,
        }

        size = sizes.get(level, self.scale.body)

        return {
            "font-size": f"{size}px",
            "line-height": str(self.scale.heading_line_height),
            "font-weight": "700" if level <= 2 else "600",
            "margin-bottom": f"{self.spacing.md}px",
            "letter-spacing": "-0.02em" if level <= 2 else "0",
        }

    def get_body_style(self, size: str = "normal") -> Dict[str, str]:
        """
        获取正文样式

        Args:
            size: 'large', 'normal', 'small'

        Returns:
            CSS 样式字典
        """
        sizes = {
            "large": self.scale.body_large,
            "normal": self.scale.body,
            "small": self.scale.body_small,
        }

        font_size = sizes.get(size, self.scale.body)

        return {
            "font-size": f"{font_size}px",
            "line-height": str(self.scale.body_line_height),
            "font-weight": "400",
            "letter-spacing": "0.01em",
        }

    def calculate_layout(
        self, layout_type: str = "single"
    ) -> Dict[str, Tuple[int, int, int, int]]:
        """
        计算布局区域坐标 (x, y, width, height)

        Args:
            layout_type: 'single', 'two_column', 'sidebar_left', 'sidebar_right'

        Returns:
            布局区域字典
        """
        g = self.grid
        safe_x = g.safe_margin_horizontal
        safe_y = g.safe_margin_vertical
        content_w = g.content_width
        content_h = g.content_height

        layouts = {
            "single": {
                "main": (safe_x, safe_y, content_w, content_h),
            },
            "two_column": {
                "left": (safe_x, safe_y, content_w // 2 - g.gutter // 2, content_h),
                "right": (
                    safe_x + content_w // 2 + g.gutter // 2,
                    safe_y,
                    content_w // 2 - g.gutter // 2,
                    content_h,
                ),
            },
            "sidebar_left": {
                "sidebar": (safe_x, safe_y, g.get_column_width(4), content_h),
                "main": (
                    safe_x + g.get_column_width(4) + g.gutter,
                    safe_y,
                    g.get_column_width(8),
                    content_h,
                ),
            },
            "sidebar_right": {
                "main": (safe_x, safe_y, g.get_column_width(8), content_h),
                "sidebar": (
                    safe_x + g.get_column_width(8) + g.gutter,
                    safe_y,
                    g.get_column_width(4),
                    content_h,
                ),
            },
            "header_content": {
                "header": (safe_x, safe_y, content_w, 100),
                "content": (safe_x, safe_y + 120, content_w, content_h - 120),
            },
        }

        return layouts.get(layout_type, layouts["single"])

    def get_spacing(self, size: str = "md") -> int:
        """获取标准间距值"""
        sizes = {
            "xs": self.spacing.xs,
            "sm": self.spacing.sm,
            "md": self.spacing.md,
            "lg": self.spacing.lg,
            "xl": self.spacing.xl,
            "xxl": self.spacing.xxl,
            "xxxl": self.spacing.xxxl,
        }
        return sizes.get(size, self.spacing.md)


# 全局实例
typography_rules = TypographyRules()
