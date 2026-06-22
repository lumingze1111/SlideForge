from slideforge.agents.propose_agent import (
    ColorProposal,
    DesignProposals,
    SYSTEM_PROMPT,
    _analyze_background,
    _backgrounds_are_similar,
    diversify_color_proposals,
    run_propose_agent,
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


def _proposal(name: str, background: str, visual_style: str = "minimalist") -> ColorProposal:
    return ColorProposal(
        name=name,
        colors={
            "gradient_bg": background,
            "primary": "#38bdf8",
            "accent": "#f97316",
            "text_primary": "#ffffff",
        },
        visual_style=visual_style,
        reasoning=f"{name} reasoning",
    )


def test_diversify_color_proposals_filters_similar_backgrounds_and_keeps_choices():
    raw = DesignProposals(
        proposals=[
            _proposal("dark blue one", "linear-gradient(135deg, #0f2027 0%, #203a43 100%)"),
            _proposal("dark blue duplicate", "linear-gradient(140deg, #102331 0%, #24475a 100%)"),
            _proposal("warm light", "linear-gradient(135deg, #fff7ed 0%, #fb923c 100%)"),
            _proposal("green radial", "radial-gradient(circle, #064e3b 0%, #22c55e 100%)"),
        ],
        recommended_index=0,
    )

    result = diversify_color_proposals(raw)

    assert [proposal.name for proposal in result.proposals] == [
        "dark blue one",
        "warm light",
        "green radial",
    ]
    assert result.recommended_index == 0


def test_diversify_color_proposals_prioritizes_coverage_after_recommended_choice():
    raw = DesignProposals(
        proposals=[
            _proposal("another dark cool", "linear-gradient(90deg, #111827 0%, #1e3a8a 100%)"),
            _proposal("recommended warm", "linear-gradient(135deg, #fff7ed 0%, #fb923c 100%)"),
            _proposal("light neutral", "#f8fafc"),
            _proposal("deep green radial", "radial-gradient(circle, #064e3b 0%, #16a34a 100%)"),
        ],
        recommended_index=1,
    )

    result = diversify_color_proposals(raw)

    assert result.proposals[0].name == "recommended warm"
    assert result.recommended_index == 0
    assert result.proposals[1].name in {"another dark cool", "deep green radial"}
    assert {proposal.name for proposal in result.proposals} == {
        "recommended warm",
        "another dark cool",
        "light neutral",
        "deep green radial",
    }


def test_diversify_color_proposals_preserves_short_or_invalid_sets():
    raw = DesignProposals(
        proposals=[
            _proposal("invalid one", "brand-color(primary)"),
            _proposal("invalid two", "not-a-css-color"),
        ],
        recommended_index=4,
    )

    result = diversify_color_proposals(raw)

    assert [proposal.name for proposal in result.proposals] == ["invalid one", "invalid two"]
    assert result.recommended_index == 0


def test_prompt_requires_distinct_metaphor_lanes():
    assert "视觉隐喻" in SYSTEM_PROMPT
    assert "品牌身份" in SYSTEM_PROMPT
    assert "环境场景" in SYSTEM_PROMPT
    assert "数据/科技" in SYSTEM_PROMPT
    assert "人物情绪" in SYSTEM_PROMPT


class _StructuredLLM:
    def __init__(self, response):
        self.response = response

    def invoke(self, prompt):
        return self.response


class _FakeLLM:
    def __init__(self, response):
        self.response = response

    def with_structured_output(self, schema):
        return _StructuredLLM(self.response)


def test_run_propose_agent_diversifies_structured_output():
    raw = DesignProposals(
        proposals=[
            _proposal("dark blue one", "linear-gradient(135deg, #0f2027 0%, #203a43 100%)"),
            _proposal("dark blue duplicate", "linear-gradient(140deg, #102331 0%, #24475a 100%)"),
            _proposal("warm light", "linear-gradient(135deg, #fff7ed 0%, #fb923c 100%)"),
            _proposal("green radial", "radial-gradient(circle, #064e3b 0%, #22c55e 100%)"),
        ],
        recommended_index=0,
    )

    result = run_propose_agent(_FakeLLM(raw), topic="Demo")

    assert [proposal.name for proposal in result.proposals] == [
        "dark blue one",
        "warm light",
        "green radial",
    ]
