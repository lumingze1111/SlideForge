"""pptx_renderer.py — 将 PPTX 逐页渲染为 PNG。

渲染器优先级（自动降级）：
1. PowerPoint COM（Windows + Office + pywin32）
2. LibreOffice headless + pdf2image（跨平台）
3. 都不可用 → 跳过，返回 None

不会让 convert 失败 —— 渲染不可用时仅打印警告。
"""

import shutil
import subprocess
import tempfile
from pathlib import Path


def try_render_pptx(pptx_path: Path, out_dir: Path,
                    only_indices: set[int] | None = None) -> tuple[str | None, int]:
    """按优先级尝试渲染器。返回 (engine_label, slide_count)。

    only_indices 给定时走增量：未列出且 cache 命中的页跳过 export。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 尝试 LibreOffice（跨平台）
    count = _try_libreoffice(pptx_path, out_dir, only_indices=only_indices)
    if count > 0:
        return ("LibreOffice", count)

    # 2. 尝试 PowerPoint COM（仅 Windows）
    count = _try_powerpoint_com(pptx_path, out_dir, only_indices=only_indices)
    if count > 0:
        return ("PowerPoint", count)

    return (None, 0)


def _find_soffice() -> str | None:
    """查找 LibreOffice soffice 可执行文件。"""
    # 先查 PATH
    path = shutil.which("soffice") or shutil.which("libreoffice")
    if path:
        return path
    # macOS 标准路径
    mac_path = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    if mac_path.exists():
        return str(mac_path)
    return None


def _try_libreoffice(pptx_path: Path, out_dir: Path,
                     only_indices: set[int] | None = None) -> int:
    """LibreOffice headless pptx → PDF → 逐页 PNG。"""
    soffice = _find_soffice()
    if not soffice:
        return 0

    try:
        from pdf2image import convert_from_path, pdfinfo_from_path
    except ImportError:
        return 0

    try:
        with tempfile.TemporaryDirectory(prefix="sf_lo_") as td:
            r = subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf",
                 "--outdir", td, str(pptx_path)],
                capture_output=True, timeout=120,
            )
            if r.returncode != 0:
                return 0

            pdf = next(Path(td).glob("*.pdf"), None)
            if not pdf:
                return 0

            if only_indices is None:
                pages = convert_from_path(str(pdf), size=(1920, 1080))
                for i, p in enumerate(pages, start=1):
                    p.save(out_dir / f"slide_{i:02d}.png")
                return len(pages)

            info = pdfinfo_from_path(str(pdf))
            total = int(info.get("Pages", 0))
            for i in range(1, total + 1):
                out_png = out_dir / f"slide_{i:02d}.png"
                if i not in only_indices and out_png.exists():
                    continue
                rendered = convert_from_path(
                    str(pdf), size=(1920, 1080),
                    first_page=i, last_page=i,
                )
                if rendered:
                    rendered[0].save(out_png)
            return total
    except Exception:
        return 0


def _try_powerpoint_com(pptx_path: Path, out_dir: Path,
                        only_indices: set[int] | None = None) -> int:
    """Windows PowerPoint COM 渲染（需 pywin32）。"""
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return 0

    try:
        pythoncom.CoInitialize()
        app = win32com.client.Dispatch("PowerPoint.Application")
        try:
            pres = app.Presentations.Open(str(pptx_path.resolve()), True, False, True)
            try:
                total = 0
                for i, slide in enumerate(pres.Slides, start=1):
                    total += 1
                    out_png = out_dir / f"slide_{i:02d}.png"
                    must_render = (
                        only_indices is None
                        or i in only_indices
                        or not out_png.exists()
                    )
                    if must_render:
                        slide.Export(str(out_png), "PNG", 1920, 1080)
                return total
            finally:
                pres.Close()
        finally:
            app.Quit()
    except Exception:
        return 0
