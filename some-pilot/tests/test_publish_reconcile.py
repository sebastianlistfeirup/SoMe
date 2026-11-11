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


def test_facebook_publish_uses_approved_page_and_signed_https_video(db, awaiting_video, monkeypatch):
    from app.pipeline.platforms import FacebookPublisher

    settings = get_settings()
    for name, value in {
        "dry_run": False,
        "publish_enabled": True,
        "meta_page_access_token": "test-page-token",
        "meta_page_id": "page-1",
        "meta_graph_version": "v27.0",
        "public_base_url": "https://example.com",
    }.items():
        monkeypatch.setattr(settings, name, value)
    approve(db, awaiting_video, "owner", "facebook", "page-1", True)
    monkeypatch.setattr("app.pipeline.platforms.create_link", lambda *_args: "https://example.com/signed-video")

    calls = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "remote-video-1"}

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr("app.pipeline.platforms.httpx.post", post)
    publication = FacebookPublisher().publish(db, awaiting_video, "page-1")

    assert publication.status == "PUBLISHED"
    assert publication.remote_id == "remote-video-1"
    assert calls[0][1]["data"]["url"] == "https://example.com/signed-video"
    assert calls[0][0][0].endswith("/v27.0/page-1/videos")


def test_facebook_graph_error_reports_safe_detail(db, awaiting_video, monkeypatch):
    from app.pipeline.platforms import FacebookPublisher

    settings = get_settings()
    for name, value in {
        "dry_run": False,
        "publish_enabled": True,
        "meta_page_access_token": "test-page-token",
        "meta_page_id": "page-1",
        "meta_graph_version": "v27.0",
        "public_base_url": "https://example.com",
    }.items():
        monkeypatch.setattr(settings, name, value)
    approve(db, awaiting_video, "owner", "facebook", "page-1", True)
    monkeypatch.setattr("app.pipeline.platforms.create_link", lambda *_args: "https://example.com/signed-video")

    class Response:
        status_code = 400

        def json(self):
            return {"error": {"type": "OAuthException", "code": 200, "message": "missing_permission"}}

    monkeypatch.setattr("app.pipeline.platforms.httpx.post", lambda *_args, **_kwargs: Response())

    with pytest.raises(PublishError, match="missing_permission"):
        FacebookPublisher().publish(db, awaiting_video, "page-1")
    assert db.query(Publication).one().status == "FAILED"
