import difflib
import json
import re
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Asset, Cost, License, Observation, Script, Topic, VideoVersion
from app.pipeline.ai import build_clip_plan, claude_draft, current_prompt_version, demo_draft, review_draft
from app.pipeline.approvals import paused, sha256_file, transition
from app.pipeline.media import probe, render, require_tools, storyboard, synthesize, technical_checks, thumbnail, transcribe
from app.pipeline.scenes import make_scene_assets
from app.pipeline.policy import content_policy, rights_policy
from app.pipeline.posts import build_post
from app.pipeline.voice import VoiceSegment, voice_asset_report


def transcription_quality(script: str, transcription: dict) -> dict:
    spoken = " ".join(segment["text"] for segment in transcription.get("segments_detail", []))
    normalize = lambda value: re.sub(r"\s+", " ", re.sub(r"[^\wæøåÆØÅ ]", " ", value.lower())).strip()
    similarity = difflib.SequenceMatcher(None, normalize(script), normalize(spoken), autojunk=False).ratio() if spoken else 0
    expected_numbers = re.findall(r"\d+(?:[.,]\d+)?", script)
    missing_numbers = [number for number in expected_numbers if number not in spoken]
    reasons = []
    if similarity < 0.65:
        reasons.append("transcription_similarity_below_0.65")
    if missing_numbers:
        reasons.append("numbers_missing_or_misread")
    if transcription.get("language_probability", 0) < 0.70:
        reasons.append("language_confidence_below_0.70")
    return {"decision": "ALLOW" if not reasons else "REVIEW", "reasons": reasons, "similarity": round(similarity, 4), "missing_numbers": missing_numbers, "names_and_numbers_require_owner_check": True}


def produce(db: Session, topic_id: int, dry_run: bool = True, allow_synthetic_fallback: bool = False) -> VideoVersion:
    settings = get_settings()
    if paused(db):
        raise RuntimeError("emergency_stop_active")
    if not dry_run and not allow_synthetic_fallback:
        raise ValueError("licensed_internet_assets_required")
    require_tools()
    disk = shutil.disk_usage(settings.data_dir)
    if disk.used / disk.total >= 0.90:
        raise RuntimeError("render_blocked_disk_at_or_above_90_percent")
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise ValueError("topic_not_found")
    if topic.status == "BLOCKED":
        raise ValueError("topic_blocked")
    claim_control = {"decision": "ALLOW", "issues": [], "mode": "demo_no_external_claims"}
    next_script_version = db.query(Script).filter(Script.topic_id == topic.id).count() + 1
    script_job_id = f"script-{topic_id}-v{next_script_version}"
    review_job_id = f"review-{topic_id}-v{next_script_version}"
    if dry_run:
        draft = demo_draft(topic)
    else:
        observations = db.query(Observation).filter(Observation.is_demo.is_(False), Observation.topic.startswith(topic.niche + ":")).order_by(Observation.collected_at_utc.desc()).limit(20).all()
        excerpts = [{"source_url": row.source_url, "topic": row.topic, "metric_name": row.metric_name, "metric_value": row.metric_value, "unit": row.unit, "collected_at_utc": row.collected_at_utc, "limitations": row.limitations} for row in observations]
        draft = claude_draft(db, topic, excerpts, script_job_id)
        claim_control = review_draft(db, draft, excerpts, review_job_id).model_dump()
    script = Script(topic_id=topic.id, version=next_script_version, content=draft.narration, claims_json=[claim.model_dump() for claim in draft.claims], prompt_version="demo-v2" if dry_run else current_prompt_version(db), model="demo" if dry_run else settings.claude_model_text, is_demo=dry_run)
    db.add(script)
    db.flush()
    production_cost = 0 if dry_run else sum(row.actual_amount or row.estimated_amount for row in db.query(Cost).filter(Cost.job_id.in_([script_job_id, review_job_id])).all())
    version_number = db.query(VideoVersion).filter(VideoVersion.topic_id == topic.id).count() + 1
    output = settings.data_dir / "versions" / f"topic-{topic.id}-v{version_number}"
    output.mkdir(parents=True, exist_ok=False)
    default_hashtags = ["ai", "artificialintelligence", "tech"] if "ai" in topic.niche.lower() else ["gaming", "handheldgaming", "tech"]
    post = build_post(draft.title, draft.post_text, default_hashtags, [claim.source_url for claim in draft.claims], ai_disclosure=True)
    video = VideoVersion(script_id=script.id, topic_id=topic.id, version=version_number, output_dir=str(output), post_json=post, hook_type=draft.hook_type, language=topic.language, features_json={"niche": topic.niche, "pacing": "measured", "voice": "espeak-ng", "CTA": "save", "production_cost": production_cost, "is_demo": dry_run})
    db.add(video)
    db.flush()
    try:
        backgrounds = make_scene_assets(output)
        assets = []
        licenses = []
        for index, background in enumerate(backgrounds, 1):
            asset = Asset(path=str(background), source_url=f"synthetic://some-pilot/scene-{index}", rights_status="CLEARED", sha256=sha256_file(str(background)), bytes=background.stat().st_size, media_type="image/png", metadata_json={"generated_by": "Original Pillow motion-graphic scene", "no_people": True})
            db.add(asset)
            db.flush()
            license_ = License(asset_id=asset.id, rights_holder="SoMe pilot owner", license_text="Original synthetic scene generated locally for this project; owner-controlled.", source_url=f"synthetic://some-pilot/scene-{index}", commercial_allowed=True, derivative_allowed=True, platforms_json=["youtube", "instagram", "tiktok", "facebook"], territories_json=["global"], evidence_path=str(background), age_clearance="NO_PEOPLE", status="ALLOW")
            db.add(license_)
            assets.append(asset)
            licenses.append(license_)
        rights = rights_policy(db, [asset.id for asset in assets], "youtube")
        if rights.decision != "ALLOW":
            transition(video, "BLOCKED")
            raise ValueError("rights_blocked:" + ",".join(rights.reasons))
        transition(video, "RIGHTS_CHECKED")
        transition(video, "SCRIPTED")
        narration = output / "narration.wav"
        synthesize(draft.narration, narration, topic.language)
        voice = voice_asset_report(VoiceSegment("full", draft.narration), narration, "espeak-ng", voice="espeak-ng", reused=False)
        (output / "voice_assets.json").write_text(json.dumps(voice, indent=2, ensure_ascii=False), encoding="utf-8")
        if voice["decision"] != "ALLOW":
            transition(video, "BLOCKED")
            db.commit()
            raise ValueError("voice_assets_blocked:" + ",".join(voice["reasons"]))
        captions = output / "captions.srt"
        transcription = transcribe(narration, captions)
        audio_duration = float(probe(narration)["format"]["duration"])
        clip_plan = build_clip_plan(transcription["segments_detail"], [asset.id for asset in assets], audio_duration, [claim.id for claim in draft.claims])
        (output / "clip_plan.json").write_text(clip_plan.model_dump_json(indent=2), encoding="utf-8")
        rendered = output / "video.mp4"
        layout = render(backgrounds, narration, captions, draft.title, rendered)
        thumb = output / "thumbnail.jpg"
        thumbnail(rendered, thumb)
        board = output / "storyboard.jpg"
        storyboard(rendered, board)
        video.video_path = str(rendered)
        video.thumbnail_path = str(thumb)
        transition(video, "RENDERED")
        technical = technical_checks(rendered, captions)
        if technical["decision"] != "ALLOW":
            transition(video, "BLOCKED")
            raise ValueError("technical_blocked:" + ",".join(technical["reasons"]))
        video.duration_seconds = technical["duration_seconds"]
        transition(video, "TECH_CHECKED")
        safety = content_policy(draft.narration + "\n" + draft.post_text, contains_people=False, ages_verified=False)
        quality = transcription_quality(draft.narration, transcription)
        checks = {"rights": rights.model_dump(), "technical": technical, "layout": layout, "safety": safety.model_dump(), "quality": quality, "claim_control": claim_control, "voice": voice, "transcription": transcription, "owner_review_required": True}
        (output / "checks.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
        if safety.decision != "ALLOW" or quality["decision"] != "ALLOW":
            transition(video, "BLOCKED")
            raise ValueError("safety_or_quality_blocked")
        transition(video, "SAFETY_REVIEWED")
        transition(video, "AWAITING_OWNER")
        _write_deliverables(output, video, script, assets, licenses, checks)
        db.commit()
        db.refresh(video)
        return video
    except Exception:
        db.commit()
        raise


def _write_deliverables(output: Path, video: VideoVersion, script: Script, assets: list[Asset], licenses: list[License], checks: dict) -> None:
    (output / "claims.json").write_text(json.dumps(script.claims_json, indent=2, ensure_ascii=False), encoding="utf-8")
    rights = {"assets": [{"asset_id": asset.id, "source_url": asset.source_url, "sha256": asset.sha256, "rights_holder": license_.rights_holder, "license": license_.license_text, "commercial": license_.commercial_allowed, "derivatives": license_.derivative_allowed, "platforms": license_.platforms_json, "territories": license_.territories_json, "age_clearance": license_.age_clearance, "status": license_.status} for asset, license_ in zip(assets, licenses)]}
    (output / "rights.json").write_text(json.dumps(rights, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "post.json").write_text(json.dumps(video.post_json, indent=2, ensure_ascii=False), encoding="utf-8")
    files = {}
    deliverable_names = ["video.mp4", "captions.srt", "thumbnail.jpg", "post.json", "claims.json", "rights.json", "checks.json", "clip_plan.json", "storyboard.jpg"]
    deliverable_names.append("voice_assets.json")
    for name in deliverable_names:
        files[name] = sha256_file(str(output / name))
    manifest = {"video_version_id": video.id, "script_id": script.id, "script_version": script.version, "prompt_version": script.prompt_version, "model": script.model, "asset_ids": [asset.id for asset in assets], "status": video.status, "is_demo": video.features_json.get("is_demo", False), "files_sha256": files}
    video.manifest_json = manifest
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
