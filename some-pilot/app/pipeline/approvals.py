import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AuditEvent, Review, Setting, VideoVersion, utcnow


class ApprovalError(ValueError):
    pass


SUPPORTED_PLATFORMS = {"youtube", "instagram", "facebook", "tiktok", "facebook_feed"}
FEED_VIDEO = "feed_4x5.mp4"
FEED_THUMBNAIL = "feed_thumbnail.jpg"


def feed_variant(video: VideoVersion) -> dict | None:
    """The native 4:5 render attached to this video for an organic Facebook feed post, if any."""
    info = (video.features_json or {}).get("feed_variant") or {}
    if not info or not video.output_dir:
        return None
    root = Path(video.output_dir)
    video_file, thumbnail = root / info.get("video", FEED_VIDEO), root / info.get("thumbnail", FEED_THUMBNAIL)
    if not video_file.is_file() or not thumbnail.is_file():
        return None
    return {**info, "video_path": str(video_file), "thumbnail_path": str(thumbnail)}


def _platform_allowed(video: VideoVersion, platform: str) -> bool:
    allowed = set((video.features_json or {}).get("allowed_platforms") or ["youtube", "instagram", "facebook", "tiktok"])
    # The feed post is a second Facebook format of the same video, allowed wherever Facebook is.
    return platform in allowed or (platform == "facebook_feed" and "facebook" in allowed)


def _validate_destination(video: VideoVersion, destination: dict, seen: set) -> None:
    if destination["platform"] not in SUPPORTED_PLATFORMS:
        raise ApprovalError("unsupported_platform")
    if not _platform_allowed(video, destination["platform"]):
        raise ApprovalError(f"format_not_for_platform:{destination['platform']}")
    if not destination["account"].strip():
        raise ApprovalError("connected_account_required")
    key = (destination["platform"], destination["account"])
    if key in seen:
        raise ApprovalError("duplicate_destination")
    seen.add(key)
    if destination.get("visibility", "public") not in {"private", "unlisted", "public"}:
        raise ApprovalError("invalid_visibility")
    if destination["platform"] == "tiktok":
        # TikTok Direct Post has no default privacy level: the owner must have chosen one.
        from app.pipeline.tiktok_post import normalize_post_settings

        normalize_post_settings(destination.get("tiktok"))
    if destination["platform"] == "facebook_feed" and feed_variant(video) is None:
        raise ApprovalError("facebook_feed_variant_missing")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def artifact_hashes(video: VideoVersion) -> dict:
    root = Path(video.output_dir)
    names = ("narration.wav", "captions.srt", "script.json", "alignment.json", "alignment.normalized.json", "editorial.json")
    return {name: sha256_file(str(root / name)) for name in names if (root / name).is_file()}


def approval_digest(video: VideoVersion, platform: str, account: str) -> dict:
    if not video.video_path or not video.thumbnail_path:
        raise ApprovalError("missing_rendered_files")
    components = {
        "video_sha256": sha256_file(video.video_path),
        "thumbnail_sha256": sha256_file(video.thumbnail_path),
        "artifacts_sha256": artifact_hashes(video),
        "text": video.post_json.get("text", ""),
        "links": sorted(video.post_json.get("links", [])),
        "platform": platform,
        "account": account,
    }
    return {**components, "approval_sha256": canonical_hash(components)}


def paused(db: Session) -> bool:
    setting = db.get(Setting, "emergency_stop")
    return bool(setting and setting.value_json.get("enabled"))


def editorial_blockers(checks: dict, now: datetime | None = None) -> list[str]:
    editorial = checks.get("editorial")
    if not editorial:
        return []
    if editorial.get("decision") != "ALLOW":
        return ["check_not_allowed:editorial"]
    valid_until = editorial.get("source_valid_until")
    if valid_until:
        expiry = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
        expiry = expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry.astimezone(timezone.utc)
        if expiry <= (now or datetime.now(timezone.utc)):
            return ["editorial_source_refresh_required"]
    return []


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


REJECTED_VOICE_PROVIDERS = {"kokoro", "espeak-ng"}


def _affiliate_blockers(video: VideoVersion) -> list[str]:
    from app.pipeline.monetization import affiliate_blockers

    return affiliate_blockers(video.post_json or {})


def uses_rejected_voice(video: VideoVersion) -> bool:
    """Kokoro af_bella (and the espeak fallback) are creatively rejected; such videos can never be approved."""
    features = video.features_json or {}
    return (features.get("voice_provider") or features.get("voice")) in REJECTED_VOICE_PROVIDERS


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
    if uses_rejected_voice(video):
        raise ApprovalError("rejected_voice_not_publishable:kokoro_or_espeak")
    checks_path = Path(video.output_dir) / "checks.json"
    if not checks_path.exists():
        raise ApprovalError("missing_checks")
    checks = json.loads(checks_path.read_text(encoding="utf-8"))
    for name in ("rights", "technical", "layout", "safety", "quality", "claim_control", "voice", "media_composition"):
        if checks.get(name, {}).get("decision") != "ALLOW":
            raise ApprovalError(f"check_not_allowed:{name}")
    blockers = editorial_blockers(checks) + _affiliate_blockers(video)
    if blockers:
        raise ApprovalError(blockers[0])
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
    blockers = editorial_blockers(review.checks_json)
    if blockers:
        raise ApprovalError(blockers[0])
    if video.status not in {"APPROVED", "SCHEDULED", "PUBLISHING", "RECONCILE_REQUIRED", "PUBLISHED"}:
        raise ApprovalError("approval_invalidated_by_state")
    destinations = review.digest_json.get("destinations")
    if destinations:
        current = destinations_digest(video, destinations)
        if not any(item["platform"] == platform and item["account"] == account for item in destinations):
            raise ApprovalError("approval_destination_mismatch")
    else:
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


def destinations_digest(video: VideoVersion, destinations: list[dict]) -> dict:
    if not video.video_path or not video.thumbnail_path:
        raise ApprovalError("missing_rendered_files")
    from app.pipeline.variants import ai_label_for, platform_variant

    normalized = []
    for destination in destinations:
        item = {
            "platform": destination["platform"],
            "account": destination["account"],
            "visibility": destination.get("visibility", "public"),
            "publish_at": destination.get("publish_at"),
        }
        # digest_version 2 binds the exact per-platform text and the AI label; older approvals keep their original shape.
        if destination.get("digest_version", 1) >= 2:
            label = ai_label_for(destination["platform"], destination.get("ai_label"))
            item.update({"digest_version": 2, "ai_label": label["ai_label"], "ai_label_applied_by": label["applied_by"], "variant": platform_variant(video.post_json, destination["platform"])})
            if destination["platform"] == "youtube":
                # Follow-up actions after upload are part of what the owner approves.
                item["post_publish"] = {"captions": (Path(video.output_dir) / "captions.srt").is_file(), "series_playlist": (video.features_json or {}).get("series_id")}
        if destination["platform"] == "facebook_feed":
            # The 4:5 file and its thumbnail are what the owner approves for the feed post.
            feed = feed_variant(video)
            if feed is None:
                raise ApprovalError("facebook_feed_variant_missing")
            item["feed_video_sha256"] = sha256_file(feed["video_path"])
            item["feed_thumbnail_sha256"] = sha256_file(feed["thumbnail_path"])
        if destination["platform"] == "tiktok" and destination.get("tiktok") is not None:
            # Privacy, interaction toggles, commercial disclosure and the consent text the owner saw are approved, like YouTube visibility.
            from app.pipeline.tiktok_post import normalize_post_settings

            item["tiktok"] = normalize_post_settings(destination["tiktok"])
        normalized.append(item)
    normalized.sort(key=lambda item: (item["platform"], item["account"], item["publish_at"] or ""))
    components = {
        "video_sha256": sha256_file(video.video_path),
        "thumbnail_sha256": sha256_file(video.thumbnail_path),
        "artifacts_sha256": artifact_hashes(video),
        "text": video.post_json.get("text", ""),
        "links": sorted(video.post_json.get("links", [])),
        "destinations": normalized,
    }
    if len(normalized) == 1:
        components.update({"platform": normalized[0]["platform"], "account": normalized[0]["account"]})
    return {**components, "approval_sha256": canonical_hash(components)}


def approved_content(review: Review, video: VideoVersion, platform: str, account: str) -> dict:
    """The exact text and AI label the owner approved for this destination."""
    destination = next((item for item in (review.digest_json or {}).get("destinations", []) if item["platform"] == platform and item["account"] == account), None)
    if destination and destination.get("variant"):
        variant = destination["variant"]
        return {"title": variant.get("title") or video.post_json.get("title", ""), "text": variant["text"], "ai_label": destination.get("ai_label"), "digest_version": 2, "post_publish": destination.get("post_publish") or {}, "tiktok": destination.get("tiktok")}
    return {"title": video.post_json.get("title") or video.post_json.get("text", "")[:100], "text": video.post_json.get("text", ""), "ai_label": None, "digest_version": 1, "post_publish": {}, "tiktok": (destination or {}).get("tiktok")}


def approve_destinations(db: Session, video: VideoVersion, reviewer: str, destinations: list[dict], owner_watched_full_video: bool) -> Review:
    if not reviewer.strip():
        raise ApprovalError("owner_reviewer_required")
    if not owner_watched_full_video:
        raise ApprovalError("owner_must_watch_full_video")
    if paused(db):
        raise ApprovalError("emergency_stop_active")
    if video.status != "AWAITING_OWNER":
        raise ApprovalError("video_not_awaiting_owner")
    if uses_rejected_voice(video):
        raise ApprovalError("rejected_voice_not_publishable:kokoro_or_espeak")
    if not destinations:
        raise ApprovalError("destination_required")
    seen = set()
    for destination in destinations:
        _validate_destination(video, destination, seen)
    checks_path = Path(video.output_dir) / "checks.json"
    if not checks_path.exists():
        raise ApprovalError("missing_checks")
    checks = json.loads(checks_path.read_text(encoding="utf-8"))
    for name in ("rights", "technical", "layout", "safety", "quality", "claim_control", "voice", "media_composition"):
        if checks.get(name, {}).get("decision") != "ALLOW":
            raise ApprovalError(f"check_not_allowed:{name}")
    blockers = editorial_blockers(checks) + _affiliate_blockers(video)
    if blockers:
        raise ApprovalError(blockers[0])
    digest = destinations_digest(video, destinations)
    review = Review(video_version_id=video.id, decision="APPROVED", reviewer=reviewer, digest_json=digest, checks_json=checks)
    transition(video, "APPROVED", reviewer)
    db.add(review)
    db.add(AuditEvent(actor=reviewer, action="APPROVED_MULTI_DESTINATION", entity_type="video_version", entity_id=str(video.id), details_json={"approval_sha256": digest["approval_sha256"], "destination_count": len(destinations)}))
    db.commit()
    db.refresh(review)
    return review


def approve_additional_destinations(db: Session, video: VideoVersion, reviewer: str, destinations: list[dict], owner_watched_full_video: bool) -> Review:
    """Add destinations to a video that is already approved and (partly) published, e.g. the 4:5 feed post.

    The new review keeps every earlier destination unchanged and binds the new ones, so the
    published posts stay covered by an approval of the same files and text. Only the new
    destinations get publish jobs (see dispatch.enqueue_publication_jobs ``only``).
    """
    if not reviewer.strip():
        raise ApprovalError("owner_reviewer_required")
    if not owner_watched_full_video:
        raise ApprovalError("owner_must_watch_full_video")
    if paused(db):
        raise ApprovalError("emergency_stop_active")
    if video.status not in {"PUBLISHING", "PUBLISHED"}:
        raise ApprovalError("video_not_published")
    if uses_rejected_voice(video):
        raise ApprovalError("rejected_voice_not_publishable:kokoro_or_espeak")
    current = latest_approval(db, video.id)
    existing = list((current.digest_json or {}).get("destinations") or []) if current else []
    if not existing:
        raise ApprovalError("multi_destination_approval_required")
    if not destinations:
        raise ApprovalError("destination_required")
    if destinations_digest(video, existing)["approval_sha256"] != current.digest_json.get("approval_sha256"):
        raise ApprovalError("approval_invalidated_by_change")
    seen = {(item["platform"], item["account"]) for item in existing}
    for destination in destinations:
        _validate_destination(video, destination, seen)
    blockers = editorial_blockers(current.checks_json or {})
    if blockers:
        raise ApprovalError(blockers[0])
    digest = destinations_digest(video, existing + destinations)
    added = [{"platform": item["platform"], "account": item["account"]} for item in destinations]
    review = Review(video_version_id=video.id, decision="APPROVED", reviewer=reviewer, digest_json={**digest, "supplements_review": current.id, "added_destinations": added}, checks_json=current.checks_json)
    if video.status == "PUBLISHED":
        # The state machine never reopens a published video on its own; an owner-approved extra destination does.
        video.status = "PUBLISHING"
        video.updated_at = utcnow()
    db.add(review)
    db.add(AuditEvent(actor=reviewer, action="APPROVED_ADDITIONAL_DESTINATION", entity_type="video_version", entity_id=str(video.id), details_json={"approval_sha256": digest["approval_sha256"], "added": added, "supplements_review": current.id}))
    db.commit()
    db.refresh(review)
    return review
