from slideforge.agents.html_generator import SlideContent
from slideforge.tools.image_matching import (
    ImageQueryContext,
    build_image_query_context,
    build_image_queries,
)


def test_build_image_query_context_collects_slide_text():
    slide = SlideContent(
        slide_type="content",
        title="三分革命",
        subtitle="改变 NBA 空间打法",
        bullets=["超远距离投篮", "勇士体系", "防守拉伸"],
        key_stat="402",
        key_stat_label="单赛季三分命中数",
    )

    context = build_image_query_context(
        topic="斯蒂芬·库里",
        slide_index=2,
        slide=slide,
        requested_keywords="three point shooting",
    )

    assert context.topic == "斯蒂芬·库里"
    assert context.slide_index == 2
    assert context.slide_title == "三分革命"
    assert "超远距离投篮" in context.slide_text
    assert "402" in context.slide_text
    assert context.requested_keywords == "three point shooting"


def test_build_image_queries_include_topic_title_and_requested_keywords():
    context = ImageQueryContext(
        topic="Stephen Curry",
        slide_index=1,
        slide_type="content",
        slide_title="Three Point Revolution",
        slide_text="Warriors spacing deep shooting NBA defense",
        requested_keywords="three point shooting",
    )

    queries = build_image_queries(context)

    assert queries[0] == "Stephen Curry Three Point Revolution three point shooting"
    assert "Stephen Curry Three Point Revolution" in queries
    assert "Stephen Curry NBA basketball" in queries
    assert len(queries) == len(set(queries))
