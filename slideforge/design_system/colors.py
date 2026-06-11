"""
设计系统 - 配色方案库
提供专业的配色组合，确保视觉和谐性
"""

from dataclasses import dataclass
from enum import Enum
from typing import List


class ColorMood(Enum):
    """配色情绪类型"""
    PROFESSIONAL = "professional"  # 专业商务
    CREATIVE = "creative"  # 创意活力
    ACADEMIC = "academic"  # 学术严谨
    MODERN = "modern"  # 现代简约
    WARM = "warm"  # 温暖亲和
    TECH = "tech"  # 科技未来


@dataclass
class ColorScheme:
    """配色方案"""
    name: str
    mood: ColorMood
    primary: str  # 主色
    secondary: str  # 辅色
    accent: str  # 强调色
    background: str  # 背景色
    surface: str  # 表面色
    text_primary: str  # 主要文本
    text_secondary: str  # 次要文本
    text_disabled: str  # 禁用文本
    border: str  # 边框色
    success: str  # 成功色
    warning: str  # 警告色
    error: str  # 错误色
    description: str  # 方案描述


# 专业配色方案库
COLOR_SCHEMES = {
    "blue_professional": ColorScheme(
        name="蓝色专业",
        mood=ColorMood.PROFESSIONAL,
        primary="#1976D2",
        secondary="#424242",
        accent="#FFC107",
        background="#FFFFFF",
        surface="#F5F5F5",
        text_primary="#212121",
        text_secondary="#757575",
        text_disabled="#BDBDBD",
        border="#E0E0E0",
        success="#4CAF50",
        warning="#FF9800",
        error="#F44336",
        description="经典蓝色商务风格，适合企业汇报和商业计划"
    ),

    "green_creative": ColorScheme(
        name="绿色创意",
        mood=ColorMood.CREATIVE,
        primary="#00897B",
        secondary="#5E35B1",
        accent="#FF6F00",
        background="#FAFAFA",
        surface="#FFFFFF",
        text_primary="#263238",
        text_secondary="#607D8B",
        text_disabled="#B0BEC5",
        border="#CFD8DC",
        success="#66BB6A",
        warning="#FFA726",
        error="#EF5350",
        description="活力绿配紫色，适合创意设计和营销方案"
    ),

    "purple_tech": ColorScheme(
        name="紫色科技",
        mood=ColorMood.TECH,
        primary="#5E35B1",
        secondary="#1E88E5",
        accent="#00E5FF",
        background="#0D1117",
        surface="#161B22",
        text_primary="#E6EDF3",
        text_secondary="#8B949E",
        text_disabled="#484F58",
        border="#30363D",
        success="#238636",
        warning="#D29922",
        error="#DA3633",
        description="深色科技风，适合技术演示和产品发布"
    ),

    "orange_warm": ColorScheme(
        name="橙色温暖",
        mood=ColorMood.WARM,
        primary="#F57C00",
        secondary="#5D4037",
        accent="#FDD835",
        background="#FFF8E1",
        surface="#FFFFFF",
        text_primary="#3E2723",
        text_secondary="#6D4C41",
        text_disabled="#A1887F",
        border="#D7CCC8",
        success="#7CB342",
        warning="#FFB300",
        error="#E64A19",
        description="温暖橙棕色调，适合教育培训和用户分享"
    ),

    "gray_modern": ColorScheme(
        name="现代灰",
        mood=ColorMood.MODERN,
        primary="#455A64",
        secondary="#00ACC1",
        accent="#FF5722",
        background="#ECEFF1",
        surface="#FFFFFF",
        text_primary="#263238",
        text_secondary="#546E7A",
        text_disabled="#90A4AE",
        border="#CFD8DC",
        success="#26A69A",
        warning="#FFA726",
        error="#EF5350",
        description="简约灰色系，适合设计作品和产品展示"
    ),

    "teal_academic": ColorScheme(
        name="青色学术",
        mood=ColorMood.ACADEMIC,
        primary="#00695C",
        secondary="#3949AB",
        accent="#C2185B",
        background="#FFFFFF",
        surface="#F1F8F6",
        text_primary="#1B5E20",
        text_secondary="#455A64",
        text_disabled="#90A4AE",
        border="#B2DFDB",
        success="#388E3C",
        warning="#F57C00",
        error="#D32F2F",
        description="学术青色，适合研究报告和论文演示"
    ),
}


def get_color_scheme(mood: ColorMood = None, name: str = None) -> ColorScheme:
    """
    获取配色方案

    Args:
        mood: 根据情绪类型选择
        name: 根据方案名称选择

    Returns:
        ColorScheme 对象
    """
    if name and name in COLOR_SCHEMES:
        return COLOR_SCHEMES[name]

    if mood:
        for scheme in COLOR_SCHEMES.values():
            if scheme.mood == mood:
                return scheme

    # 默认返回专业蓝
    return COLOR_SCHEMES["blue_professional"]


def get_schemes_by_mood(mood: ColorMood) -> List[ColorScheme]:
    """获取指定情绪的所有配色方案"""
    return [s for s in COLOR_SCHEMES.values() if s.mood == mood]


def list_all_schemes() -> List[ColorScheme]:
    """列出所有配色方案"""
    return list(COLOR_SCHEMES.values())
