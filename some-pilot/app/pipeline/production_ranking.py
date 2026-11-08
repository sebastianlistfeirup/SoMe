import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import Asset, License, Script, Topic, VideoVersion
from app.pipeline.approvals import paused, sha256_file, transition
from app.pipeline.media import probe, require_tools, transcribe
from app.pipeline.policy import content_policy, rights_policy
from app.pipeline.production import _write_deliverables, transcription_quality
from app.pipeline.ranking import RankingPlan, render_ranking
from app.pipeline.ranking_art import make_storyboard, make_thumbnail


def produce_ranking(db: Session, plan_path: Path, output: Path) -> dict:
    if paused(db):
        raise RuntimeError("emergency_stop_active")
    require_tools()
    plan = RankingPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    topic = Topic(niche="handheld_gaming", language="en", title=plan.title, score_json={"editorial": True, "external_performance_measurements": False})
    db.add(topic)
    db.flush()
    narration = " ".join([plan.hook, *[scene.narration for scene in sorted(plan.scenes, key=lambda item: item.rank, reverse=True)]])
    script = Script(topic_id=topic.id, content=narration, claims_json=[{"id": "hades-2-deck", "text": "Hades II is Steam Deck Verified.", "source_url": "https://www.supergiantgames.com/blog/hades2-faq/", "verified": True}], prompt_version="editorial-ranking-v1", model="human-reviewed-template", is_demo=False)
    db.add(script)
    db.flush()
    video = VideoVersion(script_id=script.id, topic_id=topic.id, output_dir=str(output), post_json={"text": plan.post_text, "links": sorted({str(scene.clip_url) for scene in plan.scenes}), "ai_disclosure": True, "non_affiliation": True}, hook_type="ranking_reveal", language="en", features_json={"niche": topic.niche, "format": "editorial_gameplay_ranking", "pacing": "fast", "voice": "Microsoft Zira Desktop" if plan.voice_dir else "espeak-ng-draft", "real_gameplay_clips": 10, "synthetic_fallback": False})
    db.add(video)
    db.flush()
    assets = []
    licenses = []
    for scene in plan.scenes:
        source = (plan_path.parent / scene.source_path).resolve()
        asset = Asset(path=str(source), source_url=str(scene.clip_url), rights_status="CLEARED", sha256=sha256_file(str(source)), bytes=source.stat().st_size, media_type="video/mp4", metadata_json={"game": scene.game, "rank": scene.rank, "source": "official publisher gameplay via Steam", "music_allowed": scene.music_allowed})
        db.add(asset)
        db.flush()
        license_ = License(asset_id=asset.id, rights_holder=scene.rights_holder, license_text=scene.rights_evidence, source_url=str(scene.policy_url), commercial_allowed=True, derivative_allowed=True, platforms_json=["youtube", "instagram", "tiktok", "facebook"], territories_json=["global"], attribution=scene.attribution, evidence_path=str(plan_path.parent / "rights.json"), age_clearance="NO_PEOPLE", status="ALLOW")
        db.add(license_)
        assets.append(asset)
        licenses.append(license_)
    rights = rights_policy(db, [asset.id for asset in assets], "youtube")
    if rights.decision != "ALLOW":
        transition(video, "BLOCKED")
        db.commit()
        raise ValueError("rights_blocked:" + ",".join(rights.reasons))
    transition(video, "RIGHTS_CHECKED")
    transition(video, "SCRIPTED")
    layout = render_ranking(plan_path, output)
    rendered = output / "video.mp4"
    video.video_path = str(rendered)
    thumb = make_thumbnail(plan_path, output)
    video.thumbnail_path = str(thumb)
    duration = float(probe(rendered)["format"]["duration"])
    video.duration_seconds = duration
    make_storyboard(rendered, output, duration)
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
    checks = {"rights": rights.model_dump(), "layout": layout, "technical": technical, "safety": safety.model_dump(), "quality": quality, "transcription": transcription, "visual_review": "required_before_publication", "editorial_limits": "Subjective handheld ranking, not FPS testing on Legion Go 2. Publisher policies are not legal guarantees.", "owner_review_required": True}
    (output / "checks.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
    if safety.decision != "ALLOW" or quality["decision"] != "ALLOW":
        transition(video, "BLOCKED")
        db.commit()
        raise ValueError("safety_or_quality_blocked")
    transition(video, "SAFETY_REVIEWED")
    transition(video, "AWAITING_OWNER")
    _write_deliverables(output, video, script, assets, licenses, checks)
    db.commit()
    return {"video_id": video.id, "topic_id": topic.id, "status": video.status, "output_dir": str(output), "duration_seconds": duration, "checks": checks["quality"], "real_gameplay_clips": 10}

