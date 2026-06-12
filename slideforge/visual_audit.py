"""visual_audit.py — Stage 5b 视觉审计物料生成。

产出 `<pptx>_audit/` 目录：
- `slide_NN_compare.png` — 每页 HTML | PPT 双栏对比图
- `audit_contact_NN.png` — 缩略总览图（9 页/张）
- `audit_index.json` — 每页元数据 + 审计状态
- `audit_prompt.md` — 审计指南（供 VLM agent 使用）
"""

import json
from pathlib import Path


def build_compare_image(html_png: Path, ppt_png: Path, out_path: Path,
                        page_idx: int) -> Path | None:
    """生成单页 HTML | PPT 双栏拼图。左=HTML 参考，右=PPT 输出。"""
    from PIL import Image, ImageDraw, ImageFont

    # 跨平台字体兜底
    title_font = None
    for name in ("arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"):
        try:
            title_font = ImageFont.truetype(name, 36)
            break
        except Exception:
            continue
    if title_font is None:
        title_font = ImageFont.load_default()

    try:
        html_img = Image.open(html_png).convert("RGB").resize((1920, 1080))
        ppt_img = Image.open(ppt_png).convert("RGB").resize((1920, 1080))
    except Exception as e:
        print(f"  [warn] compare build fail page {page_idx}: {e}")
        return None

    bar_h = 60
    composite = Image.new("RGB", (1920 * 2 + 8, 1080 + bar_h), (255, 255, 255))
    d = ImageDraw.Draw(composite)

    # 标题栏
    d.rectangle((0, 0, 1920, bar_h), fill=(245, 245, 247))
    d.rectangle((1928, 0, 3848, bar_h), fill=(255, 245, 235))
    d.text((28, 12), f"HTML 参考  ·  slide {page_idx:02d}", fill=(20, 20, 20),
           font=title_font)
    d.text((1956, 12), f"PPT 输出  ·  slide {page_idx:02d}", fill=(20, 20, 20),
           font=title_font)

    # 中间分隔线
    d.rectangle((1920, 0, 1928, 1080 + bar_h), fill=(200, 200, 200))

    composite.paste(html_img, (0, bar_h))
    composite.paste(ppt_img, (1928, bar_h))
    composite.save(out_path, optimize=True)
    return out_path


def build_contact_sheets(compare_dir: Path, page_indices: list[int],
                         per_sheet: int = 9) -> list[dict]:
    """从 compare 图生成缩略总览图。"""
    from PIL import Image, ImageDraw, ImageFont

    # 清理旧 contact sheet
    for old in compare_dir.glob("audit_contact_*.png"):
        try:
            old.unlink()
        except OSError:
            pass

    title_font = None
    for name in ("arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"):
        try:
            title_font = ImageFont.truetype(name, 20)
            break
        except Exception:
            continue
    if title_font is None:
        title_font = ImageFont.load_default()

    contact_sheets = []
    cols = 3
    tile_w = 760
    label_h = 28
    gap = 28
    margin = 18

    for start in range(0, len(page_indices), per_sheet):
        chunk = page_indices[start:start + per_sheet]
        images = []
        for idx in chunk:
            path = compare_dir / f"slide_{idx:02d}_compare.png"
            if not path.exists():
                continue
            img = Image.open(path).convert("RGB")
            tile_h = int(round(tile_w * img.height / img.width))
            images.append((idx, img.resize((tile_w, tile_h))))
        if not images:
            continue

        rows = (len(images) + cols - 1) // cols
        tile_h = images[0][1].height
        sheet_w = margin * 2 + cols * tile_w + (cols - 1) * gap
        sheet_h = margin * 2 + rows * (label_h + tile_h) + (rows - 1) * gap
        sheet = Image.new("RGB", (sheet_w, sheet_h), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        for pos, (idx, img) in enumerate(images):
            col = pos % cols
            row = pos // cols
            x = margin + col * (tile_w + gap)
            y = margin + row * (label_h + tile_h + gap)
            draw.text((x, y), f"slide_{idx:02d}", fill=(20, 20, 20), font=title_font)
            sheet.paste(img, (x, y + label_h))

        out_path = compare_dir / f"audit_contact_{chunk[0]:02d}_{chunk[-1]:02d}.png"
        sheet.save(out_path, optimize=True)
        contact_sheets.append({
            "file": out_path.name,
            "path": str(out_path),
            "pages": chunk,
        })

    return contact_sheets


AUDIT_PROMPT_TEMPLATE = """# 视觉审计指南

对比每页 `slide_NN_compare.png`（左=HTML 参考，右=PPT 输出），找出视觉差异。

## 不报告清单（HTML→PPT 自然差异，永不报告）

以下是浏览器 vs PPT 的渲染底层差异，**不是转换 bug，不要报告**：
- 字体 anti-aliasing / hinting / sub-pixel 渲染差异
- 位置漂移 < 5px
- 字号 / 字距 / 行高差异 < 10%
- 颜色饱和度 / 色温微差（同色系内）
- 标题换行位置不同（但不溢出、不叠压、不影响阅读）
- 装饰阴影 / blur 柔和度轻微差异
- 设计偏好（"我觉得这里更应该居中/更大"）

## 严重度阈值

- **HIGH**：瞄一眼就能看到 — 文字被裁切/遮盖、关键元素缺失、字号差 ≥50%、颜色跨色系错误
- **MID**：细看 5 秒确认且能量化 — 位置差 20-50px、字号差 20-50%、文字叠压
- **LOW**：设计师 nice-to-have（多数情况应不报）— 量化差异 10-20% 且影响局部观感

## 检查清单

1. 文字被裁切 / 溢出 slide 边界 / 被遮盖
2. 文字间不该有的重叠 / 叠压
3. 关键元素缺失 / 颜色错误
4. 元素大幅错位（≥ 20px）
5. 图片拉伸 / 变形

## 输出格式（每页一个块）

有问题的页：
```
## page NN
- [HIGH] <元素名>：HTML 半图 <实际状态>；PPT 半图 <差异 + 量化>
```

无问题的页：
```
## page NN · OK
```
"""


def build_audit_package(html_screenshots_dir: Path, ppt_screenshots_dir: Path,
                        out_dir: Path, pptx_path: Path,
                        only_indices: set[int] | None = None) -> dict:
    """产出审计物料包。

    only_indices 给定时走增量：只对列出的页重建 compare 图，其余复用缓存。
    返回 dict 描述包内容。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    html_pngs = sorted(html_screenshots_dir.glob("slide_*.png"))
    ppt_pngs = sorted(ppt_screenshots_dir.glob("slide_*.png"))
    n = min(len(html_pngs), len(ppt_pngs))

    if n == 0:
        return {"out_dir": str(out_dir), "pages": 0, "error": "no screenshots found"}

    pages_meta = []
    fresh_set: set[int] = set()
    cached_set: set[int] = set()

    for i in range(n):
        idx = i + 1
        compare_path = out_dir / f"slide_{idx:02d}_compare.png"
        must_rebuild = (
            only_indices is None
            or idx in only_indices
            or not compare_path.exists()
        )
        if must_rebuild:
            build_compare_image(html_pngs[i], ppt_pngs[i], compare_path, idx)
            fresh_set.add(idx)
        else:
            cached_set.add(idx)

        pages_meta.append({
            "index": idx,
            "compare_image": str(compare_path.name),
            "html_screenshot": str(html_pngs[i].name),
            "ppt_screenshot": str(ppt_pngs[i].name),
            "fresh": idx in fresh_set,
        })

    contact_sheets = build_contact_sheets(out_dir, [p["index"] for p in pages_meta])

    index_data = {
        "pptx": str(pptx_path.name),
        "pptx_path": str(pptx_path),
        "total_pages": n,
        "contact_sheets": contact_sheets,
        "instructions_file": "audit_prompt.md",
        "incremental_mode": only_indices is not None,
        "fresh_indices": sorted(fresh_set),
        "cached_indices": sorted(cached_set),
        "pages": pages_meta,
    }

    (out_dir / "audit_index.json").write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "audit_prompt.md").write_text(AUDIT_PROMPT_TEMPLATE, encoding="utf-8")

    return {
        "out_dir": str(out_dir),
        "pages": n,
        "contact_sheets": contact_sheets,
        "fresh": sorted(fresh_set),
        "cached": sorted(cached_set),
        "incremental": only_indices is not None,
        "index": str(out_dir / "audit_index.json"),
        "prompt": str(out_dir / "audit_prompt.md"),
    }
