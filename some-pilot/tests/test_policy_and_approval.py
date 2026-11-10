from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.db.models import Asset, License, Setting
from app.pipeline.approvals import ApprovalError, approve, invalidate_approval, set_pause, transition, verify_approval
from app.pipeline.platforms import new_publication
from app.pipeline.policy import Decision, content_policy, rights_policy


def asset_with_license(db, **overrides):
    asset = Asset(path="synthetic", rights_status=overrides.pop("rights_status", "CLEARED"), sha256="a" * 64, bytes=1, media_type="image/png")
    db.add(asset)
    db.flush()
    values = dict(asset_id=asset.id, rights_holder="owner", license_text="own work", source_url="synthetic", commercial_allowed=True, derivative_allowed=True, platforms_json=["youtube"], territories_json=["global"], age_clearance="NO_PEOPLE", status="ALLOW")
    values.update(overrides)
    db.add(License(**values))
    db.commit()
    return asset


def test_unknown_and_expired_license_block(db):
    unknown = Asset(path="unknown", rights_status="UNKNOWN", sha256="b" * 64, bytes=1, media_type="image/png")
    db.add(unknown)
    db.commit()
    assert rights_policy(db, [unknown.id], "youtube").decision == Decision.BLOCK
    expired = asset_with_license(db, expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    assert "license_expired" in rights_policy(db, [expired.id], "youtube").reasons[0]


def test_duration_never_bypasses_rights(db):
    unknown = Asset(path="five-second-clip", rights_status="UNKNOWN", sha256="c" * 64, bytes=1, media_type="video/mp4", metadata_json={"duration_seconds": 5})
    db.add(unknown)
    db.commit()
    assert rights_policy(db, [unknown.id], "youtube").decision == Decision.BLOCK


def test_minor_and_unknown_age_rules(db):
    assert content_policy("A child appears in this clip").decision == Decision.BLOCK
    assert content_policy("A product demonstration", contains_people=True).decision == Decision.REVIEW
    unclear = asset_with_license(db, age_clearance="UNKNOWN")
    assert rights_policy(db, [unclear.id], "youtube").decision == Decision.REVIEW


def test_owner_approval_and_hash_invalidation(db, awaiting_video, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dry_run", False)
    monkeypatch.setattr(settings, "publish_enabled", True)
    review = approve(db, awaiting_video, "owner", "youtube", "channel-1", True)
    assert review.digest_json["approval_sha256"]
    assert verify_approval(db, awaiting_video, "youtube", "channel-1").id == review.id
    with pytest.raises(ApprovalError, match="approval_invalidated"):
        verify_approval(db, awaiting_video, "youtube", "other-channel")
    with open(awaiting_video.video_path, "ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ApprovalError, match="approval_invalidated"):
        verify_approval(db, awaiting_video, "youtube", "channel-1")


def test_text_change_requires_new_approval(db, awaiting_video):
    approve(db, awaiting_video, "owner", "youtube", "channel-1", True)
    awaiting_video.post_json = {"text": "changed", "links": []}
    invalidate_approval(db, awaiting_video, "owner")
    assert awaiting_video.status == "AWAITING_OWNER"


def test_watch_requirement_and_invalid_transition(db, awaiting_video):
    with pytest.raises(ApprovalError, match="owner_must_watch"):
        approve(db, awaiting_video, "owner", "youtube", "channel-1", False)
    with pytest.raises(ApprovalError, match="invalid_transition"):
        transition(awaiting_video, "PUBLISHED")


def test_voice_check_is_required_for_approval(db, awaiting_video):
    import json
    from pathlib import Path
    checks_path = Path(awaiting_video.output_dir) / "checks.json"
    checks = json.loads(checks_path.read_text())
    checks.pop("voice")
    checks_path.write_text(json.dumps(checks))
    with pytest.raises(ApprovalError, match="check_not_allowed:voice"):
        approve(db, awaiting_video, "owner", "youtube", "channel-1", True)


def test_global_publish_flag_and_pause_block_every_route(db, awaiting_video, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dry_run", True)
    monkeypatch.setattr(settings, "publish_enabled", False)
    approve(db, awaiting_video, "owner", "youtube", "channel-1", True)
    with pytest.raises(ApprovalError, match="publishing_disabled"):
        new_publication(db, awaiting_video, "youtube", "channel-1")
    monkeypatch.setattr(settings, "dry_run", False)
    monkeypatch.setattr(settings, "publish_enabled", True)
    set_pause(db, True, "owner")
    with pytest.raises(ApprovalError, match="emergency_stop"):
        new_publication(db, awaiting_video, "youtube", "channel-1")
