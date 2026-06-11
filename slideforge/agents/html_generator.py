"""
HTML Generator Agent - 根据配色方案和主题生成多页幻灯片 HTML

直接使用 LLM 生成完整的幻灯片内容和 HTML 结构。
"""

import json
from typing import List
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


def generate_outline(llm: BaseChatModel, topic: str, audience: str, pages: int = 8) -> PresentationOutline:
    """生成演示文稿大纲"""
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
    data = json.loads(content.strip())
    return PresentationOutline(**data)


def render_slide_html(slide: SlideContent, colors: dict, index: int, total: int) -> str:
    """将单页幻灯片内容渲染为 HTML"""
    bg = colors.get("background", colors.get("gradient_bg", "#1a1a2e"))
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
    notes_html = f'<p style="margin-top:20px;font-size:14px;color:{text_secondary};opacity:0.7;font-style:italic;">{slide.notes}</p>' if slide.notes else ""
    return f"""<div class="slide" style="{bg_css} color:{text_primary}; position:relative;">
  <div style="padding:50px 80px 0 80px;">
    <h2 style="font-size:38px;font-weight:700;margin-bottom:10px;{title_color_css}">{slide.title}</h2>
    <div style="width:80px;height:3px;background:{accent};margin-bottom:36px;"></div>
  </div>
  <div style="padding:0 80px;">
    <ul style="list-style:none;padding:0;">{bullets_html}</ul>
    {notes_html}
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
    slides_html = "\n".join(
        render_slide_html(s, colors, i + 1, total)
        for i, s in enumerate(outline.slides)
    )

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
</style>
</head>
<body>
<div class="slide-container">
{slides_html}
</div>
</body>
</html>"""

    from pathlib import Path
    Path(output_path).write_text(html, encoding="utf-8")
    return str(Path(output_path).absolute())
