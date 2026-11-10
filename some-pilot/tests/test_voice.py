import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.pipeline.voice import VoiceSegment, prepare_voice, ranking_voice_segments, text_sha256, voice_file_map


def fake_audio(monkeypatch):
    monkeypatch.setattr("app.pipeline.voice.detect_media_type", lambda _path: "audio/wav")
    monkeypatch.setattr("app.pipeline.voice.probe", lambda _path: {"streams": [{"codec_type": "audio", "sample_rate": "24000", "channels": 1}], "format": {"duration": "4.25"}})


def existing_voice(tmp_path, text="Exact narration.") -> Path:
    directory = tmp_path / "voice"
    directory.mkdir()
    (directory / "hook.wav").write_bytes(b"wav")
    (directory / "metadata.json").write_text(json.dumps({"model": {"model": "Kokoro-82M", "license": "Apache-2.0"}, "voice": [{"file": "hook.wav", "text": text, "voice": "af_bella", "speed": 1.08}]}), encoding="utf-8")
    return directory


def test_existing_kokoro_validates_text_hash_audio_and_provenance(tmp_path, monkeypatch):
    fake_audio(monkeypatch)
    result = prepare_voice([VoiceSegment("hook", "Exact narration.")], "kokoro", tmp_path / "unused", existing_voice(tmp_path))
    assert result["decision"] == "ALLOW"
    assert result["provider"] == "kokoro"
    assert result["voice_only"] is True
    assert result["avatar_present"] is False
    assert result["cost_dkk"] == 0
    assert result["files"][0]["text_sha256"] == text_sha256("Exact narration.")
    assert result["files"][0]["duration_seconds"] == 4.25
    assert result["files"][0]["sample_rate"] == 24000
    assert len(result["files"][0]["sha256"]) == 64
    assert voice_file_map(result) == {"hook": tmp_path / "voice" / "hook.wav"}


def test_existing_kokoro_rejects_changed_script(tmp_path, monkeypatch):
    fake_audio(monkeypatch)
    result = prepare_voice([VoiceSegment("hook", "Changed narration.")], "kokoro", tmp_path / "unused", existing_voice(tmp_path))
    assert result["decision"] == "BLOCK"
    assert "voice_text_mismatch:hook" in result["reasons"]


def test_missing_voice_segment_blocks_before_render(tmp_path):
    directory = existing_voice(tmp_path)
    (directory / "hook.wav").unlink()
    result = prepare_voice([VoiceSegment("hook", "Exact narration.")], "kokoro", tmp_path / "unused", directory)
    assert result["decision"] == "BLOCK"
    assert "voice_segment_missing:hook" in result["reasons"]


def test_new_kokoro_generates_all_segments_without_network(tmp_path, monkeypatch):
    fake_audio(monkeypatch)
    monkeypatch.setattr("app.pipeline.voice._generate_kokoro_file", lambda segment, path, _voice, _speed: path.write_bytes(b"wav"))
    monkeypatch.setattr("app.pipeline.voice.httpx.post", lambda *_args, **_kwargs: pytest.fail("local Kokoro must not call HTTP"))
    result = prepare_voice([VoiceSegment("hook", "Opening."), VoiceSegment("rank-01", "Winner.")], "kokoro", tmp_path / "generated")
    assert result["decision"] == "ALLOW"
    assert len(result["files"]) == 2
    assert result["paid_call"] is False
    assert result["cost_dkk"] == 0


def test_elevenlabs_blocks_paid_calls_and_missing_price_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pipeline.voice.httpx.post", lambda *_args, **_kwargs: pytest.fail("blocked ElevenLabs call reached network"))
    result = prepare_voice([VoiceSegment("hook", "Premium voice.")], "elevenlabs", tmp_path / "generated")
    assert result["decision"] == "BLOCK"
    assert "paid_jobs_disabled" in result["reasons"]
    assert "elevenlabs_api_key_missing" in result["reasons"]
    assert "elevenlabs_verified_unit_price_required" in result["reasons"]
    assert "elevenlabs_voice_rights_confirmation_required" in result["reasons"]
    assert result["actual_cost_dkk"] is None


def test_elevenlabs_adapter_converts_pcm_and_records_cost(tmp_path, monkeypatch):
    fake_audio(monkeypatch)
    settings = get_settings()
    for name, value in {
        "paid_jobs_enabled": True,
        "elevenlabs_api_key": "test-secret",
        "elevenlabs_voice_id": "voice-1",
        "elevenlabs_model_id": "eleven_multilingual_v2",
        "elevenlabs_voice_rights_confirmed": True,
        "elevenlabs_cost_per_1000_chars_dkk": 0.1,
        "elevenlabs_pricing_verified_at": "2026-11-10",
        "max_job_ai_cost_dkk": 5,
    }.items():
        monkeypatch.setattr(settings, name, value)
    calls = []

    class Response:
        content = b"pcm"
        headers = {"x-request-id": "request-1"}

        def raise_for_status(self):
            return None

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr("app.pipeline.voice.httpx.post", post)
    monkeypatch.setattr("app.pipeline.voice.run", lambda args: Path(args[-1]).write_bytes(b"wav"))
    result = prepare_voice([VoiceSegment("hook", "Premium voice.")], "elevenlabs", tmp_path / "generated")
    assert result["decision"] == "ALLOW"
    assert result["paid_call"] is True
    assert result["actual_cost_dkk"] == 0.0014
    assert result["files"][0]["request_id"] == "request-1"
    assert calls[0][1]["params"] == {"output_format": "pcm_24000"}


def test_ranking_voice_segments_cover_hook_and_all_games_in_render_order():
    from app.pipeline.ranking import RankingPlan
    from tests.test_ranking import plan
    segments = ranking_voice_segments(plan())
    assert len(segments) == 11
    assert segments[0].segment_id == "hook"
    assert segments[1].segment_id == "rank-10"
    assert segments[-1].segment_id == "rank-01"


def test_cli_uses_voice_provider_without_avatar_arguments():
    from app.cli import build_parser
    args = build_parser().parse_args(["ranking", "--plan", "plan.json", "--output", "out", "--voice-provider", "kokoro"])
    assert args.voice_provider == "kokoro"
    assert not hasattr(args, "avatar_dir")
    assert "avatar-request" not in build_parser().format_help()


def test_doctor_reports_voice_provider_without_secrets(db):
    from app.cli import doctor
    result = doctor(db)
    assert result["integrations"]["voice"]["provider"] == "kokoro"
    assert result["integrations"]["voice"]["local_available"] is True
    assert result["integrations"]["voice"]["avatar_required"] is False
    assert "api_key" not in result["integrations"]["voice"]
