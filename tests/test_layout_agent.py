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
    def test_applies_150px_shift_to_all_elements(self):
        """All elements get init.x + 150px, with orig w/h (not init w/h)."""
        records = [
            {"id": "0", "kind": "text", "rect": {"x": 100, "y": 100, "w": 400, "h": 50},
             "text": "Hello", "tag": "h1", "fontSize": 24},
            {"id": "1", "kind": "shape", "rect": {"x": 200, "y": 300, "w": 300, "h": 200},
             "tag": "div"},
        ]
        result = run_layout_agent(None, records, slide_index=2, total_slides=3)
        assert "0" in result
        assert "1" in result
        # init.x = 100 - 400*0.25 = 0, +150 = 150
        # w/h = orig values (not init)
        assert result["0"] == (150.0, 87.5, 400, 50)
        # init.x = 200 - 300*0.25 = 125, +150 = 275
        assert result["1"] == (275.0, 250.0, 300, 200)

    def test_first_page_also_gets_shift(self):
        """First page (slide_index=1) also gets the 150px shift."""
        records = [
            {"id": "0", "kind": "text", "rect": {"x": 100, "y": 100, "w": 400, "h": 50},
             "text": "Hello", "tag": "h1", "fontSize": 24},
        ]
        result = run_layout_agent(None, records, slide_index=1, total_slides=3)
        assert result["0"][0] == 150.0  # init.x=0, +150

    def test_last_page_also_gets_shift(self):
        """Last page also gets the 150px shift."""
        records = [
            {"id": "0", "kind": "text", "rect": {"x": 100, "y": 100, "w": 400, "h": 50},
             "text": "Bye", "tag": "h1", "fontSize": 24},
        ]
        result = run_layout_agent(None, records, slide_index=3, total_slides=3)
        assert result["0"][0] == 150.0

    def test_clamps_to_slide_right_edge(self):
        """Element that would overflow right edge gets clamped."""
        records = [
            {"id": "0", "kind": "text", "rect": {"x": 1800, "y": 100, "w": 400, "h": 50},
             "text": "Right", "tag": "p", "fontSize": 16},
        ]
        result = run_layout_agent(None, records, slide_index=2, total_slides=3)
        x, y, w, h = result["0"]
        # init.x = 1800 - 400*0.25 = 1700, +150 = 1850
        # init.w = 400*1.5 = 600, 1850 + 600 = 2450 > 1920 → clamp to 1920-600=1320
        assert x == 1320.0

    def test_empty_elements_returns_empty(self):
        """Empty elements list (e.g. only fullscreen deco) returns empty dict."""
        records = [
            {"id": "0", "kind": "deco_snapshot", "rect": {"x": 0, "y": 0, "w": 1920, "h": 1080}},
        ]
        result = run_layout_agent(None, records, slide_index=2, total_slides=3)
        assert result == {}
