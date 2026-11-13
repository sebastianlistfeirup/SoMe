import pytest

from app.config import get_settings
from app.pipeline.brand_ident import concat_with_idents, ident_metadata
from app.pipeline.media import probe, run


def test_ident_metadata_tracks_approved_version_and_formats():
    vertical = ident_metadata(False)
    landscape = ident_metadata(True)
    assert vertical["approved_version"] == "original-collision-v1"
    assert vertical["intro_seconds"] == 3.5
    assert vertical["outro_seconds"] == 3.5
    assert vertical["format"] == "9:16"
    assert landscape["format"] == "16:9"
    assert vertical["subtitle_intro"] == "GAMING CULTURE  ×  AI"
    assert vertical["subtitle_outro"] == "FOLLOW FOR MORE"


@pytest.mark.parametrize("landscape,expected", [(False, (1080, 1920)), (True, (1920, 1080))])
def test_approved_idents_concat_with_real_video_in_every_format(tmp_path, monkeypatch, landscape, expected):
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    content = tmp_path / "content.mp4"
    target = tmp_path / "final.mp4"
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc2=size={expected[0]}x{expected[1]}:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(content),
    ])
    result = concat_with_idents(content, target, landscape=landscape)
    metadata = probe(result)
    video = next(stream for stream in metadata["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in metadata["streams"] if stream["codec_type"] == "audio")
    assert (video["width"], video["height"]) == expected
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"
    assert video["r_frame_rate"] == "30/1"
    assert int(video["nb_frames"]) == 240
    assert audio["codec_name"] == "aac"
    assert int(audio["sample_rate"]) == 48000
    assert audio["channels"] == 2
    assert 7.9 <= float(metadata["format"]["duration"]) <= 8.1
    assert result.stat().st_size > 100_000
