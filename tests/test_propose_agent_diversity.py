from slideforge.agents.propose_agent import (
    _analyze_background,
    _backgrounds_are_similar,
)


def test_analyze_background_parses_shorthand_hex_as_light_warm_solid():
    descriptor = _analyze_background("#fc9")

    assert descriptor.valid is True
    assert descriptor.colors == ((255, 204, 153),)
    assert descriptor.style == "solid"
    assert descriptor.tone == "light"
    assert descriptor.temperature == "warm"


def test_analyze_background_extracts_linear_gradient_colors_and_angle():
    descriptor = _analyze_background(
        "linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)"
    )

    assert descriptor.valid is True
    assert descriptor.style == "linear"
    assert descriptor.angle == 135.0
    assert descriptor.colors == ((15, 32, 39), (32, 58, 67), (44, 83, 100))
    assert descriptor.tone == "dark"
    assert descriptor.temperature == "cool"


def test_background_similarity_detects_near_duplicate_dark_blue_gradients():
    first = _analyze_background("linear-gradient(135deg, #0f2027 0%, #203a43 100%)")
    second = _analyze_background("linear-gradient(140deg, #102331 0%, #24475a 100%)")
    third = _analyze_background("linear-gradient(135deg, #fff7ed 0%, #fb923c 100%)")

    assert _backgrounds_are_similar(first, second) is True
    assert _backgrounds_are_similar(first, third) is False
