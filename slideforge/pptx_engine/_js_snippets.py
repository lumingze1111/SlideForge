"""_js_snippets.py — measure.py 与 preflight.py 共享的浏览器端 JS 片段。"""

DECO_HELPERS = r"""
  const isNonTranslateTransform = (transformStr) => {
    if (!transformStr || transformStr === 'none') return false;
    const m = transformStr.match(/^matrix\(([^)]+)\)$/);
    if (m) {
      const v = m[1].split(',').map(parseFloat);
      const [a, b, c, d] = v;
      return Math.abs(b) > 0.001 || Math.abs(c) > 0.001 ||
             Math.abs(a - 1) > 0.001 || Math.abs(d - 1) > 0.001;
    }
    return true;
  };

  const isClippingContainerWithTransformedChildren = (s, el) => {
    const ov = s.overflow, ovx = s.overflowX, ovy = s.overflowY;
    const clipped = ov === 'hidden' || ov === 'clip' ||
                    ovx === 'hidden' || ovx === 'clip' ||
                    ovy === 'hidden' || ovy === 'clip';
    if (!clipped || !el.children.length) return false;
    for (const ch of el.children) {
      const cs = getComputedStyle(ch);
      if (isNonTranslateTransform(cs.transform)) return true;
    }
    return false;
  };

  const hasPseudoDecoration = (el, pseudo) => {
    const ps = getComputedStyle(el, pseudo);
    const content = ps.content;
    const hasContent = content && content !== 'none' && content !== 'normal'
                       && content !== '""' && content !== "''";
    if (hasContent) return true;
    if (content === '""' || content === "''") {
      if (ps.backgroundImage && ps.backgroundImage !== 'none') return true;
      const bg = ps.backgroundColor;
      if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return true;
      if (parseFloat(ps.borderTopWidth) > 0 || parseFloat(ps.borderBottomWidth) > 0 ||
          parseFloat(ps.borderLeftWidth) > 0 || parseFloat(ps.borderRightWidth) > 0) return true;
    }
    return false;
  };

  const isZeroCssLength = (value) => {
    if (!value) return true;
    const n = parseFloat(value);
    return Number.isFinite(n) && Math.abs(n) < 0.001;
  };

  const isSimplePseudoLineDecoration = (el, pseudo) => {
    const ps = getComputedStyle(el, pseudo);
    const content = ps.content;
    const emptyContent = content === '""' || content === "''";
    if (!emptyContent) return false;
    if (ps.display === 'none' || ps.visibility === 'hidden') return false;
    if (ps.backgroundImage && ps.backgroundImage !== 'none') return false;
    const bg = ps.backgroundColor;
    if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return false;
    if (ps.boxShadow && ps.boxShadow !== 'none') return false;
    if (ps.filter && ps.filter !== 'none') return false;
    if (ps.mixBlendMode && ps.mixBlendMode !== 'normal') return false;
    if (ps.transform && ps.transform !== 'none') return false;
    if (!isZeroCssLength(ps.borderTopLeftRadius) ||
        !isZeroCssLength(ps.borderTopRightRadius) ||
        !isZeroCssLength(ps.borderBottomRightRadius) ||
        !isZeroCssLength(ps.borderBottomLeftRadius)) return false;
    return parseFloat(ps.borderTopWidth) > 0 || parseFloat(ps.borderBottomWidth) > 0 ||
           parseFloat(ps.borderLeftWidth) > 0 || parseFloat(ps.borderRightWidth) > 0;
  };

  const hasRasterPseudoDecoration = (el, pseudo) =>
    hasPseudoDecoration(el, pseudo) && !isSimplePseudoLineDecoration(el, pseudo);

  const isUnrepresentableTransform = (transformStr) => {
    if (!transformStr || transformStr === 'none') return false;
    const m = transformStr.match(/^matrix\(([^)]+)\)$/);
    if (!m) return true;
    const v = m[1].split(',').map(parseFloat);
    const [a, b, c, d] = v;
    const len1 = a*a + b*b;
    const len2 = c*c + d*d;
    const dot  = a*c + b*d;
    const eps  = 0.005;
    return Math.abs(len1 - 1) > eps || Math.abs(len2 - 1) > eps || Math.abs(dot) > eps;
  };

  const hasNontrivialFilter = (filterStr) => {
    if (!filterStr) return false;
    const t = filterStr.trim();
    return t !== '' && t !== 'none';
  };

  const hasComplexDecoration = (s, el) => {
    if (s.backgroundImage && s.backgroundImage !== 'none') return true;
    if (s.boxShadow && s.boxShadow !== 'none') return true;
    if (s.outlineStyle && s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) return true;
    if (hasRasterPseudoDecoration(el, '::before')) return true;
    if (hasRasterPseudoDecoration(el, '::after')) return true;
    if (isClippingContainerWithTransformedChildren(s, el)) return true;
    if (s.backdropFilter && s.backdropFilter !== 'none') return true;
    if (hasNontrivialFilter(s.filter)) return true;
    if (s.mixBlendMode && s.mixBlendMode !== 'normal') return true;
    if (isUnrepresentableTransform(s.transform)) return true;
    return false;
  };
"""
