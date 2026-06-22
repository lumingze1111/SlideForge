from slideforge.pipeline.artifacts import GenerationArtifacts, sanitize_topic_filename


def test_sanitize_topic_filename_keeps_chinese_and_replaces_spaces():
    assert sanitize_topic_filename("库里 职业 生涯") == "库里_职业_生涯"


def test_sanitize_topic_filename_removes_path_separators():
    assert sanitize_topic_filename("../bad/topic") == "bad_topic"


def test_generation_artifacts_builds_html_and_pptx_paths(tmp_path):
    artifacts = GenerationArtifacts.for_topic(tmp_path, "AI 与 艺术融合：未来趋势")

    assert artifacts.output_dir == tmp_path
    assert artifacts.html_path == tmp_path / "slides_AI_与_艺术融合.html"
    assert artifacts.pptx_path == tmp_path / "slides_AI_与_艺术融合_未来趋势.pptx"
