import httpx
import pytest

from app.config import get_settings
from app.db.models import Publication
from app.pipeline.approvals import approve
from app.pipeline.platforms import PublishError, YouTubePublisher


class StartResponse:
    status_code = 200
    headers = {"location": "https://upload.example/session"}

    def raise_for_status(self):
        return None


def test_upload_timeout_requires_reconciliation(db, awaiting_video, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dry_run", False)
    monkeypatch.setattr(settings, "publish_enabled", True)
    approve(db, awaiting_video, "owner", "youtube", "channel", True)
    publisher = YouTubePublisher()
    monkeypatch.setattr(publisher, "_access_token", lambda: "test-token")
    monkeypatch.setattr("app.pipeline.platforms.httpx.post", lambda *args, **kwargs: StartResponse())

    def timeout(*args, **kwargs):
        raise httpx.TimeoutException("possible upload succeeded")

    monkeypatch.setattr("app.pipeline.platforms.httpx.put", timeout)
    with pytest.raises(PublishError, match="reconcile_required"):
        publisher.publish(db, awaiting_video, "channel", "private")
    publication = db.query(Publication).one()
    assert publication.status == "RECONCILE_REQUIRED"
    assert awaiting_video.status == "RECONCILE_REQUIRED"
    with pytest.raises(PublishError, match="reconcile_required_before_retry"):
        publisher.publish(db, awaiting_video, "channel", "private")


def test_youtube_capabilities_use_verified_connection_state(db):
    from app.db.models import Setting

    db.merge(Setting(key="youtube_connection", value_json={"oauth_verified": True, "private_upload_verified": True, "channel_id": "channel-1"}))
    db.commit()

    result = YouTubePublisher().capabilities(db)

    assert result["oauth_verified"] is True
    assert result["private_upload_verified"] is True
    assert result["channel_id"] == "channel-1"
    assert result["manual_export"] is True
