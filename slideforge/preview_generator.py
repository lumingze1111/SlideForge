"""
HTML Preview Generator - 生成配色方案的真实 PPT 预览页面
支持点击选择方案 + 确认按钮，通过本地 HTTP server 回传选择结果。
"""

import json
import threading
import time
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .agents.propose_agent import ColorProposal


# 全局变量，用于跨线程传递选择结果
_selected_index: Optional[int] = None
_server_done = threading.Event()


class _SelectionHandler(BaseHTTPRequestHandler):
    """接收浏览器发来的方案选择结果"""

    def do_POST(self) -> None:
        global _selected_index
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            _selected_index = int(data.get("index", 0))
        except Exception:
            _selected_index = 0
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')
        _server_done.set()

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # 静默日志


def wait_for_selection(proposals_count: int, port: int = 7788, timeout: int = 300) -> int:
    """
    启动本地 HTTP server，等待浏览器回传选择结果。

    Args:
        proposals_count: 方案数量（用于校验）
        port: 监听端口
        timeout: 超时秒数

    Returns:
        用户选择的方案索引（0-based）
    """
    global _selected_index, _server_done
    _selected_index = None
    _server_done.clear()

    server = HTTPServer(("localhost", port), _SelectionHandler)

    def serve() -> None:
        server.timeout = 1
        while not _server_done.is_set():
            server.handle_request()
        server.server_close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    print(f"\n  ⏳ 等待你在浏览器中选择方案并点击「确认方案」...")
    _server_done.wait(timeout=timeout)

    if _selected_index is None:
        print("  ⚠️  超时未选择，使用第 0 号推荐方案")
        return 0

    return _selected_index


def generate_preview_html(
    proposals: List,
    topic: str,
    output_path: str = None,
    server_port: int = 7788,
) -> str:
    """
    生成配色方案对比预览页面（HTML）。
    每个方案渲染为真实 PPT 样式，页面底部有「确认方案」按钮。

    Args:
        proposals: ColorProposal 列表
        topic: 幻灯片主题
        output_path: HTML 输出路径
        server_port: 回传选择结果的本地 HTTP server 端口

    Returns:
        HTML 文件绝对路径
    """
    if output_path is None:
        output_path = "slideforge_preview.html"

    html_parts = [_html_header(server_port)]

    for i, proposal in enumerate(proposals):
        slide_html = _generate_slide_preview(proposal, topic, i)
        html_parts.append(slide_html)

    html_parts.append(_html_footer(len(proposals), server_port))

    output_path = Path(output_path)
    output_path.write_text("\n".join(html_parts), encoding="utf-8")
    return str(output_path.absolute())


def _html_header(port: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SlideForge 配色方案预览</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background: #111827;
    color: #e0e0e0;
    padding: 40px 20px 120px;
}}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{
    text-align: center;
    font-size: 28px;
    margin-bottom: 8px;
    color: #fff;
}}
.subtitle {{
    text-align: center;
    font-size: 14px;
    color: #6b7280;
    margin-bottom: 40px;
}}
.slide-card {{
    background: #1f2937;
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 32px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    border: 3px solid transparent;
    cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
    position: relative;
}}
.slide-card:hover {{
    border-color: #4b83ff;
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(75,131,255,0.25);
}}
.slide-card.selected {{
    border-color: #4ade80;
    box-shadow: 0 0 0 4px rgba(74,222,128,0.2), 0 8px 32px rgba(0,0,0,0.5);
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
    z-index: 10;
}}
.slide-card.selected .selected-badge {{
    display: inline-block;
}}
.slide-meta {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}}
.slide-title {{
    font-size: 20px;
    font-weight: 600;
    color: #fff;
}}
.slide-badge {{
    display: inline-block;
    padding: 4px 14px;
    background: #374151;
    color: #9ca3af;
    border-radius: 20px;
    font-size: 13px;
}}
.slide-preview-wrapper {{
    width: 100%;
    overflow-x: auto;
}}
.slide-preview {{
    width: 1280px;
    height: 720px;
    margin: 0 auto;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 6px 24px rgba(0,0,0,0.6);
    position: relative;
    pointer-events: none;
}}
.slide-info {{
    display: flex;
    gap: 20px;
    margin-top: 16px;
    font-size: 13px;
    align-items: center;
}}
.color-palette {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.color-chip {{
    width: 36px;
    height: 36px;
    border-radius: 6px;
    border: 2px solid rgba(255,255,255,0.08);
    flex-shrink: 0;
}}
.reasoning {{ flex: 1; color: #9ca3af; line-height: 1.6; }}

/* 底部固定确认栏 */
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
    box-shadow: 0 -4px 20px rgba(0,0,0,0.4);
}}
.confirm-hint {{
    font-size: 14px;
    color: #9ca3af;
}}
.confirm-hint span {{
    color: #4ade80;
    font-weight: 600;
}}
.confirm-btn {{
    background: #4ade80;
    color: #111827;
    border: none;
    padding: 12px 40px;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
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
<h1>🎨 SlideForge 配色方案预览</h1>
<p class="subtitle">点击方案卡片选择，然后点击底部「确认方案」按钮</p>
"""


def _generate_slide_preview(proposal, topic: str, index: int) -> str:
    colors = proposal.colors

    bg = colors.get("background", colors.get("gradient_bg", "#FFFFFF"))
    primary = colors.get("primary", "#1976D2")
    accent = colors.get("accent", colors.get("accent_1", "#FFC107"))
    text_primary = colors.get("text_primary", "#212121")
    text_secondary = colors.get("text_secondary", "#757575")
    surface = colors.get("surface", colors.get("card_bg", "#F5F5F5"))
    border = colors.get("border", colors.get("divider", "#E0E0E0"))

    is_gradient_bg = "gradient" in bg
    bg_style = f"background: {bg};" if is_gradient_bg else f"background-color: {bg};"

    is_gradient_primary = "gradient" in primary
    if is_gradient_primary:
        primary_style = (
            f"background: {primary}; "
            "-webkit-background-clip: text; "
            "-webkit-text-fill-color: transparent; "
            "background-clip: text;"
        )
        primary_solid = text_primary
    else:
        primary_style = f"color: {primary};"
        primary_solid = primary

    chips_html = ""
    for key, value in colors.items():
        display = value[:50] + "..." if len(value) > 50 else value
        bg_attr = f"background: {value};" if "gradient" in value else f"background-color: {value};"
        chips_html += f'<div class="color-chip" style="{bg_attr}" title="{key}: {display}"></div>\n'

    return f"""
<div class="slide-card" data-index="{index}" onclick="selectCard(this)">
    <div class="selected-badge">✓ 已选择</div>
    <div class="slide-meta">
        <div class="slide-title">{index + 1}. {proposal.name}</div>
        <div class="slide-badge">{proposal.visual_style}</div>
    </div>
    <div class="slide-preview-wrapper">
        <div class="slide-preview" style="{bg_style} color: {text_primary};">
            <div style="padding: 60px 80px 0 80px;">
                <h2 style="font-size: 48px; font-weight: 700; {primary_style} margin-bottom: 16px;">
                    {topic}
                </h2>
                <div style="width: 120px; height: 4px; background: {accent}; margin-bottom: 40px;"></div>
            </div>
            <div style="padding: 0 80px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 40px;">
                    <div>
                        <h3 style="font-size: 28px; color: {text_primary}; margin-bottom: 20px; font-weight: 600;">核心观点</h3>
                        <ul style="list-style: none; padding: 0;">
                            <li style="margin-bottom: 16px; padding-left: 24px; position: relative; font-size: 18px; color: {text_secondary};">
                                <span style="position: absolute; left: 0; color: {accent};">▸</span>主题核心要素一
                            </li>
                            <li style="margin-bottom: 16px; padding-left: 24px; position: relative; font-size: 18px; color: {text_secondary};">
                                <span style="position: absolute; left: 0; color: {accent};">▸</span>主题核心要素二
                            </li>
                            <li style="margin-bottom: 16px; padding-left: 24px; position: relative; font-size: 18px; color: {text_secondary};">
                                <span style="position: absolute; left: 0; color: {accent};">▸</span>主题核心要素三
                            </li>
                        </ul>
                    </div>
                    <div style="background: {surface}; padding: 32px; border-radius: 12px; border: 2px solid {border};">
                        <h4 style="font-size: 22px; color: {primary_solid}; margin-bottom: 16px; font-weight: 600;">关键数据</h4>
                        <div style="margin-bottom: 20px;">
                            <div style="font-size: 48px; font-weight: 700; color: {accent};">100%</div>
                            <div style="font-size: 16px; color: {text_secondary};">主题相关指标</div>
                        </div>
                        <div style="font-size: 14px; color: {text_secondary}; line-height: 1.6;">{proposal.reasoning}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="slide-info">
        <div class="color-palette">
            {chips_html}
        </div>
        <div class="reasoning">
            <strong>配色数量：</strong>{len(colors)} 个 &nbsp;|&nbsp;
            <strong>设计理由：</strong>{proposal.reasoning}
        </div>
    </div>
</div>
"""


def _html_footer(count: int, port: int) -> str:
    return f"""
</div>

<!-- 底部确认栏 -->
<div class="confirm-bar">
    <div class="confirm-hint" id="hint">请先点击上方任意方案卡片选择</div>
    <button class="confirm-btn" id="confirmBtn" disabled onclick="confirmSelection()">确认方案</button>
</div>

<script>
const PORT = {port};
let selectedIndex = null;

function selectCard(el) {{
    document.querySelectorAll('.slide-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    selectedIndex = parseInt(el.dataset.index);
    const title = el.querySelector('.slide-title').textContent.trim();
    document.getElementById('hint').innerHTML = '已选择：<span>' + title + '</span>';
    document.getElementById('confirmBtn').disabled = false;
}}

function confirmSelection() {{
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
        btn.textContent = '✓ 已确认，正在生成 PPT…';
        btn.style.background = '#22c55e';
        document.getElementById('hint').innerHTML = '<span>方案已提交！窗口即将关闭…</span>';
        setTimeout(() => window.close(), 800);
    }})
    .catch(err => {{
        btn.disabled = false;
        btn.textContent = '确认方案';
        alert('提交失败：' + err.message);
    }});
}}
</script>
</body>
</html>
"""
