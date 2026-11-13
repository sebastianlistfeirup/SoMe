import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import get_settings
from app.db.models import Topic
from app.pipeline.production import produce
from tests.test_editorial import complete_packet, full_quality
from tests.test_real_media import make_media, scene_payload, write_srt


PARAPHRASE = "Into the Breach squeezes a huge tactical choice into a tiny grid, and that is why strategy fans keep returning to it."


def _fake_call_json(calls):
    from app.pipeline import ai

    def fake(_db, model_class, prompt, job_id, kind, max_tokens, route="text"):
        calls.append({"model": model_class.__name__, "kind": kind, "route": route, "prompt": prompt})
        if model_class is ai.ScriptDraft:
            return ai.ScriptDraft(title="Tiny board", narration=PARAPHRASE, claims=[], hook_type="question", post_text="A small board with a big decision.")
        if model_class is ai.ControlResult:
            return ai.ControlResult(decision="ALLOW")
        if model_class.__name__ == "PostPackaging":
            return model_class(title="One Small Board, One Big Decision", post_text="Why one tiny tactics board can hold a real decision.", hook_type="Bold claim")
        raise AssertionError(model_class)

    return fake


def _live_production(db, tmp_path, monkeypatch, packet):
    _image, _video, narration_wav = make_media(tmp_path)
    plan = {"platform": "youtube", "quality_dimensions": full_quality(), "idea_id": "GI001", "scenes": [scene_payload("real_image", "photo.jpg", "zoom_in"), scene_payload()]}
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    (tmp_path / "editorial-packet.json").write_text(json.dumps(packet))
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    topic = Topic(niche="handheld_gaming", language="en", title="Into the Breach decision")
    db.add(topic)
    db.commit()
    calls = []
    monkeypatch.setattr("app.pipeline.ai._call_json", _fake_call_json(calls))
    spoken = {}

    def fake_voice(segments, provider, output_dir, **kwargs):
        spoken["text"] = segments[0].text
        output_dir.mkdir(parents=True)
        generated = output_dir / "full.wav"
        shutil.copyfile(narration_wav, generated)
        alignment = output_dir / "full.alignment.json"
        normalized = output_dir / "full.alignment.normalized.json"
        alignment.write_text("{}")
        normalized.write_text("{}")
        return {"decision": "ALLOW", "reasons": [], "provider": provider, "estimated_cost_dkk": 0.1, "actual_cost_dkk": 0.1, "files": [{"segment_id": "full", "path": str(generated), "voice": kwargs["voice_id"], "alignment_path": str(alignment), "normalized_alignment_path": str(normalized), "duration_seconds": 2}]}

    def segments():
        words = spoken["text"].split()
        middle = len(words) // 2
        return [{"start": 0, "end": 1, "text": " ".join(words[:middle])}, {"start": 1, "end": 2, "text": " ".join(words[middle:])}]

    def alignment(_segment, _path, output):
        rows = segments()
        write_srt(rows, output)
        return rows

    def transcribe(_audio, output):
        rows = segments()
        write_srt(rows, output)
        return {"language": "en", "language_probability": 0.99, "segments": 2, "model": "mock", "segments_detail": rows}

    monkeypatch.setattr("app.pipeline.production.prepare_voice", fake_voice)
    monkeypatch.setattr("app.pipeline.production.write_alignment_srt", alignment)
    monkeypatch.setattr("app.pipeline.production.transcribe", transcribe)
    monkeypatch.setattr("app.pipeline.production.concat_with_idents", lambda content, target, **_kwargs: shutil.copyfile(content, target))
    return produce(db, topic.id, False, plan_path), calls, spoken


def test_live_production_narration_is_locked_to_packet_voiceover(db, tmp_path, monkeypatch):
    packet = complete_packet(datetime.now(timezone.utc))
    expected = " ".join(segment["voiceover"] for segment in packet["segments"])
    video, calls, spoken = _live_production(db, tmp_path, monkeypatch, packet)
    assert video.status == "AWAITING_OWNER"
    assert spoken["text"] == expected
    editorial = json.loads((Path(video.output_dir) / "checks.json").read_text())["editorial"]
    assert editorial["decision"] == "ALLOW"
    packaging = next(call for call in calls if call["model"] == "PostPackaging")
    assert "<packet>" in packaging["prompt"] and "Into the Breach" in packaging["prompt"]
    assert not any(call["model"] == "ScriptDraft" for call in calls)
    review = next(call for call in calls if call["model"] == "ControlResult")
    assert "store.steampowered.com" in review["prompt"]
    assert video.hook_type == "bold_claim"
    assert video.post_json["title"] == "One Small Board, One Big Decision"
    script = json.loads((Path(video.output_dir) / "script.json").read_text())
    assert script["narration_source"] == "editorial_packet_segments"


def test_live_production_records_real_features(db, tmp_path, monkeypatch):
    packet = complete_packet(datetime.now(timezone.utc))
    video, _calls, _spoken = _live_production(db, tmp_path, monkeypatch, packet)
    features = video.features_json
    assert features["recipe_id"] == packet["recipe_id"]
    assert features["story_id"] == packet["story_id"]
    assert features["idea_id"] == "GI001"
    assert features["hook_type"] == "bold_claim"
    assert features["opening_text"].startswith(packet["segments"][0]["voiceover"].split()[0])
    assert features["duration_seconds"] == video.duration_seconds
    assert features["thumbnail_type"] == "source_frame"
    assert features["voice"] == "elevenlabs"
    assert features["aspect_ratio"] == "9:16"
    assert "pacing" not in features and "CTA" not in features


def test_packet_claims_become_script_claims_with_inspected_sources(db, tmp_path, monkeypatch):
    packet = complete_packet(datetime.now(timezone.utc))
    video, _calls, _spoken = _live_production(db, tmp_path, monkeypatch, packet)
    claims = json.loads((Path(video.output_dir) / "claims.json").read_text())
    assert {claim["id"] for claim in claims} == {claim["id"] for claim in packet["claims"]}
    source_urls = {source["url"] for source in packet["sources"]}
    assert all(claim["source_url"] in source_urls and claim["verified"] for claim in claims)


def test_unknown_packet_state_still_blocks(db, tmp_path, monkeypatch):
    packet = complete_packet(datetime.now(timezone.utc))
    packet["state"] = "needs_footage"
    with pytest.raises(ValueError, match="editorial_blocked"):
        _live_production(db, tmp_path, monkeypatch, packet)
