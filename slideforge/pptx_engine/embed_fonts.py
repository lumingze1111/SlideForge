"""embed_fonts.py — 字体映射配置。

简化版：初始时 FONT_PLAN 为空（不下载 Google Fonts），
字体直接用 CSS font-family 透传系统字体。
后续可通过 font_resolver 填充 FONT_PLAN 支持字体嵌入。
"""

FONT_PLAN: list[dict] = []


def bundled_family_names_lower() -> set[str]:
    s = set()
    for p in FONT_PLAN:
        s.add(p["typeface"].lower())
        for a in p.get("aliases", []):
            s.add(a.lower())
    return s


def cjk_typefaces() -> set[str]:
    return {p["typeface"] for p in FONT_PLAN if p.get("cjk")}


def family_alias_map() -> dict[str, str]:
    m = {}
    for p in FONT_PLAN:
        m[p["typeface"]] = p["typeface"]
        m[p["typeface"].lower()] = p["typeface"]
        for a in p.get("aliases", []):
            m[a] = p["typeface"]
            m[a.lower()] = p["typeface"]
    return m


def weighted_family_map() -> dict[tuple[str, int, bool], str]:
    m: dict[tuple[str, int, bool], str] = {}
    for p in FONT_PLAN:
        css_family = p.get("cssFamily")
        source_weight = p.get("sourceWeight")
        source_italic = bool(p.get("sourceItalic", False))
        if not css_family or source_weight is None:
            continue
        names = [css_family, *p.get("aliases", [])]
        for name in names:
            m[(name.lower(), int(source_weight), source_italic)] = p["typeface"]
    return m


def cjk_for_style(latin_style: str | None) -> str:
    for p in FONT_PLAN:
        if p.get("cjk") and p.get("style") == (latin_style or "sans"):
            return p["typeface"]
    for p in FONT_PLAN:
        if p.get("cjk"):
            return p["typeface"]
    return "Noto Sans SC"


def style_of_typeface(typeface: str) -> str | None:
    for p in FONT_PLAN:
        if p["typeface"] == typeface:
            return p.get("style")
    return None


def chars_from_measurement(meas: dict) -> set[str]:
    chars: set[str] = set()
    slides = meas.get("slides") if "slides" in meas else [meas]
    for s in slides:
        for rec in s.get("records", []):
            for run in rec.get("runs", []) or []:
                t = run.get("text", "") or ""
                chars.update(t)
            txt = rec.get("text", "") or ""
            chars.update(txt)
            chars.update(txt.upper())
            chars.update(txt.lower())
    chars.update(" ·—–-,，。.:：;；()（）/0123456789"
                 "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    return chars


def embed(in_pptx, measurement, out_pptx):
    """Stub — 无字体嵌入。复制文件。"""
    import shutil
    shutil.copyfile(in_pptx, out_pptx)
