"""Tests for Layout Agent module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from slideforge.agents.layout_agent import (
    get_slide_elements,
    _check_layout_core,
    create_layout_agent,
    run_layout_agent,
)


class TestBuildElementList:
    def test_skip_deco_fullscreen(self):
        """Full-screen deco_snapshot should be excluded from elements list."""
        records = [
            {"id": "0", "kind": "deco_snapshot", "rect": {"x": 0, "y": 0, "w": 1920, "h": 1080}},
            {"id": "1", "kind": "text", "rect": {"x": 100, "y": 100, "w": 200, "h": 50},
             "text": "Hello", "tag": "h1", "fontSize": 24},
        ]
        from slideforge.agents.layout_agent import _build_element_list
        elements = _build_element_list(records, 1920, 1080)
        assert len(elements) == 1
        assert elements[0]["id"] == "1"

    def test_rect_format(self):
        """Each element should have id, kind, orig, init fields."""
        records = [
            {"id": "0", "kind": "text", "rect": {"x": 100, "y": 200, "w": 300, "h": 50},
             "text": "Title", "tag": "h1", "fontSize": 24},
        ]
        from slideforge.agents.layout_agent import _build_element_list
        elements = _build_element_list(records, 1920, 1080)
        el = elements[0]
        assert "id" in el
        assert "orig" in el
        assert "init" in el
        # init should be the center-scaled version
        # orig: (100, 200, 300, 50)
        # offset = (1.5-1)/2 = 0.25
        # init_x = 100 - 300*0.25 = 25
        # init_y = 200 - 50*0.25 = 187.5
        # init_w = 300*1.5 = 450
        # init_h = 50*1.5 = 75
        assert el["init"]["x"] == 25
        assert el["init"]["y"] == 187.5
        assert el["init"]["w"] == 450
        assert el["init"]["h"] == 75

    def test_text_truncation(self):
        """Text longer than 40 chars should be truncated in elements."""
        records = [
            {"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 20},
             "text": "A" * 100, "tag": "p", "fontSize": 16},
        ]
        from slideforge.agents.layout_agent import _build_element_list
        elements = _build_element_list(records, 1920, 1080)
        assert len(elements[0]["text"]) <= 42  # 40 + "…"


class TestCheckLayout:
    def test_clean_layout(self):
        """All elements within slide bounds and no overlap -> score 100."""
        adjustments = {
            "0": {"x": 0, "y": 0, "w": 100, "h": 100},
            "1": {"x": 200, "y": 0, "w": 100, "h": 100},
        }
        result = _check_layout_core(adjustments, 1920, 1080)
        assert result["overflow_count"] == 0
        assert result["overlap_count"] == 0
        assert result["score"] == 100

    def test_overflow_detected(self):
        """Element past right edge should count as overflow."""
        adjustments = {
            "0": {"x": 1900, "y": 0, "w": 100, "h": 50},
        }
        result = _check_layout_core(adjustments, 1920, 1080)
        assert result["overflow_count"] == 1
        assert result["score"] == 90

    def test_overlap_detected(self):
        """Two overlapping elements should be detected."""
        adjustments = {
            "0": {"x": 0, "y": 0, "w": 200, "h": 100},
            "1": {"x": 50, "y": 0, "w": 200, "h": 100},
        }
        result = _check_layout_core(adjustments, 1920, 1080)
        assert result["overlap_count"] == 1
        assert result["score"] == 95

    def test_invalid_adjustments_still_checked(self):
        """check_layout should handle elements partly outside slide."""
        adjustments = {
            "0": {"x": -10, "y": 0, "w": 100, "h": 50},
        }
        result = _check_layout_core(adjustments, 1920, 1080)
        assert result["overflow_count"] >= 1


class TestParseAgentResponse:
    def test_parse_valid_json(self):
        from slideforge.agents.layout_agent import _parse_agent_response
        result = _parse_agent_response(
            '{"adjustments": {"0": {"x": 0, "y": 0, "w": 100, "h": 50}}}'
        )
        assert result is not None
        assert "0" in result
        assert result["0"]["x"] == 0.0

    def test_parse_with_code_block(self):
        from slideforge.agents.layout_agent import _parse_agent_response
        result = _parse_agent_response(
            '```json\n{"adjustments": {"0": {"x": 10, "y": 20, "w": 300, "h": 100}}}\n```'
        )
        assert result is not None
        assert result["0"]["x"] == 10.0

    def test_parse_invalid_returns_none(self):
        from slideforge.agents.layout_agent import _parse_agent_response
        assert _parse_agent_response("not json") is None
        assert _parse_agent_response("") is None
        assert _parse_agent_response(None) is None


class TestRunLayoutAgent:
    def test_agent_returns_adjustments(self):
        """run_layout_agent should return a dict mapping id -> (x,y,w,h)."""
        mock_llm = MagicMock()
        mock_agent = MagicMock()

        mock_result = {
            "messages": [
                HumanMessage(content=""),
                MagicMock(content=json.dumps({
                    "adjustments": {
                        "0": {"x": 0, "y": 0, "w": 100, "h": 50},
                        "1": {"x": 150, "y": 0, "w": 200, "h": 100},
                    },
                    "reasoning": "Left justified, no overlap."
                })),
            ]
        }
        mock_agent.invoke.return_value = mock_result

        records = [
            {"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
             "text": "Hello", "tag": "h1", "fontSize": 24},
            {"id": "1", "kind": "shape", "rect": {"x": 100, "y": 0, "w": 200, "h": 100},
             "tag": "div"},
        ]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1)
            assert "0" in result
            assert "1" in result
            assert result["0"] == (0, 0, 100, 50)

    def test_empty_result_fallback(self):
        """Empty adjustments dict should trigger fallback (return empty)."""
        mock_llm = MagicMock()
        mock_agent = MagicMock()

        mock_result = {
            "messages": [MagicMock(content="{}")],
        }
        mock_agent.invoke.return_value = mock_result

        records = [{"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
                     "text": "Hi", "tag": "p", "fontSize": 16}]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1)
            assert result == {}

    def test_exception_fallback(self):
        """LLM exception should return empty dict (fallback)."""
        mock_llm = MagicMock()
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = Exception("API error")

        records = [{"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
                     "text": "Hi", "tag": "p", "fontSize": 16}]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1)
            assert result == {}

    def test_no_improvement_fallback(self):
        """Two rounds with no score improvement should trigger fallback.

        Use 2 overflowing elements (score 80, below the 90 threshold)
        so the loop continues past the 'good enough' check.
        """
        mock_llm = MagicMock()
        mock_agent = MagicMock()

        # 2 elements overflowing → overflow_count=2 → score=100-20=80
        stagnant_resp = {
            "adjustments": {
                "0": {"x": -100, "y": 0, "w": 50, "h": 50},
                "1": {"x": 1900, "y": 0, "w": 100, "h": 50},
            },
        }
        call_results = [
            {"messages": [MagicMock(content=json.dumps(stagnant_resp))]},
            {"messages": [MagicMock(content=json.dumps(stagnant_resp))]},
            {"messages": [MagicMock(content=json.dumps(stagnant_resp))]},
        ]
        call_idx = [0]

        def side_effect(x):
            i = call_idx[0]
            call_idx[0] += 1
            return call_results[i]

        mock_agent.invoke.side_effect = side_effect

        records = [{"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
                     "text": "Hi", "tag": "p", "fontSize": 16},
                   {"id": "1", "kind": "text", "rect": {"x": 100, "y": 0, "w": 100, "h": 50},
                     "text": "Bye", "tag": "p", "fontSize": 16}]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1)
            assert result == {}

    def test_timeout_fallback(self):
        """Response exceeding time limit should return empty."""
        import time
        mock_llm = MagicMock()
        mock_agent = MagicMock()

        real_sleep = time.sleep
        call_count = [0]

        def delayed_invoke(x):
            call_count[0] += 1
            real_sleep(0.05)  # 50ms per call
            # Score 80 (below 90) so the loop continues
            return {"messages": [MagicMock(content=json.dumps({
                "adjustments": {
                    "0": {"x": -100, "y": 0, "w": 50, "h": 50},
                    "1": {"x": 1900, "y": 0, "w": 100, "h": 50},
                },
            }))]}

        mock_agent.invoke.side_effect = delayed_invoke

        records = [{"id": "0", "kind": "text", "rect": {"x": 0, "y": 0, "w": 100, "h": 50},
                     "text": "Hi", "tag": "p", "fontSize": 16},
                   {"id": "1", "kind": "text", "rect": {"x": 100, "y": 0, "w": 100, "h": 50},
                     "text": "Bye", "tag": "p", "fontSize": 16}]

        with patch("slideforge.agents.layout_agent.create_react_agent", return_value=mock_agent):
            result = run_layout_agent(mock_llm, records, slide_index=1, timeout_ms=60)
            # With 60ms timeout and 50ms per call, the second round should time out
            assert result == {}
