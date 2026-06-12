"""font_paths.py — 字体缓存目录。"""
import os
from pathlib import Path


def user_cache_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        root = Path(base) / "html-to-pptx" / "fonts"
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
        root = Path(base) / "html-to-pptx" / "fonts"
    root.mkdir(parents=True, exist_ok=True)
    return root


CACHE_DIR = user_cache_dir()
