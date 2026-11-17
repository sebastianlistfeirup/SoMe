"""YouTube: a rejected custom thumbnail never makes a live upload uncertain; long videos get time to process."""

import argparse

import httpx
import pytest

from app.config import get_settings
from app.db.models import AuditEvent, Publication
from app.pipeline import platforms
from app.pipeline.alerts import collect_alerts
from app.pipeline.approvals import approve
from app.pipeline.platforms import PublishError, YouTubePublisher


class Response:
    def __init__(self, body=None, status_code=200, headers=None):
        self.body = body or {}
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def ready(db, video, monkeypatch, cover_status=200, processing=lambda clock: "succeeded"):
    settings = get_settings()
    monkeypatch.setattr(settings, "dry_run", False)
    monkeypatch.setattr(settings, "publish_enabled", True)
    approve(db, video, "owner", "youtube", "channel", True)
    publisher = YouTubePublisher()
    monkeypatch.setattr(publisher, "_access_token", lambda: "test-token")
    clock = Clock()
    monkeypatch.setattr(platforms.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(platforms.time, "sleep", clock.sleep)
    calls = {"put": 0, "cover": 0}

    def post(url, **kwargs):
        if "thumbnails/set" in url:
            calls["cover"] += 1
            return Response({"error": {"code": cover_status, "errors": [{"reason": "forbidden"}]}} if cover_status >= 400 else {"items": [{}]}, cover_status)
        return Response(headers={"location": "https://upload.example/session"})

    def put(*_args, **_kwargs):
        calls["put"] += 1
        return Response({"id": "yt-1", "status": {"privacyStatus": "public"}})

    monkeypatch.setattr(platforms.httpx, "post", post)
    monkeypatch.setattr(platforms.httpx, "put", put)
    monkeypatch.setattr(platforms.httpx, "get", lambda *_a, **_k: Response({"items": [{"processingDetails": {"processingStatus": processing(clock)}}]}))
    return publisher, calls, clock


def test_rejected_thumbnail_leaves_video_published_with_warning_and_retry(db, awaiting_video, monkeypatch):
    publisher, calls, _clock = ready(db, awaiting_video, monkeypatch, cover_status=403)
    publication = publisher.publish(db, awaiting_video, "channel", "public")
    assert publication.status == "PUBLISHED" and awaiting_video.status == "PUBLISHED"
    assert publication.response_json["cover"] == "custom_thumbnail_failed"
    assert publication.response_json["cover_error"] == "http_403:forbidden"
    assert publication.response_json["cover_retry"].endswith(f"--publication {publication.id}")
    assert calls == {"put": 1, "cover": 1}
    assert db.query(AuditEvent).filter_by(action="YOUTUBE_THUMBNAIL_FAILED").count() == 1
    assert any(alert["code"] == f"youtube_thumbnail:{publication.id}" for alert in collect_alerts(db))
    # Retrying only the thumbnail clears the warning and never uploads the video again.
    monkeypatch.setattr(platforms.httpx, "post", lambda url, **_k: Response({"items": [{}]}))
    assert publisher.set_thumbnail(db, publication, awaiting_video)["cover"] == "custom_thumbnail_set"
    assert "cover_error" not in publication.response_json and calls["put"] == 1
    assert not any(alert["code"].startswith("youtube_thumbnail") for alert in collect_alerts(db))


def test_thumbnail_network_error_is_also_only_a_warning(db, awaiting_video, monkeypatch):
    publisher, _calls, _clock = ready(db, awaiting_video, monkeypatch)

    def post(url, **_kwargs):
        if "thumbnails/set" in url:
            raise httpx.ConnectError("down")
        return Response(headers={"location": "https://upload.example/session"})

    monkeypatch.setattr(platforms.httpx, "post", post)
    publication = publisher.publish(db, awaiting_video, "channel", "public")
    assert publication.status == "PUBLISHED" and publication.response_json["cover_error"] == "ConnectError"


def test_successful_publish_sets_thumbnail(db, awaiting_video, monkeypatch):
    publisher, calls, _clock = ready(db, awaiting_video, monkeypatch)
    publication = publisher.publish(db, awaiting_video, "channel", "public")
    assert publication.response_json["cover"] == "custom_thumbnail_set" and calls["cover"] == 1


def test_long_video_gets_minutes_to_process(db, awaiting_video, monkeypatch):
    publisher, _calls, clock = ready(db, awaiting_video, monkeypatch, processing=lambda clock: "succeeded" if clock.now >= 200 else "processing")
    publication = publisher.publish(db, awaiting_video, "channel", "public")
    assert publication.status == "PUBLISHED" and 200 <= clock.now <= platforms.YOUTUBE_PROCESSING_SECONDS


def test_processing_that_never_finishes_still_requires_reconcile(db, awaiting_video, monkeypatch):
    publisher, calls, clock = ready(db, awaiting_video, monkeypatch, processing=lambda clock: "processing")
    with pytest.raises(PublishError, match="processing_not_finished"):
        publisher.publish(db, awaiting_video, "channel", "public")
    assert db.query(Publication).one().status == "RECONCILE_REQUIRED" and calls["cover"] == 0
    assert clock.now <= platforms.YOUTUBE_PROCESSING_SECONDS


def test_cli_thumbnail_retry_requires_a_published_youtube_publication(db, awaiting_video, monkeypatch):
    from app.cli import run_extended

    publisher, _calls, _clock = ready(db, awaiting_video, monkeypatch, cover_status=403)
    publication = publisher.publish(db, awaiting_video, "channel", "public")
    monkeypatch.setattr(platforms.YouTubePublisher, "_access_token", lambda self: "test-token")
    monkeypatch.setattr(platforms.httpx, "post", lambda url, **_k: Response({"items": [{}]}))
    result = run_extended(db, argparse.Namespace(command="youtube-thumbnail", publication=publication.id))
    assert result["cover"] == "custom_thumbnail_set" and result["remote_id"] == "yt-1"
    with pytest.raises(ValueError, match="published_youtube_publication_required"):
        run_extended(db, argparse.Namespace(command="youtube-thumbnail", publication=999))
    # A changed thumbnail file is not the approved one: refuse.
    with open(awaiting_video.thumbnail_path, "wb") as handle:
        handle.write(b"another image")
    with pytest.raises(Exception, match="approval_invalidated_by_change"):
        run_extended(db, argparse.Namespace(command="youtube-thumbnail", publication=publication.id))
