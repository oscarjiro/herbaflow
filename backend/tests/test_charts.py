from app.pipeline import charts

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def test_png_helper_present():
    assert hasattr(charts, "render_venn")
