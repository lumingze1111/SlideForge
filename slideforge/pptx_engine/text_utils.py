"""text_utils.py — CJK 字符检测。"""
import re

CJK_RE = re.compile(
    "["
    "　-〿"
    "぀-ヿ"
    "㐀-䶿"
    "一-鿿"
    "豈-﫿"
    "＀-￯"
    "]"
)


def is_cjk_text(s: str | None) -> bool:
    return bool(s) and bool(CJK_RE.search(s))
