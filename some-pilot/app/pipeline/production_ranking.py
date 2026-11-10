import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import Asset, License, Script, Topic, VideoVersion
from app.pipeline.approvals import paused, sha256_file, transition
from app.pipeline.media import probe, require_tools, transcribe
from app.pipeline.policy import content_policy, rights_policy
from app.pipeline.production import _write_deliverables, transcription_quality
from app.pipeline.ranking import RankingPlan, get_platform, render_ranking
from app.pipeline.ranking_art import make_landscape_thumbnail, make_storyboard, make_thumbnail
from app.pipeline.ranking_claims import ranking_claim_control
from app.pipeline.voice import prepare_voice, ranking_voice_segments, voice_file_map


def _existing_voice_dir(plan_path: Path, voice_dir: str | None) -> Path | None:
    if not voice_dir:
        return None
    if Path(voice_dir).name != voice_dir or voice_dir in {"", ".", ".."} or "\\" in voice_dir:
        raise ValueError("invalid_voice_directory")
    root = plan_path.parent.resolve()
    directory = (root / voice_dir).resolve()
    if root not in directory.parents:
        raise ValueError("voice_directory_outside_research")
    return directory


def produce_ranking(db: Session, plan_path: Path, output: Path, platform: str = "reels", mobile_style: str = "zoom", voice_provider: str = "kokoro") -> dict:
    if paused(db):
        raise RuntimeError("emergency_stop_active")
    plan = RankingPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    claim_control = ranking_claim_control(plan)
    if claim_control["decision"] != "ALLOW":
        raise ValueError("ranking_claim_control_blocked:" + ",".join(claim_control["issues"]))
    require_tools()
    existing_voice = _existing_voice_dir(plan_path, plan.voice_dir) if voice_provider == "kokoro" else None
    voice = prepare_voice(ranking_voice_segments(plan), voice_provider, output / "voice-assets", existing_voice)
    output.mkdir(parents=True, exist_ok=True)
    (output / "voice_assets.json").write_text(json.dumps(voice, indent=2, ensure_ascii=False), encoding="utf-8")
    if voice["decision"] != "ALLOW":
        raise ValueError("voice_assets_blocked:" + ",".join(voice["reasons"]))
    voice_files = voice_file_map(voice)
    if len(voice_files) != 11:
        raise ValueError("voice_segment_coverage_incomplete")

    topic = Topic(niche="handheld_gaming", language="en", title=plan.title, score_json={"editorial": True, "external_performance_measurements": False})
    db.add(topic)
    db.flush()
    narration = " ".join([plan.hook, *[scene.narration for scene in sorted(plan.scenes, key=lambda item: item.rank, reverse=True)]])
    script = Script(topic_id=topic.id, content=narration, claims_json=[claim.model_dump(mode="json") for claim in plan.claims], prompt_version="editorial-ranking-v4-voiceover", model="human-reviewed-template", is_demo=False)
    db.add(script)
    db.flush()
    video = VideoVersion(script_id=script.id, topic_id=topic.id, output_dir=str(output), post_json={"text": plan.post_text, "links": sorted({str(scene.clip_url) for scene in plan.scenes}), "ai_disclosure": True, "non_affiliation": True}, hook_type="ranking_reveal", language="en", features_json={"niche": topic.niche, "platform": platform, "format": "editorial_gameplay_ranking", "aspect_ratio": "16:9" if platform == "youtube" else "9:16", "pacing": "fast", "narration_tempo": get_platform(platform).tempo, "voice_provider": voice_provider, "voice_preset": plan.voice_model, "voice_only": True, "avatar_present": False, "real_gameplay_clips": 10, "synthetic_fallback": False, "mobile_style": mobile_style, "full_bleed_action": platform != "youtube" and mobile_style == "zoom"})
    db.add(video)
    db.flush()
    assets = []
    licenses = []
    for scene in plan.scenes:
        source = (plan_path.parent / scene.source_path).resolve()
        asset = Asset(path=str(source), source_url=str(scene.clip_url), rights_status="CLEARED", sha256=sha256_file(str(source)), bytes=source.stat().st_size, media_type="video/mp4", metadata_json={"game": scene.game, "rank": scene.rank, "source": str(scene.clip_url), "source_type": "official_publisher_gameplay_or_promotional_video", "music_allowed": scene.music_allowed, "focus_x": scene.focus_x, "focus_y": scene.focus_y, "zoom": scene.zoom})
        db.add(asset)
        db.flush()
        license_ = License(asset_id=asset.id, rights_holder=scene.rights_holder, license_text=scene.rights_evidence, source_url=str(scene.policy_url), commercial_allowed=True, derivative_allowed=True, platforms_json=["youtube", "instagram", "tiktok", "facebook"], territories_json=["global"], attribution=scene.attribution, evidence_path=str(plan_path.parent / "rights.json"), age_clearance="NO_PEOPLE", status="ALLOW")
        db.add(license_)
        assets.append(asset)
        licenses.append(license_)
    target_platform = "instagram" if platform == "reels" else platform
    rights = rights_policy(db, [asset.id for asset in assets], target_platform)
    if rights.decision != "ALLOW":
        transition(video, "BLOCKED")
        db.commit()
        raise ValueError("rights_blocked:" + ",".join(rights.reasons))
    transition(video, "RIGHTS_CHECKED")
    transition(video, "SCRIPTED")
    layout = render_ranking(plan_path, output, platform, mobile_style, voice_files)
    rendered = output / "video.mp4"
    video.video_path = str(rendered)
    thumb = make_landscape_thumbnail(plan_path, output) if platform == "youtube" else make_thumbnail(plan_path, output)
    video.thumbnail_path = str(thumb)
    duration = float(probe(rendered)["format"]["duration"])
    video.duration_seconds = duration
    make_storyboard(rendered, output, duration, landscape=platform == "youtube")
    (output / "clip_plan.json").write_text((output / "editorial.json").read_text(encoding="utf-8"), encoding="utf-8")
    transition(video, "RENDERED")
    technical = layout["technical"]
    if technical["decision"] != "ALLOW":
        transition(video, "BLOCKED")
        db.commit()
        raise ValueError("technical_blocked:" + ",".join(technical["reasons"]))
    transition(video, "TECH_CHECKED")
    safety = content_policy(narration + "\n" + plan.post_text, contains_people=False, ages_verified=False)
    transcription = transcribe(output / "narration.wav", output / "transcription.srt")
    quality = transcription_quality(narration, transcription)
    checks = {"rights": rights.model_dump(), "layout": layout, "technical": technical, "safety": safety.model_dump(), "quality": quality, "claim_control": claim_control, "voice": voice, "transcription": transcription, "visual_review": "required_before_publication", "editorial_limits": "Subjective handheld ranking, not FPS testing on Legion Go 2. Publisher policies are not legal guarantees.", "owner_review_required": True}
    (output / "checks.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
    if safety.decision != "ALLOW" or quality["decision"] != "ALLOW":
        transition(video, "BLOCKED")
        db.commit()
        raise ValueError("safety_or_quality_blocked")
    transition(video, "SAFETY_REVIEWED")
    transition(video, "AWAITING_OWNER")
    _write_deliverables(output, video, script, assets, licenses, checks)
    db.commit()
    return {"video_id": video.id, "topic_id": topic.id, "platform": platform, "status": video.status, "output_dir": str(output), "duration_seconds": duration, "checks": checks["quality"], "real_gameplay_clips": 10, "voice_provider": voice_provider, "avatar_present": False}
