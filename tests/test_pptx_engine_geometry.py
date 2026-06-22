from slideforge.pptx_engine.geometry import (
    PX_TO_EMU,
    SLIDE_H_EMU,
    SLIDE_H_PX,
    SLIDE_W_EMU,
    SLIDE_W_PX,
    center_scaled_rect,
    clamp_rect_to_slide,
)


def test_slide_constants_match_existing_16_9_mapping():
    assert SLIDE_W_PX == 1920
    assert SLIDE_H_PX == 1080
    assert SLIDE_W_EMU == 12192000
    assert SLIDE_H_EMU == 6858000
    assert PX_TO_EMU == 6350


def test_center_scaled_rect_matches_layout_agent_expectation():
    rect = center_scaled_rect(x=100, y=200, w=300, h=50, scale=1.5)

    assert rect == {"x": 25.0, "y": 187.5, "w": 450.0, "h": 75.0}


def test_clamp_rect_to_slide_keeps_rect_inside_bounds():
    rect = clamp_rect_to_slide({"x": 1850, "y": -20, "w": 600, "h": 100})

    assert rect == {"x": 1320.0, "y": 0.0, "w": 600.0, "h": 100.0}
