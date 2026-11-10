import json

from app.db.models import VideoVersion
from app.pipeline.approvals import approve
from app.pipeline.production_ranking import produce_ranking
from app.pipeline.ranking import RankingPlan
from app.pipeline.voice import text_sha256
from tests.test_ranking import plan

RANK_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def test_ranking_voiceover_reaches_owner_and_passes_real_approval(db, tmp_path, monkeypatch):
    payload = plan().model_dump(mode="json")
    payload["post_text"] = "Editorial ranking, not an FPS benchmark. Independent and unsponsored."
    for item in payload["scenes"]:
        item["game"] = f"Game {item['rank']}"
        item["narration"] = f"At number {RANK_WORDS[item['rank']]}, {item['game']} is our editorial pick."
        source = tmp_path / item["source_path"]
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"video")
    payload.pop("voice_dir", None)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    RankingPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))

    voice_dir = tmp_path / "generated-voice"
    voice_dir.mkdir()
    voice_files = []
    for segment_id in ["hook", *[f"rank-{rank:02d}" for rank in range(1, 11)]]:
        path = voice_dir / f"{segment_id}.wav"
        path.write_bytes(b"voice")
        voice_files.append({"segment_id": segment_id, "path": str(path), "text_sha256": text_sha256(segment_id), "sha256": "a" * 64, "duration_seconds": 4, "sample_rate": 24000})
    voice = {"decision": "ALLOW", "reasons": [], "provider": "kokoro", "voice_only": True, "avatar_present": False, "files": voice_files}
    monkeypatch.setattr("app.pipeline.production_ranking.require_tools", lambda: None)
    monkeypatch.setattr("app.pipeline.production_ranking.prepare_voice", lambda *_args, **_kwargs: voice)

    def render(_plan_path, output, _platform, _mobile_style, files):
        assert len(files) == 11
        output.mkdir(parents=True, exist_ok=True)
        (output / "video.mp4").write_bytes(b"rendered-video")
        (output / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:04,000\nTest narration\n", encoding="utf-8")
        (output / "editorial.json").write_text(plan_path.read_text(encoding="utf-8"), encoding="utf-8")
        return {"decision": "ALLOW", "voice_only": True, "avatar_present": False, "technical": {"decision": "ALLOW", "duration_seconds": 12.5}}

    monkeypatch.setattr("app.pipeline.production_ranking.render_ranking", render)
    monkeypatch.setattr("app.pipeline.production_ranking.probe", lambda _path: {"format": {"duration": "12.5"}})

    def thumbnail(_plan_path, output):
        path = output / "thumbnail.jpg"
        path.write_bytes(b"thumbnail")
        return path

    monkeypatch.setattr("app.pipeline.production_ranking.make_thumbnail", thumbnail)
    monkeypatch.setattr("app.pipeline.production_ranking.make_storyboard", lambda _video, output, _duration, landscape=False: (output / "storyboard.jpg").write_bytes(b"storyboard"))
    expected_narration = " ".join([payload["hook"], *[item["narration"] for item in sorted(payload["scenes"], key=lambda row: row["rank"], reverse=True)]])
    monkeypatch.setattr("app.pipeline.production_ranking.transcribe", lambda *_args: {"language_probability": 0.99, "segments_detail": [{"text": expected_narration}]})

    result = produce_ranking(db, plan_path, tmp_path / "output", voice_provider="kokoro")
    assert result["status"] == "AWAITING_OWNER"
    assert result["avatar_present"] is False
    video = db.get(VideoVersion, result["video_id"])
    assert video.features_json["voice_only"] is True
    assert video.features_json["avatar_present"] is False
    checks = json.loads((tmp_path / "output" / "checks.json").read_text(encoding="utf-8"))
    assert checks["voice"]["decision"] == "ALLOW"
    assert checks["claim_control"]["decision"] == "ALLOW"
    assert "avatar" not in checks
    assert not (tmp_path / "output" / "avatar_request.json").exists()
    manifest = json.loads((tmp_path / "output" / "manifest.json").read_text(encoding="utf-8"))
    assert "voice_assets.json" in manifest["files_sha256"]
    assert len(manifest["files_sha256"]) == 10

    review = approve(db, video, "owner", "youtube", "channel-1", True)
    assert review.digest_json["approval_sha256"]
    assert video.status == "APPROVED"
