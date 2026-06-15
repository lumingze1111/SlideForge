"""
HTML Generator Agent - 根据配色方案和主题生成多页幻灯片 HTML

直接使用 LLM 生成完整的幻灯片内容和 HTML 结构。
集成研究、事实核查和演讲者备注生成。
"""

import json
from typing import List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field


class SlideContent(BaseModel):
    """单页幻灯片内容"""
    slide_type: str = Field(description="cover/section/content/two_column/data/closing")
    title: str
    subtitle: str = ""
    bullets: List[str] = Field(default_factory=list)
    key_stat: str = ""
    key_stat_label: str = ""
    notes: str = ""


class PresentationOutline(BaseModel):
    """完整演示文稿大纲"""
    slides: List[SlideContent]
    total_pages: int


OUTLINE_PROMPT = """你是一位专业演讲稿撰写人。根据主题生成演示文稿大纲。

主题：{topic}
受众：{audience}
页数：{pages} 页

输出 JSON，结构如下：
{{
  "total_pages": {pages},
  "slides": [
    {{
      "slide_type": "cover",
      "title": "主标题",
      "subtitle": "副标题或摘要"
    }},
    {{
      "slide_type": "content",
      "title": "章节标题",
      "bullets": ["要点一", "要点二", "要点三"],
      "notes": "补充说明"
    }},
    {{
      "slide_type": "data",
      "title": "数据洞察",
      "key_stat": "87%",
      "key_stat_label": "企业正在使用 AI 工具",
      "bullets": ["背景数据一", "背景数据二"]
    }},
    {{
      "slide_type": "closing",
      "title": "结论",
      "subtitle": "行动号召"
    }}
  ]
}}

slide_type 说明：
- cover: 封面，只有 title + subtitle
- section: 章节过渡页，title + subtitle
- content: 正文页，title + bullets（3-5条）
- two_column: 左右对比，title + bullets（偶数条，左右各半）
- data: 数据页，title + key_stat + key_stat_label + bullets
- closing: 结尾页，title + subtitle

只输出 JSON，不加代码块标记。"""


def generate_outline(
    llm: BaseChatModel,
    topic: str,
    audience: str,
    pages: int = 8,
    key_messages: Optional[List[str]] = None,
    research_facts: Optional[List[str]] = None
) -> PresentationOutline:
    """生成演示文稿大纲（集成研究和事实核查）"""
    from slideforge.agents.research_agent import search_topic_content
    from slideforge.agents.fact_checker import check_facts
    from slideforge.agents.speaker_notes import generate_speaker_notes

    # 1. 研究阶段
    if key_messages and not research_facts:
        print("  🔍 正在搜索主题相关内容...")
        research = search_topic_content(topic, key_messages)
        research_facts = research.facts
        print(f"  ✓ 找到 {len(research.facts)} 条核心事实")

    # 2. 生成大纲
    prompt = OUTLINE_PROMPT.format(topic=topic, audience=audience or "通用受众", pages=pages)
    response = llm.invoke([
        SystemMessage(content="You are a presentation writer. Output valid JSON only."),
        HumanMessage(content=prompt),
    ])
    content = response.content
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    try:
        data = json.loads(content.strip())
    except json.JSONDecodeError:
        # 尝试从 content 中提取 JSON 对象
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(content[start:end])
        else:
            raise
    outline = PresentationOutline(**data)

    # 3. 事实核查
    if research_facts:
        print("  ✅ 正在核查内容真实性...")
        all_content = " ".join([s.title + " " + " ".join(s.bullets) for s in outline.slides])
        fact_check = check_facts(llm, topic, all_content, research_facts)
        print(f"  ✓ 可信度评分: {fact_check.confidence_score:.2f}")
        if fact_check.issues:
            print(f"  ⚠️  发现 {len(fact_check.issues)} 个潜在问题")

    # 4. 生成演讲者备注（所有类型）
    print("  📝 正在生成演讲者备注...")
    for slide in outline.slides:
        content = slide.title
        if slide.subtitle:
            content += " " + slide.subtitle
        if slide.bullets:
            content += " " + " ".join(slide.bullets)
        if slide.key_stat:
            content += f" 关键数据: {slide.key_stat}"

        slide.notes = generate_speaker_notes(
            llm,
            slide.title,
            content,
            research_facts[:3] if research_facts else []
        )
    print("  ✓ 演讲者备注已生成")

    return outline


def render_slide_html(slide: SlideContent, colors: dict, index: int, total: int) -> str:
    """将单页幻灯片内容渲染为 HTML"""
    bg = colors.get("gradient_bg", colors.get("background", "#1a1a2e"))
    primary = colors.get("primary", "#7c3aed")
    accent = colors.get("accent", "#f59e0b")
    text_primary = colors.get("text_primary", "#ffffff")
    text_secondary = colors.get("text_secondary", "#94a3b8")
    surface = colors.get("surface", colors.get("card_bg", "#1e293b"))
    border = colors.get("border", "#475569")

    is_gradient_bg = "gradient" in bg
    bg_css = f"background: {bg};" if is_gradient_bg else f"background-color: {bg};"

    is_gradient_primary = "gradient" in primary
    if is_gradient_primary:
        title_color_css = (
            f"background: {primary}; "
            "-webkit-background-clip: text; "
            "-webkit-text-fill-color: transparent; "
            "background-clip: text;"
        )
        heading_color = text_primary
    else:
        title_color_css = f"color: {primary};"
        heading_color = primary

    page_num = f'<div style="position:absolute;bottom:24px;right:40px;font-size:13px;color:{text_secondary};opacity:0.6;">{index}/{total}</div>'

    if slide.slide_type == "cover":
        return f"""<div class="slide" style="{bg_css} color:{text_primary}; position:relative;">
  <div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;text-align:center;padding:60px 120px;">
    <div style="width:80px;height:5px;background:{accent};margin-bottom:48px;border-radius:3px;"></div>
    <h1 style="font-size:56px;font-weight:800;line-height:1.2;margin-bottom:28px;{title_color_css}">{slide.title}</h1>
    <p style="font-size:22px;color:{text_secondary};max-width:700px;line-height:1.6;">{slide.subtitle}</p>
    <div style="width:80px;height:5px;background:{accent};margin-top:48px;border-radius:3px;"></div>
  </div>
  {page_num}
</div>"""

    if slide.slide_type == "section":
        return f"""<div class="slide" style="{bg_css} color:{text_primary}; position:relative;">
  <div style="display:flex;flex-direction:column;justify-content:center;height:100%;padding:60px 100px;">
    <div style="width:60px;height:4px;background:{accent};margin-bottom:32px;border-radius:2px;"></div>
    <h2 style="font-size:48px;font-weight:700;margin-bottom:20px;{title_color_css}">{slide.title}</h2>
    <p style="font-size:20px;color:{text_secondary};">{slide.subtitle}</p>
  </div>
  {page_num}
</div>"""

    if slide.slide_type == "data":
        bullets_html = "".join(
            f'<li style="margin-bottom:12px;padding-left:20px;position:relative;font-size:16px;color:{text_secondary};">'
            f'<span style="position:absolute;left:0;color:{accent};">▸</span>{b}</li>'
            for b in slide.bullets
        )
        return f"""<div class="slide" style="{bg_css} color:{text_primary}; position:relative;">
  <div style="padding:50px 80px 0 80px;">
    <h2 style="font-size:36px;font-weight:700;margin-bottom:8px;{title_color_css}">{slide.title}</h2>
    <div style="width:80px;height:3px;background:{accent};margin-bottom:32px;"></div>
  </div>
  <div style="padding:0 80px;display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:start;">
    <div style="background:{surface};border-radius:16px;padding:40px;border:2px solid {border};text-align:center;">
      <div style="font-size:72px;font-weight:800;color:{accent};line-height:1;">{slide.key_stat}</div>
      <div style="font-size:16px;color:{text_secondary};margin-top:12px;">{slide.key_stat_label}</div>
    </div>
    <div>
      <ul style="list-style:none;padding:0;margin-top:8px;">{bullets_html}</ul>
    </div>
  </div>
  {page_num}
</div>"""

    if slide.slide_type == "two_column":
        mid = len(slide.bullets) // 2
        left_bullets = slide.bullets[:mid] if slide.bullets else []
        right_bullets = slide.bullets[mid:] if slide.bullets else []
        left_html = "".join(
            f'<li style="margin-bottom:14px;padding-left:20px;position:relative;font-size:17px;color:{text_secondary};">'
            f'<span style="position:absolute;left:0;color:{accent};">▸</span>{b}</li>'
            for b in left_bullets
        )
        right_html = "".join(
            f'<li style="margin-bottom:14px;padding-left:20px;position:relative;font-size:17px;color:{text_secondary};">'
            f'<span style="position:absolute;left:0;color:{accent};">▸</span>{b}</li>'
            for b in right_bullets
        )
        return f"""<div class="slide" style="{bg_css} color:{text_primary}; position:relative;">
  <div style="padding:50px 80px 0 80px;">
    <h2 style="font-size:36px;font-weight:700;margin-bottom:8px;{title_color_css}">{slide.title}</h2>
    <div style="width:80px;height:3px;background:{accent};margin-bottom:32px;"></div>
  </div>
  <div style="padding:0 80px;display:grid;grid-template-columns:1fr 1fr;gap:40px;">
    <div style="background:{surface};border-radius:12px;padding:28px;border:1px solid {border};">
      <ul style="list-style:none;padding:0;">{left_html}</ul>
    </div>
    <div style="background:{surface};border-radius:12px;padding:28px;border:1px solid {border};">
      <ul style="list-style:none;padding:0;">{right_html}</ul>
    </div>
  </div>
  {page_num}
</div>"""

    if slide.slide_type == "closing":
        return f"""<div class="slide" style="{bg_css} color:{text_primary}; position:relative;">
  <div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100%;text-align:center;padding:60px 120px;">
    <div style="font-size:18px;color:{accent};letter-spacing:4px;margin-bottom:24px;font-weight:600;">CONCLUSION</div>
    <h2 style="font-size:48px;font-weight:700;margin-bottom:24px;{title_color_css}">{slide.title}</h2>
    <p style="font-size:20px;color:{text_secondary};max-width:600px;line-height:1.7;">{slide.subtitle}</p>
    <div style="width:60px;height:4px;background:{accent};margin-top:40px;border-radius:2px;"></div>
  </div>
  {page_num}
</div>"""

    # default: content page
    bullets_html = "".join(
        f'<li style="margin-bottom:18px;padding-left:24px;position:relative;font-size:18px;color:{text_secondary};line-height:1.5;">'
        f'<span style="position:absolute;left:0;color:{accent};font-weight:700;">▸</span>{b}</li>'
        for b in slide.bullets
    )
    return f"""<div class="slide" style="{bg_css} color:{text_primary}; position:relative;">
  <div style="padding:50px 80px 0 80px;">
    <h2 style="font-size:38px;font-weight:700;margin-bottom:10px;{title_color_css}">{slide.title}</h2>
    <div style="width:80px;height:3px;background:{accent};margin-bottom:36px;"></div>
  </div>
  <div style="padding:0 80px;">
    <ul style="list-style:none;padding:0;">{bullets_html}</ul>
  </div>
  {page_num}
</div>"""


def generate_slides_html(
    outline: PresentationOutline,
    colors: dict,
    output_path: str = "slides.html",
) -> str:
    """将幻灯片大纲渲染为完整 HTML 文件（每页 1280×720）"""
    total = len(outline.slides)

    # 渲染幻灯片（添加 data-pptx-slide 和 data-notes 供 PPTX 转换引擎使用）
    slides_parts = []
    for i, s in enumerate(outline.slides):
        slide_html = render_slide_html(s, colors, i + 1, total)
        # 在 class="slide" 后添加 data-pptx-slide
        slide_html = slide_html.replace('<div class="slide"', '<div class="slide" data-pptx-slide', 1)
        # 添加演讲者备注
        if s.notes:
            notes_escaped = s.notes.replace('"', '&quot;').replace('\n', '\\n')
            slide_html = slide_html.replace(
                '<div class="slide" data-pptx-slide',
                f'<div class="slide" data-pptx-slide data-notes="{notes_escaped}"',
                1,
            )
        slides_parts.append(slide_html)
    slides_html = "\n".join(slides_parts)

    # 渲染演讲者备注面板
    notes_sections = ""
    for i, s in enumerate(outline.slides):
        if s.notes:
            notes_sections += f"""<div class="notes-panel" id="notes-{i+1}">
  <div class="notes-header">🎤 第 {i+1} 页演讲者备注 — {s.title}</div>
  <div class="notes-body">{s.notes}</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Presentation</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #111; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }}
.slide-container {{ display: flex; flex-direction: column; gap: 20px; padding: 20px; max-width: 1280px; margin: 0 auto; }}
.slide {{ width: 1280px; height: 720px; overflow: hidden; border-radius: 8px; box-shadow: 0 8px 30px rgba(0,0,0,0.6); flex-shrink: 0; }}
.notes-panel {{
  width: 1280px; margin: 0 auto 16px; padding: 20px 24px;
  background: #1e293b; border-radius: 8px; border-left: 4px solid #4ade80;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}}
.notes-header {{ font-size: 15px; font-weight: 600; color: #4ade80; margin-bottom: 10px; }}
.notes-body {{ font-size: 14px; color: #94a3b8; line-height: 1.7; white-space: pre-wrap; }}
</style>
</head>
<body>
<div class="slide-container">
{slides_html}
{notes_sections}
</div>
</body>
</html>"""

    from pathlib import Path
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out.absolute())


def generate_slides_html_with_images(
    outline: PresentationOutline,
    colors: dict,
    image_suggestions: list,
    chart_suggestions: list = None,
    output_path: str = "slides.html",
) -> str:
    """
    将幻灯片大纲渲染为完整 HTML 文件（智能排版，支持图片和图表）
    """
    from pathlib import Path
    import base64
    from slideforge.layout_strategy import compute_layout

    total = len(outline.slides)

    # 按 slide_index 分组
    images_by_slide = {}
    for img in image_suggestions:
        images_by_slide.setdefault(img.slide_index, []).append(img)

    charts_by_slide = {}
    for chart in (chart_suggestions or []):
        charts_by_slide.setdefault(chart.slide_index, []).append(chart)

    slides_parts = []
    for i, s in enumerate(outline.slides):
        has_image = i in images_by_slide
        has_chart = i in charts_by_slide

        img_position = images_by_slide[i][0].position if has_image else "auto"
        chart_layout_hint = charts_by_slide[i][0].layout if has_chart else "auto"

        # 计算排版策略
        layout = compute_layout(
            slide_type=s.slide_type,
            has_image=has_image,
            has_chart=has_chart,
            image_position=img_position,
            chart_layout=chart_layout_hint,
        )

        # 渲染幻灯片内容（可能压缩宽度）
        slide_html = render_slide_html(s, colors, i + 1, total)
        if layout.content_width_pct < 0.95:
            slide_html = _adjust_content_width(slide_html, layout.content_width_pct)

        # 插入图片
        if layout.image_slot and has_image:
            img = images_by_slide[i][0]
            slide_html = _insert_image_at_slot(slide_html, img, layout.image_slot)

        # 插入图表
        if layout.chart_slot and has_chart:
            chart = charts_by_slide[i][0]
            slide_html = _insert_chart_at_slot(slide_html, chart, layout.chart_slot, colors)

        # data-pptx-slide 标记
        slide_html = slide_html.replace('<div class="slide"', '<div class="slide" data-pptx-slide', 1)

        # 演讲者备注
        if s.notes:
            notes_escaped = s.notes.replace('"', '&quot;').replace('\n', '\\n')
            slide_html = slide_html.replace(
                '<div class="slide" data-pptx-slide',
                f'<div class="slide" data-pptx-slide data-notes="{notes_escaped}"',
                1,
            )

        slides_parts.append(slide_html)

    slides_html = "\n".join(slides_parts)

    notes_sections = ""
    for i, s in enumerate(outline.slides):
        if s.notes:
            notes_sections += f"""<div class="notes-panel" id="notes-{i+1}">
  <div class="notes-header">🎤 第 {i+1} 页演讲者备注 — {s.title}</div>
  <div class="notes-body">{s.notes}</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Presentation</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #111; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }}
.slide-container {{ display: flex; flex-direction: column; gap: 20px; padding: 20px; max-width: 1280px; margin: 0 auto; }}
.slide {{ width: 1280px; height: 720px; overflow: hidden; border-radius: 8px; box-shadow: 0 8px 30px rgba(0,0,0,0.6); flex-shrink: 0; position: relative; }}
.notes-panel {{
  width: 1280px; margin: 0 auto 16px; padding: 20px 24px;
  background: #1e293b; border-radius: 8px; border-left: 4px solid #4ade80;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}}
.notes-header {{ font-size: 15px; font-weight: 600; color: #4ade80; margin-bottom: 10px; }}
.notes-body {{ font-size: 14px; color: #94a3b8; line-height: 1.7; white-space: pre-wrap; }}
</style>
</head>
<body>
<div class="slide-container">
{slides_html}
{notes_sections}
</div>
</body>
</html>"""

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out.absolute())


# ──────────────────────────────────────────────────────────────────────
# 排版辅助函数
# ──────────────────────────────────────────────────────────────────────

def _adjust_content_width(slide_html: str, content_width_pct: float) -> str:
    """压缩内容区域宽度，为右侧媒体腾出空间"""
    # 原有 padding 是 0 80px，可用宽度 1120px
    # 通过增大 padding-right 来压缩内容
    content_max_width = int(1120 * content_width_pct)
    right_padding = 1280 - 80 - content_max_width

    # 替换各种 padding 模式
    replacements = [
        ('padding:50px 80px 0 80px;', f'padding:50px {right_padding}px 0 80px;'),
        ('padding:0 80px;', f'padding:0 {right_padding}px 0 80px;'),
        ('padding:60px 100px;', f'padding:60px {right_padding}px 60px 100px;'),
        ('padding:60px 120px;', f'padding:60px {right_padding}px 60px 120px;'),
    ]
    for old, new in replacements:
        if old in slide_html:
            slide_html = slide_html.replace(old, new, 1)
            break

    return slide_html


def _insert_image_at_slot(slide_html: str, img, slot) -> str:
    """在指定插槽位置插入图片"""
    import base64
    from pathlib import Path

    try:
        img_path = Path(img.image_url)
        if not img_path.exists():
            return slide_html

        with open(img_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()
        img_src = f"data:image/jpeg;base64,{img_data}"
    except Exception:
        return slide_html

    if slot.slot_type == "background":
        bg_html = (
            f'<div style="position:absolute;top:0;left:0;width:100%;height:100%;z-index:{slot.z_index};">'
            f'<img src="{img_src}" style="width:100%;height:100%;object-fit:cover;opacity:{slot.opacity};" alt="{img.description}">'
            f'</div>'
        )
        # 在 slide div 之后、第一个子元素之前插入
        slide_html = slide_html.replace(
            '<div class="slide"',
            f'<div class="slide"',
            1
        )
        # 找到第一个 > 后插入背景
        idx = slide_html.find('>', slide_html.find('<div class="slide"'))
        if idx != -1:
            slide_html = slide_html[:idx+1] + bg_html + slide_html[idx+1:]

        # 确保内容层级在图片之上
        slide_html = slide_html.replace(
            '<div style="display:flex',
            '<div style="position:relative;z-index:1;display:flex',
            1
        )
        slide_html = slide_html.replace(
            '<div style="padding:',
            '<div style="position:relative;z-index:1;padding:',
            1
        )

    elif slot.slot_type in ("inline-right", "inline-left"):
        img_html = (
            f'<div style="position:absolute;top:{slot.y}px;left:{slot.x}px;'
            f'width:{slot.width}px;height:{slot.height}px;z-index:{slot.z_index};'
            f'display:flex;align-items:center;justify-content:center;">'
            f'<img src="{img_src}" style="max-width:100%;max-height:100%;'
            f'object-fit:cover;border-radius:12px;'
            f'box-shadow:0 8px 24px rgba(0,0,0,0.4);opacity:{slot.opacity};" alt="{img.description}">'
            f'</div>'
        )
        # 在 slide 闭合标签前插入
        last_close = slide_html.rfind('</div>')
        slide_html = slide_html[:last_close] + img_html + slide_html[last_close:]

    return slide_html


def _insert_chart_at_slot(slide_html: str, chart, slot, colors: dict) -> str:
    """在指定插槽位置插入图表"""
    import base64
    from pathlib import Path

    chart_html = ""

    # 优先使用 matplotlib 图片
    if hasattr(chart, 'chart_path') and chart.chart_path:
        try:
            img_path = Path(chart.chart_path)
            if img_path.exists():
                with open(img_path, 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode()
                chart_html = (
                    f'<div style="position:absolute;top:{slot.y}px;left:{slot.x}px;'
                    f'width:{slot.width}px;height:{slot.height}px;z-index:{slot.z_index};'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'background:{colors.get("surface", "#1e293b")};border-radius:12px;'
                    f'box-shadow:0 4px 16px rgba(0,0,0,0.3);">'
                    f'<img src="data:image/png;base64,{img_data}" '
                    f'style="max-width:95%;max-height:95%;object-fit:contain;">'
                    f'</div>'
                )
        except Exception:
            pass

    # 用 native_config 渲染 CSS 图表
    if not chart_html and hasattr(chart, 'native_config') and chart.native_config:
        config = chart.native_config
        chart_type = config.get("type", "bar")

        if chart_type == "bar":
            chart_html = _render_bar_chart_html(config, slot, colors)
        elif chart_type == "pie":
            chart_html = _render_pie_chart_html(config, slot, colors)
        elif chart_type == "line":
            chart_html = _render_line_chart_html(config, slot, colors)
        elif chart_type == "table":
            chart_html = _render_table_chart_html(config, slot, colors)

    if chart_html:
        last_close = slide_html.rfind('</div>')
        slide_html = slide_html[:last_close] + chart_html + slide_html[last_close:]

    return slide_html


# ──────────────────────────────────────────────────────────────────────
# CSS 原生图表渲染
# ──────────────────────────────────────────────────────────────────────

def _render_bar_chart_html(config: dict, slot, colors: dict) -> str:
    """CSS flexbox 柱状图"""
    categories = config.get("categories", [])
    series = config.get("series", [{}])
    values = series[0].get("values", []) if series else []
    if not values:
        return ""

    max_val = max(values) if values else 1
    accent = colors.get("accent", "#f59e0b")
    surface = colors.get("surface", "#1e293b")
    text_primary = colors.get("text_primary", "#ffffff")
    text_secondary = colors.get("text_secondary", "#94a3b8")

    bars_html = ""
    for cat, val in zip(categories, values):
        bar_h = int((val / max_val) * 70)
        bars_html += (
            f'<div style="display:flex;flex-direction:column;align-items:center;flex:1;gap:4px;">'
            f'<div style="font-size:11px;color:{text_secondary};">{val}</div>'
            f'<div style="width:70%;height:{bar_h}%;background:{accent};border-radius:4px 4px 0 0;min-height:8px;"></div>'
            f'<div style="font-size:10px;color:{text_secondary};text-align:center;max-width:100%;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;">{cat}</div>'
            f'</div>'
        )

    title = config.get("title", "")
    return (
        f'<div style="position:absolute;top:{slot.y}px;left:{slot.x}px;'
        f'width:{slot.width}px;height:{slot.height}px;z-index:{slot.z_index};'
        f'background:{surface};border-radius:12px;padding:20px;'
        f'display:flex;flex-direction:column;box-shadow:0 4px 16px rgba(0,0,0,0.3);">'
        f'<div style="font-size:14px;font-weight:600;color:{text_primary};margin-bottom:16px;">{title}</div>'
        f'<div style="flex:1;display:flex;align-items:flex-end;gap:6px;padding-bottom:8px;">'
        f'{bars_html}</div></div>'
    )


def _render_pie_chart_html(config: dict, slot, colors: dict) -> str:
    """CSS conic-gradient 饼图"""
    categories = config.get("categories", [])
    values = config.get("values", [])
    if not values:
        return ""

    total = sum(values)
    if total == 0:
        return ""

    surface = colors.get("surface", "#1e293b")
    text_primary = colors.get("text_primary", "#ffffff")
    text_secondary = colors.get("text_secondary", "#94a3b8")

    pie_colors = ['#7c3aed', '#f59e0b', '#10b981', '#ef4444', '#3b82f6', '#ec4899', '#14b8a6', '#f97316']

    # 构建 conic-gradient
    segments = []
    cumulative = 0
    for i, val in enumerate(values):
        start_pct = (cumulative / total) * 100
        cumulative += val
        end_pct = (cumulative / total) * 100
        color = pie_colors[i % len(pie_colors)]
        segments.append(f'{color} {start_pct:.1f}% {end_pct:.1f}%')

    gradient = ', '.join(segments)

    # 图例
    legend_html = ""
    for i, (cat, val) in enumerate(zip(categories, values)):
        color = pie_colors[i % len(pie_colors)]
        pct = int((val / total) * 100)
        legend_html += (
            f'<div style="display:flex;align-items:center;gap:6px;font-size:11px;color:{text_secondary};">'
            f'<div style="width:10px;height:10px;border-radius:2px;background:{color};flex-shrink:0;"></div>'
            f'{cat} ({pct}%)</div>'
        )

    title = config.get("title", "")
    pie_size = min(slot.width, slot.height) - 120
    return (
        f'<div style="position:absolute;top:{slot.y}px;left:{slot.x}px;'
        f'width:{slot.width}px;height:{slot.height}px;z-index:{slot.z_index};'
        f'background:{surface};border-radius:12px;padding:20px;'
        f'display:flex;flex-direction:column;align-items:center;box-shadow:0 4px 16px rgba(0,0,0,0.3);">'
        f'<div style="font-size:14px;font-weight:600;color:{text_primary};margin-bottom:12px;align-self:flex-start;">{title}</div>'
        f'<div style="width:{pie_size}px;height:{pie_size}px;border-radius:50%;'
        f'background:conic-gradient({gradient});margin:8px 0;"></div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:8px 16px;justify-content:center;">'
        f'{legend_html}</div></div>'
    )


def _render_line_chart_html(config: dict, slot, colors: dict) -> str:
    """SVG 折线图"""
    categories = config.get("categories", [])
    series = config.get("series", [{}])
    values = series[0].get("values", []) if series else []
    if not values:
        return ""

    surface = colors.get("surface", "#1e293b")
    text_primary = colors.get("text_primary", "#ffffff")
    text_secondary = colors.get("text_secondary", "#94a3b8")
    accent = colors.get("accent", "#f59e0b")

    # SVG 坐标
    svg_w = slot.width - 80
    svg_h = slot.height - 120
    max_val = max(values) if values else 1
    min_val = min(values) if values else 0
    val_range = max_val - min_val if max_val != min_val else 1

    points = []
    for j, val in enumerate(values):
        x = int((j / max(len(values) - 1, 1)) * svg_w)
        y = int(svg_h - ((val - min_val) / val_range) * svg_h)
        points.append(f"{x},{y}")

    polyline = ' '.join(points)

    # X 轴标签
    x_labels = ""
    for j, cat in enumerate(categories):
        x = int((j / max(len(categories) - 1, 1)) * svg_w)
        x_labels += f'<text x="{x}" y="{svg_h + 18}" font-size="10" fill="{text_secondary}" text-anchor="middle">{cat}</text>'

    title = config.get("title", "")
    return (
        f'<div style="position:absolute;top:{slot.y}px;left:{slot.x}px;'
        f'width:{slot.width}px;height:{slot.height}px;z-index:{slot.z_index};'
        f'background:{surface};border-radius:12px;padding:20px;'
        f'display:flex;flex-direction:column;box-shadow:0 4px 16px rgba(0,0,0,0.3);">'
        f'<div style="font-size:14px;font-weight:600;color:{text_primary};margin-bottom:12px;">{title}</div>'
        f'<svg width="{svg_w}" height="{svg_h + 30}" style="margin:auto;">'
        f'<polyline points="{polyline}" fill="none" stroke="{accent}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        f'{x_labels}</svg></div>'
    )


def _render_table_chart_html(config: dict, slot, colors: dict) -> str:
    """HTML 表格"""
    headers = config.get("headers", [])
    rows = config.get("rows", [])
    if not headers:
        return ""

    surface = colors.get("surface", "#1e293b")
    text_primary = colors.get("text_primary", "#ffffff")
    text_secondary = colors.get("text_secondary", "#94a3b8")
    border = colors.get("border", "#475569")

    th_html = "".join(f'<th style="padding:8px 12px;text-align:left;border-bottom:2px solid {border};color:{text_primary};font-size:12px;">{h}</th>' for h in headers)
    tr_html = ""
    for row in rows[:8]:  # 最多显示 8 行
        cells = "".join(f'<td style="padding:6px 12px;border-bottom:1px solid {border};color:{text_secondary};font-size:11px;">{c}</td>' for c in row)
        tr_html += f'<tr>{cells}</tr>'

    title = config.get("title", "")
    return (
        f'<div style="position:absolute;top:{slot.y}px;left:{slot.x}px;'
        f'width:{slot.width}px;height:{slot.height}px;z-index:{slot.z_index};'
        f'background:{surface};border-radius:12px;padding:20px;overflow:hidden;'
        f'box-shadow:0 4px 16px rgba(0,0,0,0.3);">'
        f'<div style="font-size:14px;font-weight:600;color:{text_primary};margin-bottom:12px;">{title}</div>'
        f'<table style="width:100%;border-collapse:collapse;"><thead><tr>{th_html}</tr></thead>'
        f'<tbody>{tr_html}</tbody></table></div>'
    )
