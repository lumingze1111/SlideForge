from tools.llm_direct_convert import SYSTEM_PROMPT


def test_llm_direct_prompt_avoids_unsupported_gradient_stop_api():
    assert "gradient_stops.add()" not in SYSTEM_PROMPT
    assert ".gradient_stops.add()" not in SYSTEM_PROMPT
