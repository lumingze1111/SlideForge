"""
PPTX Exporter - Convert slide outline + color scheme to .pptx using python-pptx.

Handles gradient backgrounds by approximating them with solid colors,
since python-pptx doesn't natively support CSS gradients.
"""

import re
from pathlib import Path
from typing import Optional

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from slideforge.agents.html_generator import PresentationOutline, SlideContent


# Slide dimensions: 16:9 widescreen (13.33 x 7.5 inches)
SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)

MARGIN_H = Inches(0.8)   # horizontal margin
MARGIN_V = Inches(0.6)   # vertical margin
CONTENT_W = SLIDE_W - MARGIN_H * 2
CONTENT_H = SLIDE_H - MARGIN_V * 2


def _parse_hex(color: str) -> Optional[RGBColor]:
    """Parse #RRGGBB or extract first hex from a gradient string."""
    # Extract first #RRGGBB from string
    m = re.search(r'#([0-9a-fA-F]{6})', color)
    if m:
        h = m.group(1)
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return None


def _solid_bg(slide, color_str: str) -> None:
    """Fill slide background with a solid color (extracted from gradient if needed)."""
    rgb = _parse_hex(color_str)
    if not rgb:
        return
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb


def _add_text_box(
    slide,
    text: str,
    left: Emu,
    top: Emu,
    width: Emu,
    height: Emu,
    font_size: int,
    bold: bool = False,
    color: str = "#ffffff",
    align: PP_ALIGN = PP_ALIGN.LEFT,
    wrap: bool = True,
) -> None:
    """Add a text box to the slide."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    rgb = _parse_hex(color)
    if rgb:
        run.font.color.rgb = rgb


def _add_rect(
    slide,
    left: Emu,
    top: Emu,
    width: Emu,
    height: Emu,
    fill_color: str,
    line_color: Optional[str] = None,
) -> None:
    """Add a filled rectangle shape."""
    shape = slide.shapes.add_shape(1, left, top, width, height)  # MSO_SHAPE_TYPE.RECTANGLE
    fill = shape.fill
    rgb = _parse_hex(fill_color)
    if rgb:
        fill.solid()
        fill.fore_color.rgb = rgb
    else:
        fill.background()

    if line_color:
        line_rgb = _parse_hex(line_color)
        if line_rgb:
            shape.line.color.rgb = line_rgb
            shape.line.width = Pt(1)
    else:
        shape.line.fill.background()


def _render_cover(slide, s: SlideContent, colors: dict) -> None:
    bg = colors.get("background", colors.get("gradient_bg", "#1a1a2e"))
    primary = colors.get("primary", "#7c3aed")
    accent = colors.get("accent", "#f59e0b")
    text_sec = colors.get("text_secondary", "#94a3b8")

    _solid_bg(slide, bg)

    # Accent bar top
    _add_rect(slide, SLIDE_W / 2 - Inches(0.5), Inches(1.5), Inches(1), Inches(0.07), accent)

    # Title
    _add_text_box(
        slide, s.title,
        MARGIN_H, Inches(2.0), CONTENT_W, Inches(2.0),
        font_size=44, bold=True, color=primary, align=PP_ALIGN.CENTER,
    )

    # Subtitle
    if s.subtitle:
        _add_text_box(
            slide, s.subtitle,
            MARGIN_H, Inches(4.2), CONTENT_W, Inches(1.2),
            font_size=20, bold=False, color=text_sec, align=PP_ALIGN.CENTER,
        )

    # Accent bar bottom
    _add_rect(slide, SLIDE_W / 2 - Inches(0.5), Inches(5.8), Inches(1), Inches(0.07), accent)


def _render_section(slide, s: SlideContent, colors: dict) -> None:
    bg = colors.get("background", colors.get("gradient_bg", "#1a1a2e"))
    primary = colors.get("primary", "#7c3aed")
    accent = colors.get("accent", "#f59e0b")
    text_sec = colors.get("text_secondary", "#94a3b8")

    _solid_bg(slide, bg)
    _add_rect(slide, MARGIN_H, Inches(2.8), Inches(0.7), Inches(0.05), accent)

    _add_text_box(
        slide, s.title,
        MARGIN_H, Inches(2.0), CONTENT_W, Inches(1.6),
        font_size=40, bold=True, color=primary,
    )
    if s.subtitle:
        _add_text_box(
            slide, s.subtitle,
            MARGIN_H, Inches(3.2), CONTENT_W, Inches(1.0),
            font_size=20, bold=False, color=text_sec,
        )


def _render_content(slide, s: SlideContent, colors: dict) -> None:
    bg = colors.get("background", colors.get("gradient_bg", "#1a1a2e"))
    primary = colors.get("primary", "#7c3aed")
    accent = colors.get("accent", "#f59e0b")
    text_primary = colors.get("text_primary", "#ffffff")
    text_sec = colors.get("text_secondary", "#94a3b8")

    _solid_bg(slide, bg)

    # Title
    _add_text_box(
        slide, s.title,
        MARGIN_H, MARGIN_V, CONTENT_W, Inches(0.9),
        font_size=32, bold=True, color=primary,
    )
    # Underline bar
    _add_rect(slide, MARGIN_H, Inches(1.6), Inches(0.8), Inches(0.04), accent)

    # Bullets
    y = Inches(1.9)
    for bullet in s.bullets:
        # Bullet marker
        _add_text_box(slide, "▸", MARGIN_H, y, Inches(0.3), Inches(0.4), 16, color=accent)
        _add_text_box(slide, bullet, MARGIN_H + Inches(0.3), y, CONTENT_W - Inches(0.3), Inches(0.5),
                      font_size=16, color=text_sec)
        y += Inches(0.55)


def _render_two_column(slide, s: SlideContent, colors: dict) -> None:
    bg = colors.get("background", colors.get("gradient_bg", "#1a1a2e"))
    primary = colors.get("primary", "#7c3aed")
    accent = colors.get("accent", "#f59e0b")
    text_sec = colors.get("text_secondary", "#94a3b8")
    surface = colors.get("surface", colors.get("card_bg", "#1e293b"))
    border = colors.get("border", "#475569")

    _solid_bg(slide, bg)
    _add_text_box(slide, s.title, MARGIN_H, MARGIN_V, CONTENT_W, Inches(0.9), 32, True, primary)
    _add_rect(slide, MARGIN_H, Inches(1.6), Inches(0.8), Inches(0.04), accent)

    col_w = (CONTENT_W - Inches(0.3)) / 2
    mid = len(s.bullets) // 2
    left_bullets = s.bullets[:mid]
    right_bullets = s.bullets[mid:]

    # Left card
    _add_rect(slide, MARGIN_H, Inches(1.9), col_w, Inches(5.0), surface, border)
    y = Inches(2.1)
    for b in left_bullets:
        _add_text_box(slide, f"▸ {b}", MARGIN_H + Inches(0.15), y, col_w - Inches(0.3), Inches(0.5),
                      font_size=15, color=text_sec)
        y += Inches(0.5)

    # Right card
    rx = MARGIN_H + col_w + Inches(0.3)
    _add_rect(slide, rx, Inches(1.9), col_w, Inches(5.0), surface, border)
    y = Inches(2.1)
    for b in right_bullets:
        _add_text_box(slide, f"▸ {b}", rx + Inches(0.15), y, col_w - Inches(0.3), Inches(0.5),
                      font_size=15, color=text_sec)
        y += Inches(0.5)


def _render_data(slide, s: SlideContent, colors: dict) -> None:
    bg = colors.get("background", colors.get("gradient_bg", "#1a1a2e"))
    primary = colors.get("primary", "#7c3aed")
    accent = colors.get("accent", "#f59e0b")
    text_sec = colors.get("text_secondary", "#94a3b8")
    surface = colors.get("surface", colors.get("card_bg", "#1e293b"))
    border = colors.get("border", "#475569")

    _solid_bg(slide, bg)
    _add_text_box(slide, s.title, MARGIN_H, MARGIN_V, CONTENT_W, Inches(0.9), 32, True, primary)
    _add_rect(slide, MARGIN_H, Inches(1.6), Inches(0.8), Inches(0.04), accent)

    col_w = (CONTENT_W - Inches(0.3)) / 2

    # Stat card
    _add_rect(slide, MARGIN_H, Inches(1.9), col_w, Inches(4.5), surface, border)
    _add_text_box(slide, s.key_stat, MARGIN_H, Inches(2.5), col_w, Inches(1.5),
                  font_size=56, bold=True, color=accent, align=PP_ALIGN.CENTER)
    _add_text_box(slide, s.key_stat_label, MARGIN_H, Inches(4.1), col_w, Inches(0.6),
                  font_size=14, color=text_sec, align=PP_ALIGN.CENTER)

    # Bullets
    rx = MARGIN_H + col_w + Inches(0.3)
    y = Inches(2.0)
    for b in s.bullets:
        _add_text_box(slide, f"▸ {b}", rx, y, col_w, Inches(0.55), font_size=15, color=text_sec)
        y += Inches(0.55)


def _render_closing(slide, s: SlideContent, colors: dict) -> None:
    bg = colors.get("background", colors.get("gradient_bg", "#1a1a2e"))
    primary = colors.get("primary", "#7c3aed")
    accent = colors.get("accent", "#f59e0b")
    text_sec = colors.get("text_secondary", "#94a3b8")

    _solid_bg(slide, bg)
    _add_rect(slide, SLIDE_W / 2 - Inches(0.4), Inches(1.8), Inches(0.8), Inches(0.05), accent)
    _add_text_box(slide, s.title, MARGIN_H, Inches(2.2), CONTENT_W, Inches(1.6),
                  font_size=40, bold=True, color=primary, align=PP_ALIGN.CENTER)
    if s.subtitle:
        _add_text_box(slide, s.subtitle, MARGIN_H, Inches(4.0), CONTENT_W, Inches(1.2),
                      font_size=20, color=text_sec, align=PP_ALIGN.CENTER)
    _add_rect(slide, SLIDE_W / 2 - Inches(0.3), Inches(5.5), Inches(0.6), Inches(0.05), accent)


_RENDERERS = {
    "cover": _render_cover,
    "section": _render_section,
    "content": _render_content,
    "two_column": _render_two_column,
    "data": _render_data,
    "closing": _render_closing,
}


def export_pptx(outline: PresentationOutline, colors: dict, output_path: str) -> str:
    """
    Export a PresentationOutline to a .pptx file.

    Args:
        outline: Generated slide outline
        colors: ColorProposal.colors dict
        output_path: Destination .pptx path

    Returns:
        Absolute path to the generated file
    """
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    blank_layout = prs.slide_layouts[6]  # completely blank layout

    for slide_content in outline.slides:
        slide = prs.slides.add_slide(blank_layout)
        renderer = _RENDERERS.get(slide_content.slide_type, _render_content)
        renderer(slide, slide_content, colors)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return str(out.absolute())
