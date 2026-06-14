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
    output_path: str = "slides.html",
) -> str:
    """
    将幻灯片大纲渲染为完整 HTML 文件（支持图片）

    Args:
        outline: 幻灯片大纲
        colors: 配色方案
        image_suggestions: 图片建议列表（ImageSuggestion 对象）
        output_path: 输出路径

    Returns:
        输出文件的绝对路径
    """
    from pathlib import Path
    import base64

    total = len(outline.slides)

    # 构建图片索引（按 slide_index 分组）
    images_by_slide = {}
    for img in image_suggestions:
        slide_idx = img.slide_index
        if slide_idx not in images_by_slide:
            images_by_slide[slide_idx] = []
        images_by_slide[slide_idx].append(img)

    # 渲染幻灯片
    slides_parts = []
    for i, s in enumerate(outline.slides):
        slide_html = render_slide_html(s, colors, i + 1, total)

        # 如果有图片建议，插入图片
        if i in images_by_slide:
            for img in images_by_slide[i]:
                # 读取图片并转换为 base64（用于嵌入 HTML）
                try:
                    img_path = Path(img.image_url)
                    if img_path.exists():
                        with open(img_path, 'rb') as f:
                            img_data = base64.b64encode(f.read()).decode()
                            img_src = f"data:image/jpeg;base64,{img_data}"

                        # 根据位置插入图片
                        if img.position == "background":
                            # 背景图片
                            opacity = getattr(img, 'opacity', 0.3)
                            bg_img_html = f"""
<div style="position:absolute;top:0;left:0;width:100%;height:100%;z-index:0;">
  <img src="{img_src}" style="width:100%;height:100%;object-fit:cover;opacity:{opacity};" alt="{img.description}">
</div>"""
                            # 在 slide div 开始后立即插入
                            slide_html = slide_html.replace(
                                '<div class="slide"',
                                f'<div class="slide" style="position:relative;"{bg_img_html}',
                                1
                            )
                            # 确保内容在图片之上
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

                        elif img.position == "center":
                            # 居中图片
                            width_pct = img.size[0] * 100
                            height_pct = img.size[1] * 100
                            img_html = f"""
<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:2;">
  <img src="{img_src}" style="max-width:{width_pct}%;max-height:{height_pct}%;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.3);" alt="{img.description}">
</div>"""
                            slide_html = slide_html.replace('</div>', f'{img_html}</div>', 1)

                except Exception as e:
                    # 图片读取失败，跳过
                    print(f"  ⚠ Warning: Failed to load image for slide {i+1}: {e}")
                    continue

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

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out.absolute())
