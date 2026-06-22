from pathlib import Path

from slideforge.agents.html_generator import (
    PresentationOutline,
    SlideContent,
    generate_slides_html,
    generate_slides_html_with_images,
)


COLORS = {
    "background": "#0f172a",
    "primary": "#38bdf8",
    "accent": "#f59e0b",
    "text_primary": "#ffffff",
    "text_secondary": "#cbd5e1",
    "surface": "#1e293b",
    "border": "#475569",
}


def test_generate_slides_html_uses_multiple_content_templates(tmp_path):
    outline = PresentationOutline(
        total_pages=3,
        slides=[
            SlideContent(slide_type="content", title="One", bullets=["A", "B"]),
            SlideContent(slide_type="content", title="Two", bullets=["A", "B"]),
            SlideContent(slide_type="content", title="Three", bullets=["A", "B"]),
        ],
    )

    path = generate_slides_html(outline, COLORS, output_path=str(tmp_path / "slides.html"))
    html = Path(path).read_text(encoding="utf-8")

    assert 'data-layout-template="content-classic"' in html
    assert 'data-layout-template="content-insight-cards"' in html
    assert 'data-layout-template="content-left-rail"' in html
    assert html.count("data-pptx-slide") == 3


def test_dense_content_keeps_classic_template(tmp_path):
    outline = PresentationOutline(
        total_pages=1,
        slides=[
            SlideContent(slide_type="content", title="Dense", bullets=["A", "B", "C", "D", "E", "F"]),
        ],
    )

    path = generate_slides_html(outline, COLORS, output_path=str(tmp_path / "slides.html"))
    html = Path(path).read_text(encoding="utf-8")

    assert 'data-layout-template="content-classic"' in html
    assert 'data-layout-template="content-insight-cards"' not in html


def test_generate_slides_html_with_media_uses_media_templates(tmp_path):
    class ImageSuggestion:
        slide_index = 0
        image_url = str(tmp_path / "missing.jpg")
        position = "right"
        description = "missing image"

    class ChartSuggestion:
        slide_index = 1
        layout = "fullpage"

    outline = PresentationOutline(
        total_pages=2,
        slides=[
            SlideContent(slide_type="content", title="Visual", bullets=["A", "B"]),
            SlideContent(slide_type="data", title="Data", key_stat="42%", key_stat_label="Signal", bullets=["A"]),
        ],
    )

    path = generate_slides_html_with_images(
        outline,
        COLORS,
        image_suggestions=[ImageSuggestion()],
        chart_suggestions=[ChartSuggestion()],
        output_path=str(tmp_path / "slides.html"),
    )
    html = Path(path).read_text(encoding="utf-8")

    assert 'data-layout-template="content-right-visual"' in html
    assert 'data-layout-template="data-chart-forward"' in html
    assert html.count("data-pptx-slide") == 2
