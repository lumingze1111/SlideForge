from slideforge.pptx_engine.records import (
    build_layout_element,
    is_fullscreen_deco,
    truncate_text,
)


def test_is_fullscreen_deco_matches_existing_layout_behavior():
    assert is_fullscreen_deco(
        {"kind": "deco_snapshot", "rect": {"x": 0, "y": 0, "w": 1920, "h": 1080}}
    )
    assert not is_fullscreen_deco(
        {"kind": "deco_snapshot", "rect": {"x": 10, "y": 10, "w": 400, "h": 300}}
    )


def test_truncate_text_uses_existing_ellipsis_behavior():
    assert truncate_text("短文本", max_len=40) == "短文本"
    assert truncate_text("A" * 45, max_len=40) == "A" * 40 + "…"


def test_build_layout_element_includes_orig_and_init_rects():
    element = build_layout_element(
        {"id": "7", "kind": "text", "tag": "h1", "text": "标题", "fontSize": 24, "rect": {"x": 100, "y": 200, "w": 300, "h": 50}}
    )

    assert element == {
        "id": "7",
        "kind": "text",
        "tag": "h1",
        "text": "标题",
        "fontSize": 24,
        "orig": {"x": 100, "y": 200, "w": 300, "h": 50},
        "init": {"x": 25.0, "y": 187.5, "w": 450.0, "h": 75.0},
    }
