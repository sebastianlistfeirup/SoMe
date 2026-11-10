import json

from app.pipeline.voice import VoiceSegment, voice_asset_report
from scripts.build_test_posts import prepare_post_voice


def test_post_builder_creates_voiceover_timings_without_avatar(tmp_path, monkeypatch):
    def prepare(segments, provider, _output, _existing):
        assert provider == "kokoro"
        return {
            "decision": "ALLOW",
            "reasons": [],
            "provider": "kokoro",
            "avatar_present": False,
            "files": [
                {"segment_id": segment.segment_id, "path": str(tmp_path / f"{segment.segment_id}.wav"), "duration_seconds": 2.5 + len(segment.segment_id) / 10, "sample_rate": 24000, "sha256": "a" * 64}
                for segment in segments
            ],
        }

    monkeypatch.setattr("scripts.build_test_posts.prepare_voice", prepare)
    post_dir = tmp_path / "gaming"
    post_dir.mkdir()
    timings, total, directory = prepare_post_voice("gaming", post_dir)
    assert len(timings) == 7
    assert total > 0
    assert directory.name == "voice-assets"
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    assert len(metadata["voice"]) == 7
    assert metadata["model"]["model"] == "Kokoro-82M"
    report = json.loads((post_dir / "voice_assets.json").read_text(encoding="utf-8"))
    assert report["avatar_present"] is False


def test_generic_production_voice_asset_contract(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pipeline.voice.detect_media_type", lambda _path: "audio/wav")
    monkeypatch.setattr("app.pipeline.voice.probe", lambda _path: {"streams": [{"codec_type": "audio", "sample_rate": "24000", "channels": 1}], "format": {"duration": "4.0"}})
    path = tmp_path / "narration.wav"
    path.write_bytes(b"wav")
    result = voice_asset_report(VoiceSegment("full", "Complete narration."), path, "espeak-ng", voice="espeak-ng", reused=False)
    assert result["decision"] == "ALLOW"
    assert result["provider"] == "espeak-ng"
    assert result["avatar_present"] is False
    assert result["files"][0]["duration_seconds"] == 4.0
