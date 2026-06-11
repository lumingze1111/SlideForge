"""
HTML Preview Generator - 生成配色方案的真实 PPT 预览页面
"""

from pathlib import Path
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .agents.propose_agent import ColorProposal


def generate_preview_html(proposals: List["ColorProposal"], topic: str, output_path: str = None) -> str:
    """
    生成配色方案对比预览页面（HTML），每个方案渲染为真实 PPT 样式

    Args:
        proposals: 配色方案列表
        topic: 幻灯片主题（用于内容展示）
        output_path: 输出路径，默认为当前目录下的 preview.html

    Returns:
        HTML 文件路径
    """
    if output_path is None:
        output_path = "slideforge_preview.html"

    html_parts = [_html_header()]

    for i, proposal in enumerate(proposals, 1):
        slide_html = _generate_slide_preview(proposal, topic, i)
        html_parts.append(slide_html)

    html_parts.append(_html_footer())

    html_content = "\n".join(html_parts)

    output_path = Path(output_path)
    output_path.write_text(html_content, encoding="utf-8")

    return str(output_path.absolute())


def _html_header() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SlideForge 配色方案预览</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background: #1a1a1a;
    color: #e0e0e0;
    padding: 40px 20px;
}
.container { max-width: 1400px; margin: 0 auto; }
h1 {
    text-align: center;
    font-size: 32px;
    margin-bottom: 40px;
    color: #fff;
}
.slide-card {
    background: #2a2a2a;
    border-radius: 12px;
    padding: 30px;
    margin-bottom: 40px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}
.slide-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}
.slide-title {
    font-size: 24px;
    font-weight: 600;
    color: #fff;
}
.slide-badge {
    display: inline-block;
    padding: 6px 16px;
    background: #4a9eff;
    color: #fff;
    border-radius: 20px;
    font-size: 14px;
}
.slide-preview {
    width: 1280px;
    height: 720px;
    margin: 20px auto;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 8px 30px rgba(0,0,0,0.7);
    position: relative;
}
.slide-info {
    display: flex;
    gap: 20px;
    margin-top: 20px;
    font-size: 14px;
}
.color-palette {
    display: flex;
    gap: 8px;
}
.color-chip {
    width: 40px;
    height: 40px;
    border-radius: 6px;
    border: 2px solid rgba(255,255,255,0.1);
}
.reasoning {
    flex: 1;
    color: #999;
    line-height: 1.6;
}
</style>
</head>
<body>
<div class="container">
<h1>🎨 SlideForge 配色方案预览</h1>
"""


def _generate_slide_preview(proposal, topic: str, index: int) -> str:
    """生成单个方案的 PPT 预览 HTML"""
    colors = proposal.colors

    # 提取常用颜色（兼容旧格式）
    bg = colors.get('background', colors.get('gradient_bg', '#FFFFFF'))
    primary = colors.get('primary', '#1976D2')
    accent = colors.get('accent', colors.get('accent_1', '#FFC107'))
    text_primary = colors.get('text_primary', '#212121')
    text_secondary = colors.get('text_secondary', '#757575')
    surface = colors.get('surface', colors.get('card_bg', '#F5F5F5'))
    border = colors.get('border', colors.get('divider', '#E0E0E0'))

    # 检测是否为渐变
    bg_style = f"background: {bg};" if 'gradient' in bg else f"background-color: {bg};"
    primary_style = f"background: {primary}; -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;" if 'gradient' in primary else f"color: {primary};"

    # PPT 内容布局（标题+内容区）
    slide_content = f"""
<div class="slide-card">
    <div class="slide-meta">
        <div class="slide-title">{index}. {proposal.name}</div>
        <div class="slide-badge">{proposal.visual_style}</div>
    </div>

    <div class="slide-preview" style="{bg_style} color: {text_primary};">
        <!-- 顶部标题区 -->
        <div style="padding: 60px 80px 0 80px;">
            <h2 style="font-size: 48px; font-weight: 700; {primary_style} margin-bottom: 16px;">
                {topic}
            </h2>
            <div style="width: 120px; height: 4px; background: {accent}; margin-bottom: 40px;"></div>
        </div>

        <!-- 内容区 -->
        <div style="padding: 0 80px;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 40px;">
                <!-- 左栏 -->
                <div>
                    <h3 style="font-size: 28px; color: {text_primary}; margin-bottom: 20px; font-weight: 600;">
                        核心观点
                    </h3>
                    <ul style="list-style: none; padding: 0;">
                        <li style="margin-bottom: 16px; padding-left: 24px; position: relative; font-size: 18px; color: {text_secondary};">
                            <span style="position: absolute; left: 0; color: {accent};">▸</span>
                            主题核心要素一
                        </li>
                        <li style="margin-bottom: 16px; padding-left: 24px; position: relative; font-size: 18px; color: {text_secondary};">
                            <span style="position: absolute; left: 0; color: {accent};">▸</span>
                            主题核心要素二
                        </li>
                        <li style="margin-bottom: 16px; padding-left: 24px; position: relative; font-size: 18px; color: {text_secondary};">
                            <span style="position: absolute; left: 0; color: {accent};">▸</span>
                            主题核心要素三
                        </li>
                    </ul>
                </div>

                <!-- 右栏 -->
                <div style="background: {surface}; padding: 32px; border-radius: 12px; border: 2px solid {border};">
                    <h4 style="font-size: 22px; color: {primary if 'gradient' not in primary else text_primary}; margin-bottom: 16px; font-weight: 600;">
                        关键数据
                    </h4>
                    <div style="margin-bottom: 20px;">
                        <div style="font-size: 48px; font-weight: 700; color: {accent};">100%</div>
                        <div style="font-size: 16px; color: {text_secondary};">主题相关指标</div>
                    </div>
                    <div style="font-size: 14px; color: {text_secondary}; line-height: 1.6;">
                        {proposal.reasoning}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="slide-info">
        <div class="color-palette">"""

    # 显示所有颜色（至少4个）
    for key, value in colors.items():
        if 'gradient' in value:
            slide_content += f'''
            <div class="color-chip" style="background: {value};" title="{key}: {value[:50]}..."></div>'''
        else:
            slide_content += f'''
            <div class="color-chip" style="background: {value};" title="{key}: {value}"></div>'''

    slide_content += f"""
        </div>
        <div class="reasoning">
            <strong>配色数量：</strong>{len(colors)} 个颜色
            <br><strong>设计理由：</strong>{proposal.reasoning}
        </div>
    </div>
</div>
"""
    return slide_content


def _html_footer() -> str:
    return """
</div>
<script>
// 点击幻灯片预览区域可以放大查看
document.querySelectorAll('.slide-preview').forEach(slide => {
    slide.style.cursor = 'pointer';
    slide.addEventListener('click', function() {
        if (this.style.transform === 'scale(1.1)') {
            this.style.transform = 'scale(1)';
            this.style.transition = 'transform 0.3s';
        } else {
            this.style.transform = 'scale(1.1)';
            this.style.transition = 'transform 0.3s';
        }
    });
});
</script>
</body>
</html>
"""
