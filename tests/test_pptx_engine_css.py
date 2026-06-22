from slideforge.pptx_engine.css import (
    first_font,
    parse_css_alpha,
    parse_rgb,
    parse_rgba,
    parse_text_shadow,
)


def test_parse_rgba_accepts_hex_and_alpha_hex():
    assert parse_rgba("#336699") == (51, 102, 153, 1.0)
    assert parse_rgba("#33669980") == (51, 102, 153, 128 / 255)


def test_parse_rgba_accepts_modern_space_syntax():
    assert parse_rgba("rgb(10 20 30 / 50%)") == (10, 20, 30, 0.5)


def test_parse_css_alpha_defaults_to_one_for_invalid_values():
    assert parse_css_alpha(None) == 1.0
    assert parse_css_alpha("bad") == 1.0
    assert parse_css_alpha("25%") == 0.25


def test_parse_rgb_discards_alpha():
    assert parse_rgb("rgba(1, 2, 3, 0.4)") == (1, 2, 3)


def test_parse_text_shadow_handles_rgb_commas():
    assert parse_text_shadow("rgb(244, 208, 63) 4px 5px 0px") == (
        4.0,
        5.0,
        0.0,
        (244, 208, 63, 1.0),
    )


def test_first_font_skips_generic_family():
    assert first_font("system-ui, Calibri, sans-serif") == "Calibri"
