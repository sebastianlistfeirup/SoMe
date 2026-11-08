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
