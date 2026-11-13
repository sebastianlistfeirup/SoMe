import json
import shutil
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from app.config import get_settings
from app.db.models import Topic
from app.pipeline.media import probe, run, write_srt
from app.pipeline.production import produce
from app.pipeline.real_media import PreparedMedia, RealMediaPlan, RealMediaScene, load_media_plan, media_coverage, prepare_media, render_real_media


def scene_payload(kind="real_video", source_path="clip.mp4", effect="static"):
    return {
        "kind": kind,
        "source_type": "synthetic" if kind == "graphic" else "producer",
        "source_path": source_path,
        "context": "Real product footage in context",
        "source_url": "" if kind == "graphic" else "https://publisher.example/video",
        "policy_url": "" if kind == "graphic" else "https://publisher.example/policy",
        "rights_holder": "Publisher",
        "rights_evidence": "Official publisher policy permits edited commercial videos.",
        "effect": effect,
    }


def prepared(scene, path):
    return PreparedMedia(scene=scene, path=path, media_type="video/mp4", source_duration_seconds=10)


def test_duration_weighted_coverage_allows_exactly_eighty_percent(tmp_path):
    plan = RealMediaPlan.model_validate({"scenes": [scene_payload() for _ in range(4)] + [scene_payload("graphic", "")]})
    items = [prepared(scene, tmp_path / str(index)) for index, scene in enumerate(plan.scenes)]
    result = media_coverage(plan, [1, 1, 1, 1, 1], items)
    assert result["decision"] == "ALLOW"
    assert result["real_media_percent"] == 80.0
    assert result["measurement"] == "duration_weighted_not_scene_count"


def test_coverage_blocks_below_eighty_percent_and_plan_cannot_lower_limit(tmp_path):
    with pytest.raises(ValidationError):
        RealMediaPlan.model_validate({"minimum_real_ratio": 0.79, "scenes": [scene_payload()]})
    plan = RealMediaPlan.model_validate({"scenes": [scene_payload() for _ in range(3)] + [scene_payload("graphic", "")]})
    items = [prepared(scene, tmp_path / str(index)) for index, scene in enumerate(plan.scenes)]
    result = media_coverage(plan, [1, 1, 1, 1], items)
    assert result["decision"] == "BLOCK"
    assert result["real_media_percent"] == 75.0


def test_real_media_requires_https_evidence_and_rejects_effects_on_video():
    with pytest.raises(ValidationError, match="https"):
        RealMediaScene.model_validate({**scene_payload(), "policy_url": "http://insecure.example"})
    with pytest.raises(ValidationError, match="video_effects"):
        RealMediaScene.model_validate(scene_payload(effect="zoom_in"))
    with pytest.raises(ValidationError, match="ai_generated_cannot_count_as_real"):
        RealMediaScene.model_validate({**scene_payload(), "ai_generated": True})


def make_media(root: Path):
    image = root / "photo.jpg"
    Image.new("RGB", (1200, 900), (35, 110, 175)).save(image, quality=92)
    video = root / "clip.mp4"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "2", "-pix_fmt", "yuv420p", "-c:v", "libx264", str(video)])
    narration = root / "narration.wav"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000", "-t", "2", "-c:a", "pcm_s16le", str(narration)])
    return image, video, narration


def test_render_real_video_and_animated_photo(tmp_path):
    image, video, narration = make_media(tmp_path)
    image_scene = RealMediaScene.model_validate(scene_payload("real_image", "photo.jpg", "zoom_in"))
    video_scene = RealMediaScene.model_validate(scene_payload())
    items = [
        PreparedMedia(scene=image_scene, path=image, media_type="image/jpeg", source_duration_seconds=0),
        PreparedMedia(scene=video_scene, path=video, media_type="video/mp4", source_duration_seconds=2),
    ]
    captions = tmp_path / "captions.srt"
    write_srt([{"start": 0, "end": 1, "text": "Real photo with motion"}, {"start": 1, "end": 2, "text": "Real producer video"}], captions)
    coverage = {"decision": "ALLOW", "real_media_ratio": 1.0, "real_media_percent": 100.0}
    output = tmp_path / "real.mp4"
    layout = render_real_media(items, narration, captions, "Real media test", output, coverage)
    metadata = probe(output)
    visual = next(stream for stream in metadata["streams"] if stream["codec_type"] == "video")
    assert output.stat().st_size > 10_000
    assert (visual["width"], visual["height"]) == (1080, 1920)
    assert layout["real_media_percent"] == 100.0
    assert layout["image_effects"] == ["zoom_in"]
    assert layout["synthetic_slide_fallback"] is False


def test_prepare_media_blocks_parent_path_and_type_mismatch(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"scenes": [scene_payload(source_path="../outside.mp4")]}))
    with pytest.raises(ValueError, match="outside_plan_directory"):
        prepare_media(load_media_plan(plan_path), plan_path, tmp_path)
    image, _video, _narration = make_media(tmp_path)
    plan_path.write_text(json.dumps({"scenes": [scene_payload(source_path="photo.jpg")]}))
    with pytest.raises(ValueError, match="real_video_signature_mismatch"):
        prepare_media(load_media_plan(plan_path), plan_path, tmp_path)
    assert image.exists()


def test_produce_end_to_end_with_real_media(db, tmp_path, monkeypatch):
    image, video, narration = make_media(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"platform": "youtube", "scenes": [scene_payload("real_image", "photo.jpg", "zoom_in"), scene_payload()]}))
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    topic = Topic(niche="handheld_gaming", language="en", title="Real media production")
    db.add(topic)
    db.commit()
    def fake_voice(_segments, provider, output_dir, **_kwargs):
        output_dir.mkdir(parents=True)
        generated = output_dir / "full.wav"
        shutil.copyfile(narration, generated)
        return {"decision": "ALLOW", "reasons": [], "provider": provider, "files": [{"segment_id": "full", "path": str(generated), "voice": "test-voice", "duration_seconds": 2}]}

    monkeypatch.setattr("app.pipeline.production.prepare_voice", fake_voice)
    monkeypatch.setattr("app.pipeline.production.concat_with_idents", lambda content, target, **_kwargs: shutil.copyfile(content, target))
    from app.pipeline.ai import demo_draft
    narration_text = demo_draft(topic).narration
    words = narration_text.split()
    midpoint = len(words) // 2
    texts = [" ".join(words[:midpoint]), " ".join(words[midpoint:])]

    def fake_transcribe(_audio, captions):
        segments = [{"start": 0, "end": 1, "text": texts[0]}, {"start": 1, "end": 2, "text": texts[1]}]
        write_srt(segments, captions)
        return {"language": "en", "language_probability": 0.99, "segments": 2, "model": "mock", "segments_detail": segments}

    monkeypatch.setattr("app.pipeline.production.transcribe", fake_transcribe)
    result = produce(db, topic.id, True, plan_path)
    output = Path(result.output_dir)
    composition = json.loads((output / "media_composition.json").read_text())
    manifest = json.loads((output / "manifest.json").read_text())
    assert result.status == "AWAITING_OWNER"
    assert composition["real_media_percent"] == 100.0
    assert composition["real_video_scenes"] == 1
    assert composition["real_image_scenes"] == 1
    assert len(manifest["files_sha256"]) == 13
    assert "narration.wav" in manifest["files_sha256"]
    assert "script.json" in manifest["files_sha256"]
    assert manifest["real_media_ratio"] == 1.0
    assert result.features_json["real_media_required"] is True
    assert Path(result.video_path).stat().st_size > 10_000


def test_live_production_uses_ai_elevenlabs_voice_and_records_cost(db, tmp_path, monkeypatch):
    from app.db.models import Cost
    from app.pipeline.ai import ControlResult, demo_draft

    _image, _video, narration = make_media(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"platform": "youtube", "scenes": [scene_payload("real_image", "photo.jpg", "zoom_in"), scene_payload()]}))
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    topic = Topic(niche="ai", language="en", title="AI production")
    db.add(topic)
    db.commit()
    monkeypatch.setattr("app.pipeline.production.packet_draft", lambda *_args: demo_draft(topic))
    monkeypatch.setattr("app.pipeline.production.packet_excerpts", lambda _packet: [])
    monkeypatch.setattr("app.pipeline.production.review_draft", lambda *_args: ControlResult(decision="ALLOW"))
    monkeypatch.setattr("app.pipeline.production.current_prompt_version", lambda _db: "test-prompt")
    (tmp_path / "editorial-packet.json").write_text('{"lane":"ai"}')
    monkeypatch.setattr("app.pipeline.production.evaluate_editorial_packet", lambda *_args: {"decision": "ALLOW", "blockers": [], "score": 100, "source_valid_until": None})
    monkeypatch.setattr("app.pipeline.production.independent_quality_review", lambda *_args: {"decision": "ALLOW", "score": 92, "threshold": 85, "blind": True})
    selected = {}

    def fake_voice(_segments, provider, output_dir, **kwargs):
        selected.update({"provider": provider, **kwargs})
        output_dir.mkdir(parents=True)
        generated = output_dir / "full.wav"
        shutil.copyfile(narration, generated)
        alignment = output_dir / "full.alignment.json"
        normalized = output_dir / "full.alignment.normalized.json"
        alignment.write_text("{}")
        normalized.write_text("{}")
        return {
            "decision": "ALLOW",
            "reasons": [],
            "provider": provider,
            "estimated_cost_dkk": 0.1,
            "actual_cost_dkk": 0.1,
            "files": [{"segment_id": "full", "path": str(generated), "voice": kwargs["voice_id"], "alignment_path": str(alignment), "normalized_alignment_path": str(normalized), "duration_seconds": 2}],
        }

    monkeypatch.setattr("app.pipeline.production.prepare_voice", fake_voice)
    monkeypatch.setattr("app.pipeline.production.concat_with_idents", lambda content, target, **_kwargs: shutil.copyfile(content, target))
    draft = demo_draft(topic)
    words = draft.narration.split()
    midpoint = len(words) // 2
    segments = [{"start": 0, "end": 1, "text": " ".join(words[:midpoint])}, {"start": 1, "end": 2, "text": " ".join(words[midpoint:])}]

    def alignment(_segment, _path, output):
        write_srt(segments, output)
        return segments

    monkeypatch.setattr("app.pipeline.production.write_alignment_srt", alignment)

    def transcribe(_audio, output):
        write_srt(segments, output)
        return {"language": "en", "language_probability": 0.99, "segments": 2, "model": "mock", "segments_detail": segments}

    monkeypatch.setattr("app.pipeline.production.transcribe", transcribe)
    result = produce(db, topic.id, False, plan_path)
    assert selected == {"provider": "elevenlabs", "voice_id": "8CjmkufHc22WbMZEBHbm"}
    assert result.features_json["voice"] == "elevenlabs"
    assert result.features_json["voice_lane"] == "ai"
    assert db.query(Cost).filter_by(kind="ELEVENLABS", actual_amount=0.1).count() == 1
    manifest = json.loads((Path(result.output_dir) / "manifest.json").read_text())
    assert {"narration.wav", "alignment.json", "alignment.normalized.json", "transcription.srt", "script.json"} <= set(manifest["files_sha256"])
