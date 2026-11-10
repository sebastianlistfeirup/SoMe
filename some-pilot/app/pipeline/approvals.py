import hashlib
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AuditEvent, Review, Setting, VideoVersion, utcnow


class ApprovalError(ValueError):
    pass


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def approval_digest(video: VideoVersion, platform: str, account: str) -> dict:
    if not video.video_path or not video.thumbnail_path:
        raise ApprovalError("missing_rendered_files")
    components = {
        "video_sha256": sha256_file(video.video_path),
        "thumbnail_sha256": sha256_file(video.thumbnail_path),
        "text": video.post_json.get("text", ""),
        "links": sorted(video.post_json.get("links", [])),
        "platform": platform,
        "account": account,
    }
    return {**components, "approval_sha256": canonical_hash(components)}


def paused(db: Session) -> bool:
    setting = db.get(Setting, "emergency_stop")
    return bool(setting and setting.value_json.get("enabled"))


def set_pause(db: Session, enabled: bool, actor: str) -> None:
    setting = db.get(Setting, "emergency_stop") or Setting(key="emergency_stop")
    setting.value_json = {"enabled": enabled}
    db.merge(setting)
    db.add(AuditEvent(actor=actor, action="PAUSE" if enabled else "RESUME", entity_type="system", entity_id="all", details_json={}))
    db.commit()


def transition(video: VideoVersion, target: str, actor: str = "system") -> None:
    allowed = {
        "DISCOVERED": {"RIGHTS_CHECKED", "BLOCKED", "FAILED", "PAUSED"},
        "RIGHTS_CHECKED": {"SCRIPTED", "BLOCKED", "FAILED", "PAUSED"},
        "SCRIPTED": {"RENDERED", "BLOCKED", "FAILED", "PAUSED"},
        "RENDERED": {"TECH_CHECKED", "BLOCKED", "FAILED", "PAUSED"},
        "TECH_CHECKED": {"SAFETY_REVIEWED", "BLOCKED", "FAILED", "PAUSED"},
        "SAFETY_REVIEWED": {"AWAITING_OWNER", "BLOCKED", "FAILED", "PAUSED"},
        "AWAITING_OWNER": {"APPROVED", "REJECTED", "BLOCKED", "PAUSED"},
        "APPROVED": {"SCHEDULED", "AWAITING_OWNER", "PAUSED"},
        "SCHEDULED": {"PUBLISHING", "PAUSED", "FAILED"},
        "PUBLISHING": {"PUBLISHED", "RECONCILE_REQUIRED", "FAILED", "PAUSED"},
        "RECONCILE_REQUIRED": {"PUBLISHED", "FAILED", "PAUSED"},
        "FAILED": {"AWAITING_OWNER", "PAUSED"},
        "PAUSED": {"AWAITING_OWNER", "SCHEDULED"},
        "PUBLISHED": set(),
        "REJECTED": {"AWAITING_OWNER"},
        "BLOCKED": set(),
    }
    if target not in allowed.get(video.status, set()):
        raise ApprovalError(f"invalid_transition:{video.status}->{target}")
    video.status = target
    video.updated_at = utcnow()


def approve(
    db: Session,
    video: VideoVersion,
    reviewer: str,
    platform: str,
    account: str,
    owner_watched_full_video: bool,
) -> Review:
    if not reviewer.strip():
        raise ApprovalError("owner_reviewer_required")
    if not owner_watched_full_video:
        raise ApprovalError("owner_must_watch_full_video")
    if paused(db):
        raise ApprovalError("emergency_stop_active")
    if video.status != "AWAITING_OWNER":
        raise ApprovalError("video_not_awaiting_owner")
    checks_path = Path(video.output_dir) / "checks.json"
    if not checks_path.exists():
        raise ApprovalError("missing_checks")
    checks = json.loads(checks_path.read_text(encoding="utf-8"))
    for name in ("rights", "technical", "layout", "safety", "quality", "claim_control", "voice"):
        if checks.get(name, {}).get("decision") != "ALLOW":
            raise ApprovalError(f"check_not_allowed:{name}")
    digest = approval_digest(video, platform, account)
    review = Review(
        video_version_id=video.id,
        decision="APPROVED",
        reviewer=reviewer,
        digest_json=digest,
        checks_json=checks,
    )
    transition(video, "APPROVED", reviewer)
    db.add(review)
    db.add(AuditEvent(actor=reviewer, action="APPROVED", entity_type="video_version", entity_id=str(video.id), details_json={"approval_sha256": digest["approval_sha256"]}))
    db.commit()
    db.refresh(review)
    return review


def latest_approval(db: Session, video_id: int) -> Review | None:
    return (
        db.query(Review)
        .filter(Review.video_version_id == video_id, Review.decision == "APPROVED")
        .order_by(Review.created_at.desc(), Review.id.desc())
        .first()
    )


def verify_approval(db: Session, video: VideoVersion, platform: str, account: str) -> Review:
    settings = get_settings()
    if settings.dry_run or not settings.publish_enabled:
        raise ApprovalError("publishing_disabled")
    if paused(db):
        raise ApprovalError("emergency_stop_active")
    review = latest_approval(db, video.id)
    if review is None:
        raise ApprovalError("owner_approval_required")
    current = approval_digest(video, platform, account)
    if current["approval_sha256"] != review.digest_json.get("approval_sha256"):
        raise ApprovalError("approval_invalidated_by_change")
    return review


def invalidate_approval(db: Session, video: VideoVersion, actor: str) -> None:
    if video.status in {"APPROVED", "SCHEDULED"}:
        video.status = "AWAITING_OWNER"
        video.updated_at = utcnow()
        db.add(AuditEvent(actor=actor, action="APPROVAL_INVALIDATED", entity_type="video_version", entity_id=str(video.id), details_json={}))
        db.commit()
