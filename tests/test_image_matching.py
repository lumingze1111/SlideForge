from unittest.mock import Mock

from slideforge.agents.html_generator import SlideContent
from slideforge.tools.image_search import ImageResult, ImageSource
from slideforge.tools.image_matching import (
    ImageQueryContext,
    build_image_query_context,
    build_image_queries,
    choose_best_image,
    search_best_image,
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


def _image(description, width=1920, height=1080):
    return ImageResult(
        url=f"https://example.com/{description.replace(' ', '-')}.jpg",
        description=description,
        author="Test",
        source=ImageSource.UNSPLASH,
        width=width,
        height=height,
        download_url=f"https://example.com/{description.replace(' ', '-')}-raw.jpg",
    )


def test_choose_best_image_prefers_slide_relevant_basketball_candidate():
    context = ImageQueryContext(
        topic="Stephen Curry",
        slide_index=2,
        slide_type="content",
        slide_title="Three Point Revolution",
        slide_text="NBA Warriors basketball shooting deep threes",
        requested_keywords="three point shooting",
    )
    candidates = [
        _image("Office desk with marketing documents"),
        _image("Soccer player celebrating a goal"),
        _image("Basketball player shooting a three point shot in NBA arena"),
        _image("Traditional architecture at sunset"),
    ]

    selected = choose_best_image(context, candidates)

    assert selected is not None
    assert selected.description == "Basketball player shooting a three point shot in NBA arena"


def test_choose_best_image_rejects_unrelated_candidates():
    context = ImageQueryContext(
        topic="Stephen Curry",
        slide_index=2,
        slide_type="content",
        slide_title="Three Point Revolution",
        slide_text="NBA Warriors basketball shooting deep threes",
        requested_keywords="three point shooting",
    )
    candidates = [
        _image("Office desk with laptop"),
        _image("Traditional architecture at sunset"),
        _image("Wedding flowers on a table"),
    ]

    selected = choose_best_image(context, candidates)

    assert selected is None


def test_choose_best_image_prefers_landscape_when_relevance_is_close():
    context = ImageQueryContext(
        topic="NBA",
        slide_index=1,
        slide_type="cover",
        slide_title="Global Basketball Business",
        slide_text="NBA basketball league arena fans",
        requested_keywords="basketball arena",
    )
    portrait = _image("Basketball arena fans", width=900, height=1400)
    landscape = _image("Basketball arena fans", width=1920, height=1080)

    selected = choose_best_image(context, [portrait, landscape])

    assert selected is landscape


def test_search_best_image_queries_multiple_candidates_and_downloads_only_selected(tmp_path):
    context = ImageQueryContext(
        topic="Stephen Curry",
        slide_index=2,
        slide_type="content",
        slide_title="Three Point Revolution",
        slide_text="NBA Warriors basketball shooting deep threes",
        requested_keywords="three point shooting",
    )
    unrelated = _image("Office desk with laptop")
    selected = _image("Basketball player shooting a three point shot in NBA arena")
    image_tool = Mock()
    image_tool.search.side_effect = [
        [unrelated, selected],
    ]
    image_tool.download_image.return_value = str(tmp_path / "image.jpg")

    result = search_best_image(
        image_tool=image_tool,
        context=context,
        output_dir=tmp_path,
        preferred_source=ImageSource.UNSPLASH,
    )

    assert result is not None
    assert result.image is selected
    assert result.image_path.name.startswith("image_")
    image_tool.search.assert_called_once()
    assert image_tool.search.call_args.kwargs["limit"] == 6
    assert image_tool.search.call_args.kwargs["orientation"] == "landscape"
    image_tool.download_image.assert_called_once_with(selected, str(result.image_path))
