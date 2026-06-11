"""
交互式设计方案选择器
提供预设方案展示 + 用户自定义输入
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .design_system.colors import COLOR_SCHEMES, ColorScheme, ColorMood
from .design_system.typography import TypographyScale, SpacingScale, LayoutGrid


@dataclass
class DesignSpec:
    """完整设计规范（用户最终确认的结果）"""
    color_scheme: ColorScheme
    layout_type: str          # single / two_column / sidebar_left / sidebar_right / header_content
    visual_style: str         # minimalist / bold / elegant / corporate / playful
    heading_font: str
    body_font: str
    typography: TypographyScale = field(default_factory=TypographyScale)
    spacing: SpacingScale = field(default_factory=SpacingScale)
    grid: LayoutGrid = field(default_factory=LayoutGrid)


# ──────────────────────────────────────────────
# 预设配色方案展示
# ──────────────────────────────────────────────

def _show_color_options() -> None:
    print("\n" + "═" * 56)
    print("  可用配色方案")
    print("═" * 56)
    for i, (key, scheme) in enumerate(COLOR_SCHEMES.items(), 1):
        print(f"  [{i}] {scheme.name:<12}  {scheme.description}")
    print(f"  [{len(COLOR_SCHEMES)+1}] 自定义配色（手动输入色值）")
    print("═" * 56)


def _pick_color_scheme() -> ColorScheme:
    _show_color_options()
    keys = list(COLOR_SCHEMES.keys())
    while True:
        raw = input("请选择配色方案编号：").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(keys):
                return COLOR_SCHEMES[keys[idx - 1]]
            if idx == len(keys) + 1:
                return _custom_color_scheme()
        print("  ✗ 无效输入，请重新选择")


def _custom_color_scheme() -> ColorScheme:
    print("\n  自定义配色方案（输入十六进制色值，如 #1976D2）")

    def ask(prompt: str, default: str) -> str:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val if val else default

    return ColorScheme(
        name="自定义",
        mood=ColorMood.MODERN,
        primary=ask("主色 (primary)", "#1976D2"),
        secondary=ask("辅色 (secondary)", "#424242"),
        accent=ask("强调色 (accent)", "#FFC107"),
        background=ask("背景色 (background)", "#FFFFFF"),
        surface=ask("表面色 (surface)", "#F5F5F5"),
        text_primary=ask("主要文字色 (text_primary)", "#212121"),
        text_secondary=ask("次要文字色 (text_secondary)", "#757575"),
        text_disabled=ask("禁用文字色 (text_disabled)", "#BDBDBD"),
        border=ask("边框色 (border)", "#E0E0E0"),
        success=ask("成功色 (success)", "#4CAF50"),
        warning=ask("警告色 (warning)", "#FF9800"),
        error=ask("错误色 (error)", "#F44336"),
        description="用户自定义配色",
    )


# ──────────────────────────────────────────────
# 布局选择
# ──────────────────────────────────────────────

_LAYOUTS = [
    ("single",        "单栏   — 全宽单区域，适合标题页/全图页"),
    ("two_column",    "双栏   — 左右各占 50%，适合对比说明"),
    ("sidebar_left",  "左侧栏 — 左 4 列导航 + 右 8 列内容"),
    ("sidebar_right", "右侧栏 — 左 8 列内容 + 右 4 列补充"),
    ("header_content","标题内容 — 顶部标题区 + 下方大内容区"),
]


def _pick_layout() -> str:
    print("\n" + "═" * 56)
    print("  布局类型")
    print("═" * 56)
    for i, (key, desc) in enumerate(_LAYOUTS, 1):
        print(f"  [{i}] {desc}")
    print("═" * 56)
    while True:
        raw = input("请选择布局编号：").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(_LAYOUTS):
            return _LAYOUTS[int(raw) - 1][0]
        print("  ✗ 无效输入，请重新选择")


# ──────────────────────────────────────────────
# 视觉风格选择
# ──────────────────────────────────────────────

_STYLES = [
    ("minimalist", "极简   — 大量留白，字体驱动"),
    ("bold",       "大胆   — 强对比色块，视觉冲击"),
    ("elegant",    "优雅   — 柔和渐变，精致细节"),
    ("corporate",  "商务   — 规整严谨，专业感强"),
    ("playful",    "活泼   — 圆角图形，明快色彩"),
]


def _pick_visual_style() -> str:
    print("\n" + "═" * 56)
    print("  视觉风格")
    print("═" * 56)
    for i, (key, desc) in enumerate(_STYLES, 1):
        print(f"  [{i}] {desc}")
    print("═" * 56)
    while True:
        raw = input("请选择风格编号：").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(_STYLES):
            return _STYLES[int(raw) - 1][0]
        print("  ✗ 无效输入，请重新选择")


# ──────────────────────────────────────────────
# 字体选择
# ──────────────────────────────────────────────

_HEADING_FONTS = [
    ("'PingFang SC', 'Microsoft YaHei', sans-serif",  "苹方 / 微软雅黑（中文首选）"),
    ("'Source Han Sans CN', 'Noto Sans CJK SC', sans-serif", "思源黑体（正式/学术）"),
    ("'Inter', 'Roboto', Arial, sans-serif",           "Inter / Roboto（英文现代）"),
    ("'Georgia', 'Times New Roman', serif",            "Georgia（英文衬线/学术）"),
]

_BODY_FONTS = [
    ("'PingFang SC', 'Microsoft YaHei', sans-serif",  "苹方 / 微软雅黑"),
    ("'Source Han Sans CN', sans-serif",              "思源黑体"),
    ("'Inter', Arial, sans-serif",                    "Inter（英文无衬线）"),
    ("'Georgia', serif",                              "Georgia（英文衬线）"),
]


def _pick_font(label: str, options: list[tuple[str, str]]) -> str:
    print(f"\n  {label}")
    for i, (_, desc) in enumerate(options, 1):
        print(f"  [{i}] {desc}")
    print(f"  [{len(options)+1}] 自定义（手动输入 CSS font-family）")
    while True:
        raw = input(f"请选择{label}编号：").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
            if idx == len(options) + 1:
                return input("  输入 CSS font-family 值：").strip()
        print("  ✗ 无效输入，请重新选择")


# ──────────────────────────────────────────────
# 公开接口
# ──────────────────────────────────────────────

def select_design_spec() -> DesignSpec:
    """
    交互式收集用户设计偏好，返回完整 DesignSpec。
    每个维度都提供预设选项 + 自定义入口。
    """
    print("\n🎨  SlideForge 设计规范配置向导")

    color = _pick_color_scheme()
    layout = _pick_layout()
    style = _pick_visual_style()
    heading_font = _pick_font("标题字体", _HEADING_FONTS)
    body_font = _pick_font("正文字体", _BODY_FONTS)

    spec = DesignSpec(
        color_scheme=color,
        layout_type=layout,
        visual_style=style,
        heading_font=heading_font,
        body_font=body_font,
    )

    _print_summary(spec)
    return spec


def _print_summary(spec: DesignSpec) -> None:
    print("\n" + "═" * 56)
    print("  ✅ 设计规范确认")
    print("═" * 56)
    print(f"  配色方案  {spec.color_scheme.name}  ({spec.color_scheme.description})")
    print(f"  布局类型  {spec.layout_type}")
    print(f"  视觉风格  {spec.visual_style}")
    print(f"  标题字体  {spec.heading_font[:40]}")
    print(f"  正文字体  {spec.body_font[:40]}")
    print(f"  主色      {spec.color_scheme.primary}")
    print(f"  背景色    {spec.color_scheme.background}")
    print("═" * 56 + "\n")
