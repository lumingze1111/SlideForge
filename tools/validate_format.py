#!/usr/bin/env python3
"""validate_format.py — comprehensive HTML→PPTX format diff.

Walks every measurement record and verifies the PPTX has a corresponding
shape with matching:
  - position (within tolerance)
  - text content (exact)
  - per-run: font size, color, bold/italic, font family
  - paragraph horizontal alignment

Reports concrete mismatches per slide. Used by the validation loop to
decide whether the PPTX faithfully represents the HTML.

Usage:
    python tools/validate_format.py <html_path> [--out OUT.pptx] [--max-attempts 3]
"""

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NSP = "http://schemas.openxmlformats.org/presentationml/2006/main"
NSA = "http://schemas.openxmlformats.org/drawingml/2006/main"

PX_TO_EMU = 6350
EMU_TO_PX = 1.0 / PX_TO_EMU
PX_TO_PT = 0.75
SIZE_SCALE = 1.5
EMU_SIZE_TO_PX = 1.0 / (PX_TO_EMU * SIZE_SCALE)
CENTER_OFFSET = (SIZE_SCALE - 1.0) / 2.0  # 0.25 — 中心缩放时位置的左/上偏移

POS_TOL = 8.0          # px
TEXT_PREFIX = 24       # chars compared for text matching


# ── Color parsing ─────────────────────────────────────────────────────────────

def parse_css_color(s) -> tuple[int, int, int] | None:
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    m = re.match(r'rgba?\(([^)]+)\)', s, re.IGNORECASE)
    if m:
        parts = [p.strip() for p in m.group(1).split(',')]
        try:
            return (int(float(parts[0])), int(float(parts[1])), int(float(parts[2])))
        except (ValueError, IndexError):
            return None
    if s.startswith('#'):
        h = s[1:]
        if len(h) in (3, 4):
            h = ''.join(ch * 2 for ch in h)
        if len(h) >= 6:
            try:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            except ValueError:
                return None
    return None


def hex_to_rgb(s: str) -> tuple[int, int, int] | None:
    if not s or len(s) < 6:
        return None
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return None


def color_close(a, b, tol: int = 4) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# ── PPTX shape extraction ────────────────────────────────────────────────────

def load_pptx_shapes(pptx_path: Path) -> list[list[dict]]:
    from lxml import etree
    out = []
    with zipfile.ZipFile(pptx_path) as zf:
        slide_names = sorted(
            (n for n in zf.namelist() if re.match(r'ppt/slides/slide\d+\.xml$', n)),
            key=lambda n: int(re.search(r'slide(\d+)', n).group(1)),
        )
        for name in slide_names:
            root = etree.fromstring(zf.read(name))
            cSld = root.find(f'{{{NSP}}}cSld')
            spTree = cSld.find(f'{{{NSP}}}spTree') if cSld is not None else None
            shapes = []
            if spTree is not None:
                for sp in spTree:
                    tag = etree.QName(sp).localname
                    if tag in ('nvGrpSpPr', 'grpSpPr'):
                        continue
                    shapes.append(_shape_summary(sp, tag))
            out.append(shapes)
    return out


def _shape_summary(sp, tag) -> dict:
    from lxml import etree
    spPr = sp.find(f'{{{NSP}}}spPr')
    info = {
        'tag': tag, 'x': 0.0, 'y': 0.0, 'w': 0.0, 'h': 0.0,
        'fill': None, 'gradient': False, 'shape': None,
        'has_image': tag == 'pic', 'text': '', 'runs': [], 'algn': None,
    }
    if spPr is not None:
        xfrm = spPr.find(f'{{{NSA}}}xfrm')
        if xfrm is not None:
            off = xfrm.find(f'{{{NSA}}}off')
            ext = xfrm.find(f'{{{NSA}}}ext')
            if off is not None:
                info['x'] = int(off.get('x', '0')) * EMU_TO_PX
                info['y'] = int(off.get('y', '0')) * EMU_TO_PX
            if ext is not None:
                info['w'] = int(ext.get('cx', '0')) * EMU_SIZE_TO_PX
                info['h'] = int(ext.get('cy', '0')) * EMU_SIZE_TO_PX
        # 反转中心缩放偏移，使位置与测量记录的 (rx, ry) 可比
        info['x'] += info['w'] * CENTER_OFFSET
        info['y'] += info['h'] * CENTER_OFFSET
        prst = spPr.find(f'{{{NSA}}}prstGeom')
        if prst is not None:
            info['shape'] = prst.get('prst')
        if spPr.find(f'{{{NSA}}}gradFill') is not None:
            info['gradient'] = True
        sf = spPr.find(f'{{{NSA}}}solidFill')
        if sf is not None:
            srgb = sf.find(f'{{{NSA}}}srgbClr')
            if srgb is not None:
                info['fill'] = hex_to_rgb(srgb.get('val', ''))

    txBody = sp.find(f'{{{NSP}}}txBody')
    if txBody is not None:
        full_text_parts = []
        runs = []
        first_algn = None
        for p in txBody.findall(f'{{{NSA}}}p'):
            pPr = p.find(f'{{{NSA}}}pPr')
            if pPr is not None and first_algn is None:
                first_algn = pPr.get('algn')
            for r in p.findall(f'{{{NSA}}}r'):
                t = r.find(f'{{{NSA}}}t')
                txt = (t.text or '') if t is not None else ''
                full_text_parts.append(txt)
                rPr = r.find(f'{{{NSA}}}rPr')
                run_info = {'text': txt, 'sz': None, 'bold': False, 'italic': False,
                            'color': None, 'latin': None}
                if rPr is not None:
                    sz = rPr.get('sz')
                    if sz:
                        run_info['sz'] = int(sz)  # 1/100 pt
                    if rPr.get('b') == '1':
                        run_info['bold'] = True
                    if rPr.get('i') == '1':
                        run_info['italic'] = True
                    sf2 = rPr.find(f'{{{NSA}}}solidFill')
                    if sf2 is not None:
                        srgb = sf2.find(f'{{{NSA}}}srgbClr')
                        if srgb is not None:
                            run_info['color'] = hex_to_rgb(srgb.get('val', ''))
                    latin = rPr.find(f'{{{NSA}}}latin')
                    if latin is not None:
                        run_info['latin'] = latin.get('typeface')
                runs.append(run_info)
            for _br in p.findall(f'{{{NSA}}}br'):
                full_text_parts.append('\n')
        info['text'] = ''.join(full_text_parts)
        info['runs'] = runs
        info['algn'] = first_algn
    return info


# ── Matching ──────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    return re.sub(r'\s+', ' ', s or '').strip()


def _text_match(rec_text: str, shape_text: str) -> bool:
    a, b = _normalize(rec_text), _normalize(shape_text)
    if not a and not b:
        return True
    if not a or not b:
        return False
    a, b = a[:TEXT_PREFIX], b[:TEXT_PREFIX]
    return a == b or a in b or b in a


def match_records_to_shapes(records: list[dict], shapes: list[dict]) -> dict:
    """Greedy match: for each record, find the closest unused shape."""
    used = set()
    pairs: list[tuple[int, int]] = []
    unmatched: list[tuple[int, str]] = []

    # First pass: deco_snapshot covering full slide → gradient_bg rect
    for ri, rec in enumerate(records):
        if rec.get('kind') != 'deco_snapshot':
            continue
        rect = rec.get('rect', {})
        if rect.get('w', 0) < 1900 or rect.get('h', 0) < 1060:
            continue
        for si, s in enumerate(shapes):
            if si in used:
                continue
            if s.get('gradient') and s['w'] >= 1900 and s['h'] >= 1060:
                used.add(si)
                pairs.append((ri, si))
                break

    for ri, rec in enumerate(records):
        if any(p == ri for p, _ in pairs):
            continue
        rect = rec.get('rect', {})
        rx, ry = rect.get('x', 0), rect.get('y', 0)
        rw, rh = rect.get('w', 0), rect.get('h', 0)
        kind = rec.get('kind', '')
        rtext = rec.get('text', '') if kind == 'text' else ''

        # Candidate-set strategy:
        # - text records: only consider shapes whose text matches AND whose
        #   position is near. This is safer than score-only because PPTX
        #   over-sizes text boxes.
        # - non-text: pure geometric proximity.
        best, best_score = None, float('inf')
        for si, s in enumerate(shapes):
            if si in used:
                continue
            dx = abs(s['x'] - rx)
            dy = abs(s['y'] - ry)
            if kind == 'text' and rtext:
                if not _text_match(rtext, s.get('text', '')):
                    continue
                score = dx + dy
            else:
                # non-text: must also have similar size since text isn't a fingerprint
                dw = abs(s['w'] - rw)
                dh = abs(s['h'] - rh)
                score = dx + dy + dw + dh
            if score < best_score:
                best_score = score
                best = si

        if best is None:
            unmatched.append((ri, 'no candidate'))
            continue

        # Position must be close
        s = shapes[best]
        dx = abs(s['x'] - rx)
        dy = abs(s['y'] - ry)
        if dx > POS_TOL or dy > POS_TOL:
            unmatched.append((ri, f'position off by ({dx:.0f},{dy:.0f})'))
            continue

        used.add(best)
        pairs.append((ri, best))

    return {
        'pairs': pairs,
        'unmatched_records': unmatched,
        'spurious_shapes': [si for si in range(len(shapes)) if si not in used],
    }


# ── Style verification ────────────────────────────────────────────────────────

def _is_bold_html(run: dict) -> bool:
    fw = run.get('fontWeight', '400')
    try:
        return int(str(fw).rstrip('px') or 400) >= 600
    except ValueError:
        return str(fw).lower() in ('bold', 'bolder')


def verify_text_runs(rec: dict, shape: dict) -> list[str]:
    """Compare measurement runs vs PPTX runs. Return list of issue strings."""
    issues = []
    rec_runs = [r for r in (rec.get('runs') or []) if not r.get('linebreak')]
    sh_runs = shape.get('runs') or []

    if not rec_runs and not sh_runs:
        return issues
    if len(rec_runs) != len(sh_runs):
        if abs(len(rec_runs) - len(sh_runs)) >= 2:
            issues.append(f'run count: html={len(rec_runs)} pptx={len(sh_runs)}')
    pairs = list(zip(rec_runs, sh_runs))
    for i, (rr, sr) in enumerate(pairs):
        # Font size
        rr_fs = float(rr.get('fontSize', 16) or 16)
        rr_pt = rr_fs * PX_TO_PT
        if sr.get('sz') is not None:
            sr_pt = sr['sz'] / 100.0
            if abs(rr_pt - sr_pt) > 0.5:
                issues.append(f'run{i} font size: html={rr_pt:.1f}pt pptx={sr_pt:.1f}pt')
        # Color
        rr_color = parse_css_color(rr.get('color'))
        sr_color = sr.get('color')
        if rr_color and sr_color and not color_close(rr_color, sr_color):
            issues.append(f'run{i} color: html={rr_color} pptx={sr_color}')
        # Bold
        rr_bold = _is_bold_html(rr)
        if rr_bold != sr.get('bold', False):
            issues.append(f'run{i} bold: html={rr_bold} pptx={sr.get("bold")}')
        # Italic
        rr_italic = (rr.get('fontStyle') or '').lower() == 'italic'
        if rr_italic != sr.get('italic', False):
            issues.append(f'run{i} italic: html={rr_italic} pptx={sr.get("italic")}')
    return issues


def verify_alignment(rec: dict, shape: dict) -> list[str]:
    issues = []
    style = rec.get('style') or {}
    align = (style.get('textAlign') or 'start').lower()
    display = (style.get('display') or '').lower()
    align_map = {'start': 'l', 'left': 'l', 'center': 'ctr', 'right': 'r', 'end': 'r'}
    expected = align_map.get(align, 'l')
    if 'flex' in display or 'grid' in display:
        jc = (style.get('justifyContent') or '').lower()
        jc_map = {'center': 'ctr', 'flex-end': 'r', 'end': 'r', 'right': 'r',
                  'flex-start': 'l', 'start': 'l', 'left': 'l',
                  'space-between': 'just'}
        if jc in jc_map:
            expected = jc_map[jc]
    actual = shape.get('algn') or 'l'
    if actual != expected:
        issues.append(f'algn: html={expected} pptx={actual}')
    return issues


def verify_shape_fill(rec: dict, shape: dict) -> list[str]:
    issues = []
    deco = rec.get('deco') or {}
    if not deco.get('hasBg'):
        return issues
    expected = parse_css_color(deco.get('bg'))
    actual = shape.get('fill')
    if expected and actual and not color_close(expected, actual, tol=4):
        issues.append(f'fill: html={expected} pptx={actual}')
    return issues


# ── Position verification ──────────────────────────────────────────────────────

SLIDE_W_PX = 1920.0
SLIDE_H_PX = 1080.0
POS_PROP_TOL = 0.02   # 比例位置偏差容忍度（2%）


def verify_position(rec: dict, shape: dict, slide_w: float = SLIDE_W_PX,
                    slide_h: float = SLIDE_H_PX) -> list[str]:
    """校验元素在 HTML 与 PPTX 中的比例位置是否一致。

    比较元素中心的相对位置（center_x / slide_w）和尺寸比例。
    返回 issue 列表。
    """
    issues = []
    rect = rec.get('rect') or {}
    rx, ry = rect.get('x', 0), rect.get('y', 0)
    rw, rh = rect.get('w', 0), rect.get('h', 0)
    sx, sy = shape['x'], shape['y']
    sw, sh = shape['w'], shape['h']

    if rw <= 0 or rh <= 0 or sw <= 0 or sh <= 0:
        return issues

    # 比例中心
    h_center_x = (rx + rw / 2.0) / slide_w
    h_center_y = (ry + rh / 2.0) / slide_h
    p_center_x = (sx + sw / 2.0) / slide_w
    p_center_y = (sy + sh / 2.0) / slide_h

    dx_prop = abs(p_center_x - h_center_x)
    dy_prop = abs(p_center_y - h_center_y)

    if dx_prop > POS_PROP_TOL:
        issues.append(
            f'pos center_x: html={h_center_x:.3f} pptx={p_center_x:.3f} '
            f'(Δ={dx_prop:.3f}, html=({rx:.0f},{ry:.0f},{rw:.0f},{rh:.0f}) '
            f'pptx=({sx:.0f},{sy:.0f},{sw:.0f},{sh:.0f}))')
    if dy_prop > POS_PROP_TOL:
        issues.append(
            f'pos center_y: html={h_center_y:.3f} pptx={p_center_y:.3f} '
            f'(Δ={dy_prop:.3f})')

    # 尺寸比例
    h_w_ratio = rw / slide_w
    h_h_ratio = rh / slide_h
    p_w_ratio = sw / slide_w
    p_h_ratio = sh / slide_h
    dw = abs(p_w_ratio - h_w_ratio)
    dh = abs(p_h_ratio - h_h_ratio)
    if dw > POS_PROP_TOL:
        issues.append(f'pos w_ratio: html={h_w_ratio:.3f} pptx={p_w_ratio:.3f} (Δ={dw:.3f})')
    if dh > POS_PROP_TOL:
        issues.append(f'pos h_ratio: html={h_h_ratio:.3f} pptx={p_h_ratio:.3f} (Δ={dh:.3f})')

    # 溢出检测
    p_right = sx + sw
    p_bottom = sy + sh
    if sx < -1 or sy < -1:
        issues.append(f'pos overflow: shape starts outside slide (x={sx:.0f}, y={sy:.0f})')
    if p_right > slide_w + 1 or p_bottom > slide_h + 1:
        issues.append(
            f'pos overflow: shape exceeds slide (right={p_right:.0f}, bottom={p_bottom:.0f})')

    return issues


# ── Main diff ─────────────────────────────────────────────────────────────────

def diff_decks(measurement: dict, pptx_path: Path) -> dict:
    slides_meas = measurement.get('slides') or [measurement]
    slides_pptx = load_pptx_shapes(pptx_path)

    report = {
        'slide_count_match': len(slides_meas) == len(slides_pptx),
        'meas_slides': len(slides_meas),
        'pptx_slides': len(slides_pptx),
        'slides': [],
        'totals': {'records': 0, 'matched': 0, 'unmatched': 0,
                   'style_issues': 0, 'spurious': 0},
    }

    for i, (m, shapes) in enumerate(zip(slides_meas, slides_pptx), start=1):
        records = m.get('records') or []
        match = match_records_to_shapes(records, shapes)

        slide_issues = []
        pos_issues = []
        for ri, si in match['pairs']:
            rec = records[ri]
            shape = shapes[si]
            kind = rec.get('kind', '')
            # 位置比例校验（所有类型）
            pos_issues.extend([
                (ri, 'pos', issue)
                for issue in verify_position(rec, shape)
            ])
            if kind == 'text':
                slide_issues.extend([
                    (ri, 'text-run', issue)
                    for issue in verify_text_runs(rec, shape)
                ])
                slide_issues.extend([
                    (ri, 'text-algn', issue)
                    for issue in verify_alignment(rec, shape)
                ])
            elif kind == 'shape':
                slide_issues.extend([
                    (ri, 'shape-fill', issue)
                    for issue in verify_shape_fill(rec, shape)
                ])

        report['slides'].append({
            'index': i,
            'records': len(records),
            'shapes': len(shapes),
            'matched': len(match['pairs']),
            'unmatched': match['unmatched_records'],
            'spurious': match['spurious_shapes'],
            'style_issues': slide_issues,
            'pos_issues': pos_issues,
        })
        report['totals']['records'] += len(records)
        report['totals']['matched'] += len(match['pairs'])
        report['totals']['unmatched'] += len(match['unmatched_records'])
        report['totals']['style_issues'] += len(slide_issues)
        report['totals']['spurious'] += len(match['spurious_shapes'])
        report['totals']['pos_issues'] = report['totals'].get('pos_issues', 0) + len(pos_issues)

    return report


def print_report(report: dict, verbose: bool = True) -> None:
    t = report['totals']
    print(f"[format] Slides: meas={report['meas_slides']} pptx={report['pptx_slides']} "
          f"({'OK' if report['slide_count_match'] else 'MISMATCH'})")
    print(f"[format] Records: {t['matched']}/{t['records']} matched, "
          f"{t['unmatched']} unmatched, {t['style_issues']} style, "
          f"{t.get('pos_issues', 0)} position, {t['spurious']} spurious")
    if not verbose:
        return
    for s in report['slides']:
        pos_issues = s.get('pos_issues', [])
        bad = s['unmatched'] or s['style_issues'] or pos_issues or s['spurious']
        if not bad:
            continue
        print(f"\n  slide {s['index']}: {s['matched']}/{s['records']} records matched"
              f" ({len(s['style_issues'])} style, {len(pos_issues)} pos)")
        for ri, why in s['unmatched']:
            print(f"    - LOST [{ri}]: {why}")
        for ri, cat, msg in s['style_issues']:
            print(f"    ! STYLE [{ri}/{cat}]: {msg}")
        for ri, cat, msg in pos_issues:
            print(f"    ! POS [{ri}]: {msg}")
        for si in s['spurious']:
            print(f"    + SPURIOUS shape index {si}")


def is_clean(report: dict) -> bool:
    t = report['totals']
    return (
        report['slide_count_match']
        and t['unmatched'] == 0
        and t['style_issues'] == 0
        and t['spurious'] == 0
        and t.get('pos_issues', 0) == 0
    )


# ── Style patching ────────────────────────────────────────────────────────────

def collect_style_fixes(report: dict, measurement: dict, pptx_path: Path) -> dict:
    """For each slide with style issues, collect a list of run-level patches.

    Returns: {slide_idx_0_based: [{shape_idx, run_idx, color?, sz?, bold?, italic?}]}
    """
    slides_meas = measurement.get('slides') or [measurement]
    slides_pptx = load_pptx_shapes(pptx_path)
    fixes: dict[int, list[dict]] = {}
    for slide_report in report['slides']:
        if not slide_report['style_issues']:
            continue
        idx = slide_report['index'] - 1
        if idx >= len(slides_meas) or idx >= len(slides_pptx):
            continue
        records = slides_meas[idx].get('records') or []
        shapes = slides_pptx[idx]
        match = match_records_to_shapes(records, shapes)
        rec_to_shape = {ri: si for ri, si in match['pairs']}

        slide_fixes = []
        seen_runs = set()
        for ri, cat, _msg in slide_report['style_issues']:
            if cat != 'text-run':
                continue
            si = rec_to_shape.get(ri)
            if si is None:
                continue
            rec_runs = [r for r in (records[ri].get('runs') or []) if not r.get('linebreak')]
            sh_runs = shapes[si].get('runs') or []
            for rni in range(min(len(rec_runs), len(sh_runs))):
                key = (si, rni)
                if key in seen_runs:
                    continue
                rr, sr = rec_runs[rni], sh_runs[rni]
                fix: dict = {'shape_idx': si, 'run_idx': rni}
                rr_fs = float(rr.get('fontSize', 16) or 16) * PX_TO_PT
                if sr.get('sz') is not None and abs(rr_fs - sr['sz'] / 100.0) > 0.5:
                    fix['sz'] = max(100, int(round(rr_fs * 100)))
                rr_color = parse_css_color(rr.get('color'))
                if rr_color and not color_close(rr_color, sr.get('color')):
                    fix['color'] = '{:02X}{:02X}{:02X}'.format(*rr_color)
                rr_bold = _is_bold_html(rr)
                if rr_bold != sr.get('bold', False):
                    fix['bold'] = rr_bold
                rr_italic = (rr.get('fontStyle') or '').lower() == 'italic'
                if rr_italic != sr.get('italic', False):
                    fix['italic'] = rr_italic
                if len(fix) > 2:
                    slide_fixes.append(fix)
                    seen_runs.add(key)
        if slide_fixes:
            fixes[idx] = slide_fixes
    return fixes


def patch_pptx_styles(pptx_path: Path, fixes: dict[int, list[dict]]) -> int:
    """Apply style fixes to a PPTX. Returns the number of runs patched."""
    if not fixes:
        return 0
    from lxml import etree
    patched = 0
    tmp = pptx_path.with_suffix('.tmp.pptx')
    with zipfile.ZipFile(pptx_path, 'r') as zin, \
         zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        slide_names = sorted(
            (n for n in zin.namelist() if re.match(r'ppt/slides/slide\d+\.xml$', n)),
            key=lambda n: int(re.search(r'slide(\d+)', n).group(1)),
        )
        for n in zin.namelist():
            data = zin.read(n)
            if n in slide_names:
                idx = slide_names.index(n)
                if idx in fixes:
                    data, n_patched = _apply_slide_fixes(data, fixes[idx])
                    patched += n_patched
            zout.writestr(n, data)
    tmp.replace(pptx_path)
    return patched


def _apply_slide_fixes(xml_bytes: bytes, slide_fixes: list[dict]) -> tuple[bytes, int]:
    from lxml import etree
    root = etree.fromstring(xml_bytes)
    cSld = root.find(f'{{{NSP}}}cSld')
    spTree = cSld.find(f'{{{NSP}}}spTree') if cSld is not None else None
    if spTree is None:
        return xml_bytes, 0

    # Build flat list of shapes in same order as load_pptx_shapes
    shapes: list = []
    for sp in spTree:
        tag = etree.QName(sp).localname
        if tag in ('nvGrpSpPr', 'grpSpPr'):
            continue
        shapes.append(sp)

    patched = 0
    for fix in slide_fixes:
        si = fix['shape_idx']
        rni = fix['run_idx']
        if si >= len(shapes):
            continue
        sp = shapes[si]
        txBody = sp.find(f'{{{NSP}}}txBody')
        if txBody is None:
            continue
        runs = []
        for p in txBody.findall(f'{{{NSA}}}p'):
            for r_el in p.findall(f'{{{NSA}}}r'):
                runs.append(r_el)
        if rni >= len(runs):
            continue
        rPr = runs[rni].find(f'{{{NSA}}}rPr')
        if rPr is None:
            rPr = etree.SubElement(runs[rni], f'{{{NSA}}}rPr')
            runs[rni].insert(0, rPr)

        if 'sz' in fix:
            rPr.set('sz', str(fix['sz']))
        if 'bold' in fix:
            rPr.set('b', '1' if fix['bold'] else '0')
        if 'italic' in fix:
            rPr.set('i', '1' if fix['italic'] else '0')
        if 'color' in fix:
            for sf in rPr.findall(f'{{{NSA}}}solidFill'):
                rPr.remove(sf)
            sf = etree.SubElement(rPr, f'{{{NSA}}}solidFill')
            srgb = etree.SubElement(sf, f'{{{NSA}}}srgbClr')
            srgb.set('val', fix['color'])
            # solidFill must come before latin/ea/cs typeface elements per OOXML schema;
            # move it to immediately after attributes (insert at index 0 of children)
            rPr.remove(sf)
            insert_at = 0
            for i, child in enumerate(rPr):
                if etree.QName(child).localname in ('ln', 'noFill', 'solidFill',
                                                    'gradFill', 'blipFill',
                                                    'pattFill', 'grpFill'):
                    insert_at = i
                    break
                insert_at = i + 1
            rPr.insert(insert_at, sf)
        patched += 1

    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True), patched


# ── Validation loop ───────────────────────────────────────────────────────────

def run_loop(html_path: Path, out_pptx: Path | None,
             max_attempts: int, verbose: bool) -> tuple[bool, Path]:
    from slideforge.pptx_engine.measure import measure
    from slideforge.pptx_engine.assemble import assemble
    from tools.validate_gradients import (
        ensure_pptx_slide_markers, extract_html_gradients,
        extract_pptx_gradients, gradients_match, patch_pptx_gradients,
    )

    src_html = html_path
    fixed, added = ensure_pptx_slide_markers(html_path)
    if verbose and added:
        print(f"[format] HTML preprocess: tagged {added} .slide div(s)")
    work_html = fixed

    if out_pptx is None:
        out_pptx = src_html.with_suffix('.pptx')

    work_dir = Path(tempfile.mkdtemp(prefix='sf_format_'))
    try:
        meas_json = work_dir / 'measurements.json'
        m = measure(work_html, meas_json, no_screenshots=True, verbose=False)
        assemble(m, out_pptx)

        for attempt in range(1, max_attempts + 1):
            if verbose:
                print(f"\n[format] ── Attempt {attempt}/{max_attempts} ──")

            # 1. Gradient sub-loop
            expected_grads = extract_html_gradients(work_html)
            actual_grads = extract_pptx_gradients(out_pptx)
            if len(actual_grads) > len(expected_grads):
                actual_grads = actual_grads[:len(expected_grads)]
            elif len(actual_grads) < len(expected_grads):
                actual_grads += [None] * (len(expected_grads) - len(actual_grads))
            grad_fixes = {
                i: expected_grads[i]
                for i, (h, p) in enumerate(zip(expected_grads, actual_grads))
                if expected_grads[i] is not None and not gradients_match(h, p)
            }
            if grad_fixes:
                if verbose:
                    print(f"[format]   Patching gradients on slides "
                          f"{sorted(i + 1 for i in grad_fixes)}")
                patch_pptx_gradients(out_pptx, grad_fixes)

            # 2. Format diff
            report = diff_decks(m, out_pptx)
            print_report(report, verbose=verbose)

            if is_clean(report):
                if verbose:
                    print("\n[format] ✓ All checks passed.")
                return True, out_pptx

            # 3. Style patches
            style_fixes = collect_style_fixes(report, m, out_pptx)
            if style_fixes:
                n = patch_pptx_styles(out_pptx, style_fixes)
                if verbose:
                    affected = sorted(i + 1 for i in style_fixes)
                    print(f"[format]   Patched {n} run(s) across slides {affected}")
                continue  # re-validate next loop

            # If nothing was patchable, exiting won't help
            if not grad_fixes:
                break

        # Final report after the last patch attempt
        report = diff_decks(m, out_pptx)
        if verbose and not is_clean(report):
            print("\n[format] Final state:")
            print_report(report, verbose=verbose)
        return is_clean(report), out_pptx
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if fixed != src_html and fixed.exists():
            try:
                fixed.unlink()
            except OSError:
                pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('html_path', nargs='?')
    p.add_argument('--out')
    p.add_argument('--max-attempts', type=int, default=3)
    p.add_argument('--quiet', action='store_true')
    args = p.parse_args()

    if args.html_path:
        html_path = Path(args.html_path)
    else:
        cands = sorted((ROOT / 'output').glob('slides_*.html'),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not cands:
            print('[format] No HTML found in output/')
            sys.exit(1)
        html_path = cands[0]

    out = Path(args.out) if args.out else None
    ok, pptx = run_loop(html_path, out, args.max_attempts, verbose=not args.quiet)
    if not args.quiet:
        print(f"\n[format] Output: {pptx}")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
