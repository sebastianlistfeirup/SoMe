from pathlib import Path

import pytest

from app.pipeline.downloader import UnsafeDownload, detect_media_type, validate_public_url


@pytest.mark.parametrize("url", ["http://example.com/file.mp4", "https://127.0.0.1/video.mp4", "https://localhost/video.mp4", "https://169.254.169.254/latest/meta-data", "https://user:pass@example.com/video.mp4"])
def test_unsafe_urls_blocked(url):
    with pytest.raises(UnsafeDownload):
        validate_public_url(url)


def test_file_signatures(tmp_path):
    jpeg = tmp_path / "image.jpg"
    jpeg.write_bytes(b"\xff\xd8\xff" + b"0" * 20)
    assert detect_media_type(jpeg) == "image/jpeg"
    bad = tmp_path / "fake.mp4"
    bad.write_bytes(b"<html>not video</html>")
    with pytest.raises(UnsafeDownload):
        detect_media_type(bad)
