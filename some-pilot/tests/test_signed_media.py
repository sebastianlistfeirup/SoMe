import pytest

from app.pipeline.approvals import approve
from app.pipeline.signed_media import SignedMediaError, create_link, resolve_link


def test_signed_media_requires_current_approval_and_valid_signature(db, awaiting_video):
    with pytest.raises(SignedMediaError, match="not_approved"):
        create_link(db, awaiting_video, "instagram", "account")
    approve(db, awaiting_video, "owner", "instagram", "account", True)
    link = create_link(db, awaiting_video, "instagram", "account")
    token = link.rsplit("/", 1)[-1]
    assert resolve_link(db, token).name == "video.mp4"
    with pytest.raises(SignedMediaError):
        resolve_link(db, token[:-1] + "x")


def test_signed_media_invalidated_by_content_change(db, awaiting_video):
    approve(db, awaiting_video, "owner", "instagram", "account", True)
    token = create_link(db, awaiting_video, "instagram", "account").rsplit("/", 1)[-1]
    with open(awaiting_video.video_path, "ab") as handle:
        handle.write(b"changed")
    with pytest.raises(SignedMediaError, match="approval_changed|invalid_or_expired"):
        resolve_link(db, token)


def test_multi_approval_signs_exact_thumbnail_and_detects_change(db, awaiting_video, monkeypatch):
    from app.config import get_settings
    from app.pipeline.approvals import approve_destinations

    monkeypatch.setattr(get_settings(), "dry_run", False)
    monkeypatch.setattr(get_settings(), "publish_enabled", True)
    approve_destinations(db, awaiting_video, "owner", [{"platform": "instagram", "account": "account", "visibility": "public", "publish_at": None}], True)
    token = create_link(db, awaiting_video, "instagram", "account", asset="thumbnail").rsplit("/", 1)[-1]
    assert resolve_link(db, token).name == "thumbnail.jpg"
    with open(awaiting_video.thumbnail_path, "ab") as handle:
        handle.write(b"changed")
    with pytest.raises(SignedMediaError, match="approval_changed|invalid_or_expired"):
        resolve_link(db, token)


def test_signed_media_rejects_unknown_asset(db, awaiting_video):
    approve(db, awaiting_video, "owner", "instagram", "account", True)
    with pytest.raises(SignedMediaError, match="unsupported_media_asset"):
        create_link(db, awaiting_video, "instagram", "account", asset="script")
