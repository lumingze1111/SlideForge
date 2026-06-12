"""自动运行 SlideForge 完整流程并截图。

用法：python tools/capture_demo.py <主题>
示例：python tools/capture_demo.py 库里
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)


def post_selection(port: int, index: int = 0, timeout: int = 120) -> bool:
    """POST 选择到交互服务器。"""
    url = f"http://localhost:{port}/select"
    data = json.dumps({"index": index}).encode("utf-8")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=5)
            result = json.loads(resp.read())
            print(f"  ✓ 已选择第 {index + 1} 项 (port {port})")
            return True
        except Exception:
            time.sleep(2)
    print(f"  ✗ 超时等待 port {port}")
    return False


def screenshot_url(html_path: Path, out_path: Path, full_page: bool = False):
    """用 Playwright 截取 HTML 页面。"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(out_path), full_page=full_page)
        browser.close()
    print(f"  📸 {out_path.name} ({out_path.stat().st_size:,} B)")


def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "库里"
    print(f"\n{'='*60}")
    print(f"  SlideForge Demo Capture — 主题：{topic}")
    print(f"{'='*60}\n")

    # 清理旧预览文件
    for old in OUTPUT_DIR.glob("slideforge_*preview*.html"):
        old.unlink()

    # ── 启动 main.py ────────────────────────────────────────────
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "main.py"), topic],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # ── 监控输出，在交互节点自动选择 ─────────────────────────────
    color_selected = False
    outline_selected = False
    output_lines = []

    deadline = time.time() + 600  # 10 分钟超时
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
            continue
        print(line, end="")
        output_lines.append(line)

        # 配色方案选择页面已启动
        if "配色方案" in line and "http" in line and not color_selected:
            time.sleep(3)  # 等浏览器打开
            screenshot_url(
                OUTPUT_DIR / "slideforge_preview.html",
                DOCS_DIR / "color_preview.png",
            )
            post_selection(7788, index=0)
            color_selected = True

        # 大纲结构选择页面已启动
        if "大纲" in line and "http" in line and not outline_selected:
            time.sleep(3)
            screenshot_url(
                OUTPUT_DIR / "slideforge_outline_preview.html",
                DOCS_DIR / "outline_preview.png",
            )
            post_selection(7789, index=0)
            outline_selected = True

        # 步骤 0 的 "按 Enter 继续"
        if "按 Enter 继续" in line:
            try:
                proc.stdin.write("\n")
                proc.stdin.flush()
            except Exception:
                pass

    proc.wait(timeout=30)

    # ── 找到生成的 HTML 和 PPTX ──────────────────────────────────
    html_files = sorted(
        OUTPUT_DIR.glob(f"slides_{topic}*.html"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    pptx_files = sorted(
        OUTPUT_DIR.glob(f"slides_{topic}*.pptx"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )

    if not html_files:
        print(f"\n❌ 未找到生成的 HTML 文件")
        sys.exit(1)

    html_path = html_files[0]
    pptx_path = pptx_files[0] if pptx_files else None

    print(f"\n{'='*60}")
    print(f"  生成文件：")
    print(f"  HTML: {html_path}")
    if pptx_path:
        print(f"  PPTX: {pptx_path}")
    print(f"{'='*60}\n")

    # ── 截图 HTML 预览 ──────────────────────────────────────────
    print("截取 HTML 幻灯片预览...")
    screenshot_url(html_path, DOCS_DIR / "slides_html.png")

    # ── 截图 PPTX ───────────────────────────────────────────────
    if pptx_path:
        print("渲染 PPTX 截图...")
        from slideforge.pptx_renderer import try_render_pptx
        import shutil
        render_dir = Path("/tmp/sf_ppt_demo")
        shutil.rmtree(render_dir, ignore_errors=True)
        render_dir.mkdir(parents=True, exist_ok=True)
        engine, count = try_render_pptx(pptx_path, render_dir)
        if engine:
            shutil.copy(render_dir / "slide_01.png", DOCS_DIR / "ppt_sample.png")
            print(f"  📸 ppt_sample.png ({DOCS_DIR / 'ppt_sample.png'})")
        else:
            # 失败则用 HTML 截图代替
            print("  ⚠ LibreOffice 不可用，用 HTML 截图代替")
            shutil.copy(DOCS_DIR / "slides_html.png", DOCS_DIR / "ppt_sample.png")

    print(f"\n✅ 截图完成，保存在 {DOCS_DIR}/")
    print(f"   color_preview.png  — 配色方案选择")
    print(f"   outline_preview.png — 大纲结构选择")
    print(f"   slides_html.png    — HTML 幻灯片预览")
    print(f"   ppt_sample.png     — PPTX 输出效果")


if __name__ == "__main__":
    main()
