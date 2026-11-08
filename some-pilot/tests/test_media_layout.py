from app.pipeline.media import _font_size, _srt_seconds


def test_font_size_keeps_text_inside_horizontal_safe_area():
    lines = ["DEMO: A practical checklist for", "choosing a gaming handheld"]
    size = _font_size(lines, 64, 900)
    assert max(len(line) for line in lines) * size * 0.62 <= 900


def test_srt_time_conversion():
    assert _srt_seconds("00:01:03,540") == 63.54
