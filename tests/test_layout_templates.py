from slideforge.agents.layout_templates import TemplateContext, select_layout_template


def test_content_slides_rotate_through_text_templates():
    first = select_layout_template(TemplateContext(slide_type="content", slide_index=1, total_slides=5))
    second = select_layout_template(TemplateContext(slide_type="content", slide_index=2, total_slides=5))
    third = select_layout_template(TemplateContext(slide_type="content", slide_index=3, total_slides=5))

    assert [first.name, second.name, third.name] == [
        "content-classic",
        "content-insight-cards",
        "content-left-rail",
    ]


def test_media_context_prefers_visual_templates():
    image_template = select_layout_template(
        TemplateContext(slide_type="content", slide_index=2, total_slides=5, has_image=True)
    )
    chart_template = select_layout_template(
        TemplateContext(slide_type="data", slide_index=3, total_slides=5, has_chart=True)
    )

    assert image_template.name == "content-right-visual"
    assert chart_template.name == "data-chart-forward"


def test_dense_content_uses_wide_text_template():
    template = select_layout_template(
        TemplateContext(slide_type="content", slide_index=3, total_slides=6, bullet_count=6)
    )

    assert template.name == "content-classic"


def test_unknown_slide_type_falls_back_to_content_default():
    template = select_layout_template(TemplateContext(slide_type="unknown", slide_index=1, total_slides=3))

    assert template.slide_type == "content"
    assert template.name == "content-classic"
