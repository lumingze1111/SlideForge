"""
智能排版策略引擎 - 根据 slide_type 和媒体内容计算最佳布局位置
"""

from dataclasses import dataclass
from typing import Optional

SLIDE_W = 1280
SLIDE_H = 720


@dataclass
class MediaSlot:
    """媒体插槽 - 描述可用于放置图片/图表的区域"""
    x: int
    y: int
    width: int
    height: int
    z_index: int
    slot_type: str  # "background" / "inline-right" / "inline-left" / "card-replace"
    opacity: float = 1.0


@dataclass
class LayoutDecision:
    """排版决策结果"""
    image_slot: Optional[MediaSlot]
    chart_slot: Optional[MediaSlot]
    content_width_pct: float  # 内容区域宽度百分比 (0-1)


def compute_layout(
    slide_type: str,
    has_image: bool,
    has_chart: bool,
    image_position: str = "auto",
    chart_layout: str = "auto",
) -> LayoutDecision:
    """
    根据 slide_type 和媒体内容计算最佳排版方案。

    image_position="auto" 时根据策略矩阵自动选择。
    """
    if slide_type == "cover":
        return _layout_cover(has_image, has_chart, image_position)
    elif slide_type == "content":
        return _layout_content(has_image, has_chart, image_position, chart_layout)
    elif slide_type == "data":
        return _layout_data(has_image, has_chart, image_position, chart_layout)
    elif slide_type == "two_column":
        return _layout_two_column(has_image, has_chart, image_position, chart_layout)
    elif slide_type == "section":
        return _layout_section(has_image, has_chart, image_position)
    elif slide_type == "closing":
        return _layout_closing(has_image, has_chart, image_position)
    else:
        return _layout_content(has_image, has_chart, image_position, chart_layout)


def _layout_cover(has_image, has_chart, image_position):
    """cover 页：图片做背景，不放图表"""
    image_slot = None
    if has_image:
        if image_position in ("auto", "background"):
            image_slot = MediaSlot(
                x=0, y=0, width=SLIDE_W, height=SLIDE_H,
                z_index=0, slot_type="background", opacity=0.25
            )
        elif image_position == "right":
            image_slot = MediaSlot(
                x=750, y=80, width=460, height=560,
                z_index=1, slot_type="inline-right", opacity=0.9
            )

    return LayoutDecision(
        image_slot=image_slot,
        chart_slot=None,
        content_width_pct=1.0
    )


def _layout_section(has_image, has_chart, image_position):
    """section 页：图片做背景或放右侧"""
    image_slot = None
    if has_image:
        if image_position in ("auto", "background"):
            image_slot = MediaSlot(
                x=0, y=0, width=SLIDE_W, height=SLIDE_H,
                z_index=0, slot_type="background", opacity=0.2
            )
        elif image_position == "right":
            image_slot = MediaSlot(
                x=780, y=100, width=420, height=520,
                z_index=1, slot_type="inline-right", opacity=1.0
            )

    return LayoutDecision(
        image_slot=image_slot,
        chart_slot=None,
        content_width_pct=1.0
    )


def _layout_content(has_image, has_chart, image_position, chart_layout):
    """content 页：标题+bullets 左侧，右侧放媒体"""
    image_slot = None
    chart_slot = None
    content_width_pct = 1.0

    if has_chart:
        chart_slot = MediaSlot(
            x=700, y=100, width=520, height=520,
            z_index=1, slot_type="inline-right"
        )
        content_width_pct = 0.52

        if has_image:
            image_slot = MediaSlot(
                x=0, y=0, width=SLIDE_W, height=SLIDE_H,
                z_index=0, slot_type="background", opacity=0.12
            )
    elif has_image:
        if image_position in ("right", "auto"):
            image_slot = MediaSlot(
                x=720, y=100, width=480, height=520,
                z_index=1, slot_type="inline-right", opacity=1.0
            )
            content_width_pct = 0.54
        elif image_position == "left":
            image_slot = MediaSlot(
                x=80, y=100, width=480, height=520,
                z_index=1, slot_type="inline-left", opacity=1.0
            )
            content_width_pct = 0.54
        elif image_position == "background":
            image_slot = MediaSlot(
                x=0, y=0, width=SLIDE_W, height=SLIDE_H,
                z_index=0, slot_type="background", opacity=0.15
            )

    return LayoutDecision(
        image_slot=image_slot,
        chart_slot=chart_slot,
        content_width_pct=content_width_pct
    )


def _layout_data(has_image, has_chart, image_position, chart_layout):
    """data 页：图表替换左侧数据卡区域"""
    image_slot = None
    chart_slot = None

    if has_chart:
        chart_slot = MediaSlot(
            x=80, y=130, width=540, height=480,
            z_index=2, slot_type="card-replace"
        )

    if has_image:
        image_slot = MediaSlot(
            x=0, y=0, width=SLIDE_W, height=SLIDE_H,
            z_index=0, slot_type="background", opacity=0.1
        )

    return LayoutDecision(
        image_slot=image_slot,
        chart_slot=chart_slot,
        content_width_pct=1.0
    )


def _layout_two_column(has_image, has_chart, image_position, chart_layout):
    """two_column 页：图表替换右栏"""
    image_slot = None
    chart_slot = None

    if has_chart:
        chart_slot = MediaSlot(
            x=660, y=120, width=540, height=500,
            z_index=1, slot_type="inline-right"
        )

    if has_image:
        image_slot = MediaSlot(
            x=0, y=0, width=SLIDE_W, height=SLIDE_H,
            z_index=0, slot_type="background", opacity=0.1
        )

    return LayoutDecision(
        image_slot=image_slot,
        chart_slot=chart_slot,
        content_width_pct=1.0
    )


def _layout_closing(has_image, has_chart, image_position):
    """closing 页：图片做背景"""
    image_slot = None
    if has_image:
        image_slot = MediaSlot(
            x=0, y=0, width=SLIDE_W, height=SLIDE_H,
            z_index=0, slot_type="background", opacity=0.2
        )

    return LayoutDecision(
        image_slot=image_slot,
        chart_slot=None,
        content_width_pct=1.0
    )
