"""
Outline Proposal Agent - 生成多个大纲方案供用户选择
"""

import json
from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel


class OutlineProposal(BaseModel):
    """单个大纲提案"""
    name: str = Field(description="方案名称，如'故事叙述型'、'数据驱动型'")
    structure: str = Field(description="结构说明，如'问题-方案-案例-总结'")
    slide_count: int = Field(description="页数")
    slide_types: List[str] = Field(description="每页类型序列，如['cover','content','data',...]")
    titles: List[str] = Field(description="每页标题")
    reasoning: str = Field(description="为什么这个结构适合该主题，50字以内")


class OutlineProposals(BaseModel):
    """多个大纲方案"""
    proposals: List[OutlineProposal] = Field(description="3-4套大纲方案")
    recommended_index: int = Field(description="最推荐方案的索引（0-based）")


OUTLINE_PROPOSAL_PROMPT = """你是演示文稿结构设计专家。根据主题生成 3-4 套不同结构的大纲方案。

主题：{topic}
受众：{audience}
页数：{pages} 页

要求：
1. 每套方案有不同的叙事结构（故事型、数据型、问题解决型、对比型等）
2. 提供每页的类型（cover/section/content/two_column/data/closing）和标题
3. 方案之间差异明显，适应不同演讲风格

输出 JSON：
{{
  "proposals": [
    {{
      "name": "故事叙述型",
      "structure": "引入-冲突-转折-解决-展望",
      "slide_count": {pages},
      "slide_types": ["cover", "content", "data", "content", "content", "data", "two_column", "closing"],
      "titles": ["标题1", "标题2", ...],
      "reasoning": "通过故事线索引导，适合感性受众"
    }},
    ...
  ],
  "recommended_index": 0
}}

只输出 JSON，不加代码块。"""


def generate_outline_proposals(
    llm: BaseChatModel,
    topic: str,
    audience: str,
    pages: int = 8
) -> OutlineProposals:
    """生成多套大纲方案"""
    prompt = OUTLINE_PROPOSAL_PROMPT.format(
        topic=topic,
        audience=audience or "通用受众",
        pages=pages
    )
    
    try:
        structured_llm = llm.with_structured_output(OutlineProposals)
        result = structured_llm.invoke(prompt)
        return result
    except Exception:
        # Fallback to JSON mode
        schema_str = json.dumps(OutlineProposals.model_json_schema(), ensure_ascii=False, indent=2)
        json_prompt = prompt + "\n\n必须严格按照以下 JSON schema 输出：\n" + schema_str
        
        response = llm.invoke([
            SystemMessage(content="You are a presentation structure designer. Output valid JSON only."),
            HumanMessage(content=json_prompt)
        ])
        
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        data = json.loads(content.strip())
        return OutlineProposals(**data)


def render_outline_preview_html(proposals: List[OutlineProposal], topic: str, output_path: str, server_port: int = 7789) -> str:
    """生成大纲方案预览 HTML"""
    from pathlib import Path
    
    cards_html = ""
    for i, prop in enumerate(proposals):
        slide_list = "\n".join(
            f'<div class="slide-item"><span class="slide-type">{stype}</span><span class="slide-title">{title}</span></div>'
            for stype, title in zip(prop.slide_types, prop.titles)
        )
        
        cards_html += f"""
<div class="outline-card" data-index="{i}" onclick="selectOutline(this)">
    <div class="selected-badge">✓ 已选择</div>
    <div class="outline-meta">
        <div class="outline-title">{i + 1}. {prop.name}</div>
        <div class="outline-badge">{prop.slide_count} 页</div>
    </div>
    <div class="outline-structure">
        <strong>结构：</strong>{prop.structure}
    </div>
    <div class="outline-slides">
        {slide_list}
    </div>
    <div class="outline-reasoning">
        <strong>设计理由：</strong>{prop.reasoning}
    </div>
</div>
"""
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>SlideForge 大纲方案选择</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background: #111827;
    color: #e0e0e0;
    padding: 40px 20px 120px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ text-align: center; font-size: 28px; margin-bottom: 8px; color: #fff; }}
.subtitle {{ text-align: center; font-size: 14px; color: #6b7280; margin-bottom: 40px; }}

.outline-card {{
    background: #1f2937;
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 32px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    border: 3px solid transparent;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
}}
.outline-card:hover {{
    border-color: #4b83ff;
    transform: translateY(-2px);
}}
.outline-card.selected {{
    border-color: #4ade80;
    box-shadow: 0 0 0 4px rgba(74,222,128,0.2);
}}
.selected-badge {{
    display: none;
    position: absolute;
    top: 16px;
    right: 16px;
    background: #4ade80;
    color: #111827;
    font-weight: 700;
    font-size: 13px;
    padding: 4px 14px;
    border-radius: 20px;
}}
.outline-card.selected .selected-badge {{ display: inline-block; }}

.outline-meta {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}}
.outline-title {{ font-size: 20px; font-weight: 600; color: #fff; }}
.outline-badge {{
    padding: 4px 14px;
    background: #374151;
    color: #9ca3af;
    border-radius: 20px;
    font-size: 13px;
}}
.outline-structure {{
    margin-bottom: 16px;
    color: #9ca3af;
    font-size: 14px;
}}
.outline-slides {{
    background: #0f172a;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
    max-height: 300px;
    overflow-y: auto;
}}
.slide-item {{
    display: flex;
    gap: 12px;
    padding: 8px 0;
    border-bottom: 1px solid #1e293b;
}}
.slide-item:last-child {{ border-bottom: none; }}
.slide-type {{
    background: #374151;
    color: #9ca3af;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-family: monospace;
    min-width: 80px;
    text-align: center;
}}
.slide-title {{ color: #e0e0e0; font-size: 14px; }}
.outline-reasoning {{
    color: #9ca3af;
    font-size: 13px;
    line-height: 1.6;
}}

.confirm-bar {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #1f2937;
    border-top: 1px solid #374151;
    padding: 16px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    z-index: 100;
}}
.confirm-hint {{ font-size: 14px; color: #9ca3af; }}
.confirm-hint span {{ color: #4ade80; font-weight: 600; }}
.confirm-btn {{
    background: #4ade80;
    color: #111827;
    border: none;
    padding: 12px 40px;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
}}
.confirm-btn:hover {{ background: #22c55e; transform: scale(1.03); }}
.confirm-btn:disabled {{
    background: #374151;
    color: #6b7280;
    cursor: not-allowed;
    transform: none;
}}
</style>
</head>
<body>
<div class="container">
<h1>📋 SlideForge 大纲结构选择</h1>
<p class="subtitle">点击方案卡片选择演示结构，然后点击底部「确认大纲」按钮</p>
{cards_html}
</div>

<div class="confirm-bar">
    <div class="confirm-hint" id="hint">请先点击上方任意大纲方案</div>
    <button class="confirm-btn" id="confirmBtn" disabled onclick="confirmOutline()">确认大纲</button>
</div>

<script>
const PORT = {server_port};
let selectedIndex = null;

function selectOutline(el) {{
    document.querySelectorAll('.outline-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    selectedIndex = parseInt(el.dataset.index);
    const title = el.querySelector('.outline-title').textContent.trim();
    document.getElementById('hint').innerHTML = '已选择：<span>' + title + '</span>';
    document.getElementById('confirmBtn').disabled = false;
}}

function confirmOutline() {{
    if (selectedIndex === null) return;
    const btn = document.getElementById('confirmBtn');
    btn.disabled = true;
    btn.textContent = '提交中…';
    fetch('http://localhost:' + PORT + '/select', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{index: selectedIndex}})
    }})
    .then(r => r.json())
    .then(() => {{
        btn.textContent = '✓ 已确认';
        btn.style.background = '#22c55e';
        document.getElementById('hint').innerHTML = '<span>大纲已提交！窗口即将关闭…</span>';
        setTimeout(() => window.close(), 800);
    }})
    .catch(err => {{
        btn.disabled = false;
        btn.textContent = '确认大纲';
        alert('提交失败：' + err.message);
    }});
}}
</script>
</body>
</html>"""
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path.absolute())


def pick_outline_proposal(proposals: OutlineProposals, topic: str) -> OutlineProposal:
    """让用户在浏览器中选择大纲方案"""
    from slideforge.preview_generator import wait_for_selection
    import subprocess
    
    preview_path = render_outline_preview_html(
        proposals.proposals,
        topic,
        output_path="output/slideforge_outline_preview.html",
        server_port=7789
    )
    print(f"\n  💡 大纲预览页面已生成：{preview_path}")
    
    try:
        subprocess.run(["open", preview_path], check=False)
        print(f"  ✓ 已在浏览器中打开大纲预览")
    except Exception:
        pass
    
    idx = wait_for_selection(len(proposals.proposals), port=7789)
    chosen = proposals.proposals[idx]
    print(f"\n  ✓ 已选择大纲 [{idx + 1}]：{chosen.name}")
    return chosen
