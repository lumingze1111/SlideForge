import zipfile
from pathlib import Path

from slideforge.pptx_converter import convert_html_to_pptx


def test_convert_simple_html_to_pptx_smoke(tmp_path):
    html = Path("tests/fixtures/simple_slides.html")
    output = tmp_path / "simple.pptx"

    convert_html_to_pptx(
        str(html),
        str(output),
        verbose=False,
        validate_gradients=False,
        audit=False,
    )

    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "ppt/slides/slide1.xml" in names
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "Smoke Test" in slide_xml
