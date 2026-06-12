#!/usr/bin/env python3
"""structural_diff.py — compare measurement.json records against generated PPTX shapes.

For each slide, tries to greedy-match each record to a shape by position/size,
then reports records with no match (lost in translation) and shapes with no
backing record (spurious additions).

Usage:
    python tools/structural_diff.py <measurement.json> <out.pptx>
"""

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NSP = "http://schemas.openxmlformats.org/presentationml/2006/main"
NSA = "http://schemas.openxmlformats.org/drawingml/2006/main"

PX_TO_EMU = 6350
EMU_TO_PX = 1.0 / PX_TO_EMU
SIZE_SCALE = 1.5
EMU_SIZE_TO_PX = 1.0 / (PX_TO_EMU * SIZE_SCALE)
CENTER_OFFSET = (SIZE_SCALE - 1.0) / 2.0  # 0.25


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
            spTree = root.find(f'{{{NSP}}}cSld').find(f'{{{NSP}}}spTree')
            shapes = []
            for sp in spTree:
                tag = etree.QName(sp).localname
                if tag in ('nvGrpSpPr', 'grpSpPr'):
                    continue
                shapes.append(_shape_summary(sp, tag))
            out.append(shapes)
    return out


def _shape_summary(sp, tag) -> dict:
    from lxml import etree
    spPr = sp.find(f'{{{NSP}}}spPr') or sp.find(f'{{{NSP}}}grpSpPr')
    info = {'tag': tag, 'x': 0, 'y': 0, 'w': 0, 'h': 0,
            'fill': None, 'gradient': False, 'text': '', 'shape': None,
            'has_image': tag == 'pic'}
    if spPr is None:
        return info
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
            info['fill'] = srgb.get('val')
    txBody = sp.find(f'{{{NSP}}}txBody')
    if txBody is not None:
        info['text'] = ''.join(t.text or '' for t in txBody.iter(f'{{{NSA}}}t'))
    return info


def diff_slide(records: list[dict], shapes: list[dict], slide_idx: int,
               pos_tol: float = 5.0, size_tol: float = 5.0) -> dict:
    """Greedy match each record to a shape; report unmatched on both sides."""
    used = set()
    pairings = []
    unmatched_records = []

    for ri, r in enumerate(records):
        rect = r.get('rect', {})
        rx, ry = rect.get('x', 0), rect.get('y', 0)
        rw, rh = rect.get('w', 0), rect.get('h', 0)
        kind = r.get('kind', '')
        rtext = (r.get('text') or '').strip()

        # Special case: deco_snapshot covering full slide is replaced by native
        # gradient — match it to the slide-sized gradient rect if present
        if kind == 'deco_snapshot' and rw >= 1900 and rh >= 1060:
            for si, s in enumerate(shapes):
                if si in used:
                    continue
                if s.get('gradient') and s['w'] >= 1900 and s['h'] >= 1060:
                    used.add(si)
                    pairings.append((ri, si, 'deco_snapshot→gradient_bg'))
                    break
            else:
                unmatched_records.append((ri, r, 'deco_snapshot not realized'))
            continue

        best = None
        best_score = float('inf')
        for si, s in enumerate(shapes):
            if si in used:
                continue
            # Position distance
            dx = abs(s['x'] - rx)
            dy = abs(s['y'] - ry)
            dw = abs(s['w'] - rw)
            dh = abs(s['h'] - rh)
            # For text, require text similarity bonus
            if kind == 'text' and rtext:
                stext = (s.get('text') or '').strip()
                text_match = rtext[:20] == stext[:20] or rtext in stext or stext in rtext
                if not text_match:
                    continue
            score = dx + dy + dw + dh
            if score < best_score:
                best_score = score
                best = si
        if best is not None and best_score < (pos_tol + size_tol) * 4:
            used.add(best)
            pairings.append((ri, best, f'{kind}→{shapes[best]["tag"]}'))
        else:
            unmatched_records.append((ri, r, 'no shape match'))

    spurious = [(si, s) for si, s in enumerate(shapes) if si not in used]

    return {
        'slide': slide_idx,
        'records': len(records),
        'shapes': len(shapes),
        'matched': len(pairings),
        'unmatched_records': unmatched_records,
        'spurious_shapes': spurious,
    }


def fmt_record(r: dict) -> str:
    rect = r.get('rect', {})
    snippet = ''
    if r.get('kind') == 'text' and r.get('text'):
        snippet = ' text=' + repr(r['text'][:30])
    return (f"kind={r.get('kind','')} tag={r.get('tag','')} "
            f"pos=({rect.get('x',0):.0f},{rect.get('y',0):.0f}) "
            f"size=({rect.get('w',0):.0f}x{rect.get('h',0):.0f}){snippet}")


def fmt_shape(s: dict) -> str:
    snippet = ''
    if s.get('text'):
        snippet = ' text=' + repr(s['text'][:30])
    return (f"tag={s['tag']} shape={s.get('shape','-')} "
            f"pos=({s['x']:.0f},{s['y']:.0f}) "
            f"size=({s['w']:.0f}x{s['h']:.0f}){snippet}")


def main():
    if len(sys.argv) < 3:
        print("Usage: structural_diff.py <measurement.json> <out.pptx>")
        sys.exit(2)
    meas_path = Path(sys.argv[1])
    pptx_path = Path(sys.argv[2])

    data = json.loads(meas_path.read_text())
    slides_meas = data.get('slides') or [data]
    slides_pptx = load_pptx_shapes(pptx_path)

    if len(slides_meas) != len(slides_pptx):
        print(f"[diff] slide count mismatch: meas={len(slides_meas)} pptx={len(slides_pptx)}")

    total_records = 0
    total_unmatched = 0
    total_spurious = 0
    for i, (m, p) in enumerate(zip(slides_meas, slides_pptx), start=1):
        records = m.get('records', [])
        result = diff_slide(records, p, i)
        total_records += result['records']
        total_unmatched += len(result['unmatched_records'])
        total_spurious += len(result['spurious_shapes'])

        if not result['unmatched_records'] and not result['spurious_shapes']:
            print(f"slide {i}: ✓ {result['matched']}/{result['records']} matched")
            continue
        print(f"\nslide {i}: {result['matched']}/{result['records']} matched, "
              f"{len(result['unmatched_records'])} unmatched record(s), "
              f"{len(result['spurious_shapes'])} spurious shape(s)")
        for ri, r, why in result['unmatched_records']:
            print(f"  - LOST [{ri}]: {fmt_record(r)} ({why})")
        for si, s in result['spurious_shapes']:
            print(f"  + EXTRA [{si}]: {fmt_shape(s)}")

    print(f"\nTotal: {total_records} records, "
          f"{total_records - total_unmatched} matched, "
          f"{total_unmatched} unmatched, {total_spurious} spurious shapes")


if __name__ == '__main__':
    main()
