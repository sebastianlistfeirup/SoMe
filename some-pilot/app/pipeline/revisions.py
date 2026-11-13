import json
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Asset, AuditEvent, License, Review, Script, Topic, VideoVersion, utcnow
from app.pipeline.ai import claude_revise_post
from app.pipeline.approvals import paused, transition
from app.pipeline.policy import content_policy
from app.pipeline.posts import build_post, post_view
from app.pipeline.production import _write_deliverables


REQUIRED_CHECKS = ("rights", "technical", "layout", "safety", "quality", "claim_control", "voice", "media_composition")


def create_post_revision(db: Session, video_id: int, review_id: int, job_id: str) -> VideoVersion:
    if paused(db):
        raise RuntimeError("emergency_stop_active")
    source = db.get(VideoVersion, video_id)
    rejection = db.get(Review, review_id)
    if not source or not rejection or rejection.video_version_id != source.id or rejection.decision != "REJECTED":
        raise ValueError("rejected_source_and_review_required")
    if source.status != "REJECTED":
        raise ValueError("source_is_not_rejected")
    feedback = rejection.note.strip()
    if len(feedback) < 3:
        raise ValueError("revision_feedback_required")
    candidates = db.query(VideoVersion).filter(VideoVersion.topic_id == source.topic_id).order_by(VideoVersion.id.desc()).all()
    existing = next((item for item in candidates if item.features_json.get("revision_review_id") == rejection.id), None)
    if existing:
        return existing

    topic = db.get(Topic, source.topic_id)
    script = db.get(Script, source.script_id)
    if not topic or not script:
        raise ValueError("source_topic_or_script_missing")
    original = post_view(source.post_json, topic.title)
    revised = claude_revise_post(db, original, feedback, job_id)
    revised_post = build_post(revised.title, revised.caption, revised.hashtags, list(source.post_json.get("links", [])))
    post = {**source.post_json, **revised_post}
    safety = content_policy(script.content + "\n" + post["text"])
    if safety.decision != "ALLOW":
        raise ValueError("revised_post_safety_blocked")

    source_dir = Path(source.output_dir)
    checks = json.loads((source_dir / "checks.json").read_text(encoding="utf-8"))
    if any(checks.get(name, {}).get("decision") != "ALLOW" for name in REQUIRED_CHECKS):
        raise ValueError("source_checks_not_allowed")
    asset_ids = source.manifest_json.get("asset_ids", [])
    assets_by_id = {asset.id: asset for asset in db.query(Asset).filter(Asset.id.in_(asset_ids)).all()} if asset_ids else {}
    if len(assets_by_id) != len(asset_ids):
        raise ValueError("source_assets_missing")
    asset_rows = [assets_by_id[asset_id] for asset_id in asset_ids]
    license_rows = [db.query(License).filter(License.asset_id == asset.id).one() for asset in asset_rows]

    version = db.query(VideoVersion).filter(VideoVersion.topic_id == source.topic_id).count() + 1
    output = get_settings().data_dir / "versions" / f"topic-{source.topic_id}-v{version}"
    temporary = output.with_name(f".{output.name}-{job_id}.tmp")
    if output.exists() or temporary.exists():
        raise ValueError("revision_output_already_exists")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    created_output = False
    try:
        shutil.copytree(source_dir, temporary)
        temporary.rename(output)
        created_output = True
        video = VideoVersion(
            script_id=source.script_id,
            topic_id=source.topic_id,
            version=version,
            output_dir=str(output),
            video_path=str(output / "video.mp4"),
            thumbnail_path=str(output / "thumbnail.jpg"),
            post_json=post,
            duration_seconds=source.duration_seconds,
            hook_type=source.hook_type,
            format=source.format,
            language=source.language,
            features_json={
                **source.features_json,
                "revision_of": source.id,
                "revision_review_id": rejection.id,
                "revision_scope": "title_caption_hashtags",
                "revised_at_utc": utcnow().isoformat(),
            },
        )
        db.add(video)
        db.flush()
        for target in ("RIGHTS_CHECKED", "SCRIPTED", "RENDERED", "TECH_CHECKED", "SAFETY_REVIEWED", "AWAITING_OWNER"):
            transition(video, target, "post-revision")
        checks["safety"] = safety.model_dump()
        checks["revision"] = {
            "source_video_id": source.id,
            "rejection_review_id": rejection.id,
            "scope": "title_caption_hashtags",
            "video_audio_and_visuals_reused": True,
            "owner_feedback": feedback,
        }
        (output / "checks.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
        _write_deliverables(output, video, script, asset_rows, license_rows, checks)
        db.add(AuditEvent(
            actor="post-revision-worker",
            action="POST_REVISION_CREATED",
            entity_type="video_version",
            entity_id=str(video.id),
            details_json={"source_video_id": source.id, "rejection_review_id": rejection.id, "scope": "title_caption_hashtags"},
        ))
        db.commit()
        db.refresh(video)
        from app.pipeline.alerts import notify_awaiting_owner

        notify_awaiting_owner(db, video)
        return video
    except Exception:
        db.rollback()
        if temporary.exists():
            shutil.rmtree(temporary)
        if created_output and output.exists():
            shutil.rmtree(output)
        raise
