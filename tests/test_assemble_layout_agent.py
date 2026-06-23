"""Tests for Layout Agent integration in assemble.py."""

from unittest.mock import Mock, patch

import pytest

from slideforge.pptx_engine import assemble as assemble_module
from slideforge.pptx_engine.assemble import _resolve_rect, _scaled_rect, px_to_emu


class TestResolveRect:
    def test_uses_adjusted_rect_when_present(self):
        """_resolve_rect should use _adjusted_rect when available."""
        rec = {
            "rect": {"x": 100, "y": 50, "w": 400, "h": 60},
            "_adjusted_rect": (50, 30, 500, 80),
        }
        x, y, w, h = _resolve_rect(rec)
        # Position: 50*6350 = 317500, 30*6350 = 190500
        # Size: 500*6350*1.5 = 4762500, 80*6350*1.5 = 762000
        assert x == int(50 * 6350)
        assert y == int(30 * 6350)
        assert w == int(500 * 6350 * 1.5)
        assert h == int(80 * 6350 * 1.5)

    def test_falls_back_to_scaled_rect_without_adjusted(self):
        """_resolve_rect should use _scaled_rect when _adjusted_rect is absent."""
        rec = {
            "rect": {"x": 100, "y": 50, "w": 400, "h": 60},
        }
        x, y, w, h = _resolve_rect(rec)
        # Same as _scaled_rect(100, 50, 400, 60)
        # offset = 0.25
        # x = (100 - 400*0.25)*6350 = 0
        # y = (50 - 60*0.25)*6350 = 35*6350 = 222250
        # w = 400*1.5*6350 = 3810000
        # h = 60*1.5*6350 = 571500
        assert x >= 0
        assert y >= 0
        assert w == int(400 * 6350 * 1.5)
        assert h == int(60 * 6350 * 1.5)

    def test_fallback_with_custom_size(self):
        """_resolve_rect should pass fallback_w/fallback_h to _scaled_rect."""
        rec = {
            "rect": {"x": 100, "y": 50, "w": 400, "h": 60},
        }
        x, y, w, h = _resolve_rect(rec, fallback_w=500, fallback_h=80)
        # Same as _scaled_rect(100, 50, 500, 80)
        # offset = 0.25
        # x = (100 - 500*0.25)*6350 = -25*6350 = -158750 → clamped to 0
        # y = (50 - 80*0.25)*6350 = 30*6350 = 190500
        # w = 500*1.5*6350 = 4762500
        # h = 80*1.5*6350 = 762000
        assert y == int(30 * 6350)
        assert w == int(500 * 6350 * 1.5)
        assert h == int(80 * 6350 * 1.5)

    def test_adjusted_rect_clamped_to_slide(self):
        """_adjusted_rect should be clamped to slide bounds."""
        rec = {
            "rect": {"x": 100, "y": 50, "w": 400, "h": 60},
            "_adjusted_rect": (-100, -50, 5000, 8000),
        }
        x, y, w, h = _resolve_rect(rec)
        # Should be clamped to [0, 12192000] × [0, 6858000]
        SLIDE_W_EMU = 12192000
        SLIDE_H_EMU = 6858000
        assert x >= 0
        assert y >= 0
        assert w <= SLIDE_W_EMU
        assert h <= SLIDE_H_EMU

    def test_ignores_adjusted_rect_on_text_with_custom_size(self):
        """When adjusted_rect is present, custom fallback size is ignored."""
        rec = {
            "rect": {"x": 100, "y": 50, "w": 400, "h": 60},
            "_adjusted_rect": (50, 30, 500, 80),
        }
        x, y, w, h = _resolve_rect(rec, fallback_w=999, fallback_h=999)
        # Should use adjusted_rect, NOT the fallback
        assert w == int(500 * 6350 * 1.5)
        assert h == int(80 * 6350 * 1.5)


def test_screenshot_mode_does_not_overlay_visible_text(monkeypatch):
    slide = Mock()
    data = {
        "slide": {
            "screenshot": "/tmp/slide.png",
            "background": "rgb(0, 0, 0)",
            "backgroundImage": "none",
        },
        "records": [
            {
                "kind": "text",
                "rect": {"x": 10, "y": 20, "w": 300, "h": 80},
                "text": "already captured in screenshot",
                "style": {},
                "runs": [],
            }
        ],
    }

    add_background = Mock()
    add_text_box = Mock()
    monkeypatch.setattr(assemble_module, "add_background", add_background)
    monkeypatch.setattr(assemble_module, "add_text_box", add_text_box)
    prepare_text_layouts = Mock()
    monkeypatch.setattr(assemble_module, "_prepare_text_layouts", prepare_text_layouts)

    assemble_module.assemble_slide(slide, data, screenshot_mode=True)

    add_background.assert_called_once()
    prepare_text_layouts.assert_not_called()
    add_text_box.assert_not_called()
