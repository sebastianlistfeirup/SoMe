"""Organic Facebook feed post (native 4:5 render), chosen per video and bound into the approval."""

import json
import re

import httpx
import pytest

from app.config import get_settings
from app.db.models import AuditEvent, AuthUser, Job, Publication, Review, Setting
from app.pipeline import feed_variant as feed_module
from app.pipeline import platforms
from app.pipeline.approvals import ApprovalError, approve_additional_destinations, approve_destinations, destinations_digest, feed_variant, verify_approval
from app.pipeline.dispatch import enqueue_publication_jobs, publish_destination
from app.pipeline.platforms import FacebookPublisher, PublishError

FEED_BYTES = b"feed-4x5-video-bytes"


class Response:
    def __init__(self, body=None, status_code=200):
        self.body = body or {}
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


def render_folder(tmp_path, size=(1080, 1350), duration=10.0, passed=True, fmt="4x5"):
    folder = tmp_path / f"render-{size[0]}x{size[1]}-{duration}-{passed}"
    folder.mkdir()
    (folder / "final.mp4").write_bytes(FEED_BYTES)
    (folder / "thumbnail.jpg").write_bytes(b"feed-thumbnail")
    (folder / "manifest.json").write_text(json.dumps({"format": fmt, "checks": {"pass": passed, "integrated_lufs": -14.0}, "real_media_ratio": 0.92}))
    return folder


def fake_probe(monkeypatch, size=(1080, 1350), duration=10.0, codec="h264"):
    monkeypatch.setattr(feed_module, "probe", lambda _path: {"streams": [{"codec_type": "video", "codec_name": codec, "width": size[0], "height": size[1]}, {"codec_type": "audio"}], "format": {"duration": str(duration)}})


def attached(db, video, monkeypatch, tmp_path):
    video.duration_seconds = 10.4
    video.features_json = {**video.features_json, "aspect_ratio": "9:16"}
    db.commit()
    fake_probe(monkeypatch)
    feed_module.attach_feed_variant(db, video, render_folder(tmp_path))
    return video


def meta_ready(monkeypatch):
    settings = get_settings()
    for name, value in {"dry_run": False, "publish_enabled": True, "meta_page_access_token": "test-page-token", "meta_page_id": "page-1", "meta_graph_version": "v27.0"}.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(platforms.time, "sleep", lambda *_a: None)


def FEED(**extra):
    return {"platform": "facebook_feed", "account": "page-1", "visibility": "public", "publish_at": None, "digest_version": 2, "ai_label": True, **extra}


# --- attaching the 4:5 render -----------------------------------------------------------------


def test_attach_copies_validated_4x5_render_and_records_it(db, awaiting_video, monkeypatch, tmp_path):
    attached(db, awaiting_video, monkeypatch, tmp_path)
    feed = feed_variant(awaiting_video)
    assert feed and feed["aspect_ratio"] == "4:5" and feed["width"] == 1080 and feed["height"] == 1350
    assert open(feed["video_path"], "rb").read() == FEED_BYTES
    assert db.query(AuditEvent).filter_by(action="ATTACH_FEED_VARIANT").count() == 1


@pytest.mark.parametrize("problem, kwargs, error", [
    ("size", {"size": (1080, 1920)}, "feed_render_not_4x5:1080x1920"),
    ("codec", {"codec": "hevc"}, "feed_render_codec_unsupported"),
    ("duration", {"duration": 30.0}, "feed_render_duration_differs_from_video"),
])
def test_attach_refuses_bad_renders(db, awaiting_video, monkeypatch, tmp_path, problem, kwargs, error):
    awaiting_video.duration_seconds = 10.0
    db.commit()
    fake_probe(monkeypatch, **kwargs)
    with pytest.raises(ApprovalError, match=error):
        feed_module.attach_feed_variant(db, awaiting_video, render_folder(tmp_path))
    assert feed_variant(awaiting_video) is None


def test_attach_refuses_failed_checks(db, awaiting_video, monkeypatch, tmp_path):
    fake_probe(monkeypatch)
    with pytest.raises(ApprovalError, match="feed_render_checks_failed"):
        feed_module.attach_feed_variant(db, awaiting_video, render_folder(tmp_path, passed=False))


# --- approval ---------------------------------------------------------------------------------


def test_feed_destination_requires_variant_and_binds_its_files(db, awaiting_video, monkeypatch, tmp_path):
    with pytest.raises(ApprovalError, match="facebook_feed_variant_missing"):
        approve_destinations(db, awaiting_video, "owner", [FEED()], True)
    attached(db, awaiting_video, monkeypatch, tmp_path)
    meta_ready(monkeypatch)
    review = approve_destinations(db, awaiting_video, "owner", [FEED()], True)
    item = review.digest_json["destinations"][0]
    assert item["feed_video_sha256"] == feed_variant(awaiting_video)["video_sha256"]
    assert item["variant"]["platform"] == "facebook_feed"
    assert verify_approval(db, awaiting_video, "facebook_feed", "page-1").id == review.id
    with open(feed_variant(awaiting_video)["video_path"], "wb") as handle:
        handle.write(b"edited after approval")
    with pytest.raises(ApprovalError, match="approval_invalidated_by_change"):
        verify_approval(db, awaiting_video, "facebook_feed", "page-1")
    with pytest.raises(ApprovalError, match="feed_variant_already_approved"):
        feed_module.attach_feed_variant(db, awaiting_video, render_folder(tmp_path, duration=10.1))


# --- publishing -------------------------------------------------------------------------------


def chunked(calls):
    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/thumbnails"):
            return Response({"success": True})
        phase = kwargs["data"]["upload_phase"]
        if phase == "start":
            return Response({"upload_session_id": "s-1", "video_id": "feed-video-1", "start_offset": "0", "end_offset": str(len(FEED_BYTES))})
        if phase == "transfer":
            return Response({"start_offset": str(len(FEED_BYTES)), "end_offset": str(len(FEED_BYTES))})
        return Response({"success": True})

    return post


def test_feed_post_uploads_the_4x5_file_as_page_video_with_thumbnail(db, awaiting_video, monkeypatch, tmp_path):
    attached(db, awaiting_video, monkeypatch, tmp_path)
    meta_ready(monkeypatch)
    review = approve_destinations(db, awaiting_video, "owner", [FEED()], True)
    calls = []
    monkeypatch.setattr(platforms.httpx, "post", chunked(calls))
    result = publish_destination(db, {"video_id": awaiting_video.id, "review_id": review.id, "platform": "facebook_feed", "account": "page-1", "visibility": "public", "publish_at": None})
    assert result["status"] == "PUBLISHED" and result["remote_id"] == "feed-video-1"
    assert all("video_reels" not in url for url, _ in calls), "the 4:5 feed post is never a Reel"
    transfer = next(kwargs for url, kwargs in calls if (kwargs.get("data") or {}).get("upload_phase") == "transfer")
    assert transfer["files"]["video_file_chunk"][1] == FEED_BYTES
    finish = next(kwargs for url, kwargs in calls if (kwargs.get("data") or {}).get("upload_phase") == "finish")
    assert finish["data"]["description"] == review.digest_json["destinations"][0]["variant"]["text"]
    assert calls[-1][0] == "https://graph.facebook.com/v27.0/feed-video-1/thumbnails"
    publication = db.query(Publication).filter_by(platform="facebook_feed").one()
    assert publication.response_json["format"] == "feed_4x5" and publication.response_json["cover"] == "custom_thumbnail_set"


def test_rejected_feed_thumbnail_is_only_a_warning(db, awaiting_video, monkeypatch, tmp_path):
    attached(db, awaiting_video, monkeypatch, tmp_path)
    meta_ready(monkeypatch)
    approve_destinations(db, awaiting_video, "owner", [FEED()], True)
    calls = []
    base = chunked(calls)
    monkeypatch.setattr(platforms.httpx, "post", lambda url, **kw: Response({"error": {"type": "OAuthException", "code": 100, "message": "bad image"}}, 400) if url.endswith("/thumbnails") else base(url, **kw))
    publication = FacebookPublisher().publish_feed(db, awaiting_video, "page-1")
    assert publication.status == "PUBLISHED" and publication.response_json["cover"] == "custom_thumbnail_failed"
    assert "bad image" in publication.response_json["cover_error"]


# --- adding the feed post to an already published video ----------------------------------------


def published_with_reel(db, video, monkeypatch, tmp_path):
    attached(db, video, monkeypatch, tmp_path)
    meta_ready(monkeypatch)
    review = approve_destinations(db, video, "owner", [{"platform": "facebook", "account": "page-1", "visibility": "public", "publish_at": None, "digest_version": 2, "ai_label": True}], True)
    db.add(Publication(video_version_id=video.id, platform="facebook", account="page-1", idempotency_key=f"video:{video.id}:platform:facebook:account:page-1", status="PUBLISHED", remote_id="reel-1", response_json={"format": "reel"}))
    video.status = "PUBLISHED"
    db.commit()
    return review


def test_feed_can_be_added_to_published_video_without_touching_existing_posts(db, awaiting_video, monkeypatch, tmp_path):
    first = published_with_reel(db, awaiting_video, monkeypatch, tmp_path)
    review = approve_additional_destinations(db, awaiting_video, "owner", [FEED()], True)
    assert review.digest_json["supplements_review"] == first.id
    assert {item["platform"] for item in review.digest_json["destinations"]} == {"facebook", "facebook_feed"}
    assert awaiting_video.status == "PUBLISHING"
    jobs = enqueue_publication_jobs(db, review, only=[FEED()])
    assert [job.payload["platform"] for job in jobs] == ["facebook_feed"]
    assert verify_approval(db, awaiting_video, "facebook", "page-1").id == review.id  # old post still covered
    calls = []
    monkeypatch.setattr(platforms.httpx, "post", chunked(calls))
    publish_destination(db, jobs[0].payload)
    assert awaiting_video.status == "PUBLISHED"
    assert db.query(Publication).filter_by(status="PUBLISHED").count() == 2
    with pytest.raises(ApprovalError, match="duplicate_destination"):
        approve_additional_destinations(db, awaiting_video, "owner", [FEED()], True)


def test_adding_destination_requires_watch_unchanged_files_and_a_published_video(db, awaiting_video, monkeypatch, tmp_path):
    with pytest.raises(ApprovalError, match="video_not_published"):
        approve_additional_destinations(db, awaiting_video, "owner", [FEED()], True)
    published_with_reel(db, awaiting_video, monkeypatch, tmp_path)
    with pytest.raises(ApprovalError, match="owner_must_watch_full_video"):
        approve_additional_destinations(db, awaiting_video, "owner", [FEED()], False)
    with open(awaiting_video.video_path, "wb") as handle:
        handle.write(b"changed main video")
    with pytest.raises(ApprovalError, match="approval_invalidated_by_change"):
        approve_additional_destinations(db, awaiting_video, "owner", [FEED()], True)


# --- review page ------------------------------------------------------------------------------


def _client(db):
    from argon2 import PasswordHasher
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    db.add(AuthUser(username="owner", password_hash=PasswordHasher().hash("a-secure-test-password")))
    db.add(Setting(key="meta_connection", value_json={"facebook_page_id": "page-1", "facebook_page_name": "Pixel and Parameters"}))
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://testserver")
    assert client.post("/login", data={"username": "owner", "password": "a-secure-test-password"}, follow_redirects=False).status_code == 303
    return app, client


def test_review_page_offers_feed_per_video_unchecked(db, awaiting_video, monkeypatch, tmp_path):
    app, client = _client(db)
    try:
        page = client.get(f"/review/{awaiting_video.id}").text
        assert re.search(r'value="facebook_feed"\s*\s+disabled', page) and "4:5-version mangler" in page
        attached(db, awaiting_video, monkeypatch, tmp_path)
        page = client.get(f"/review/{awaiting_video.id}").text
        feed_input = re.search(r'<input type="checkbox" name="platforms" value="facebook_feed"[^>]*>', page).group(0)
        assert "disabled" not in feed_input and "checked" not in feed_input
        assert "Facebook Reel" in page and f"/media/{awaiting_video.id}/feed_4x5.mp4" in page
        assert client.get(f"/media/{awaiting_video.id}/feed_4x5.mp4").content == FEED_BYTES
    finally:
        app.dependency_overrides.clear()


def test_add_destination_route_queues_only_the_feed_post(db, awaiting_video, monkeypatch, tmp_path):
    published_with_reel(db, awaiting_video, monkeypatch, tmp_path)
    app, client = _client(db)
    try:
        page = client.get(f"/review/{awaiting_video.id}").text
        assert "Læg den også i Facebook-feedet" in page
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        response = client.post(f"/review/{awaiting_video.id}/add-destination", data={"csrf_token": token, "platforms": "facebook_feed", "watched": "true", "ai_labels": "facebook_feed"}, follow_redirects=False)
        assert response.status_code == 303
        jobs = db.query(Job).filter_by(kind="publish").all()
        assert [job.payload["platform"] for job in jobs] == ["facebook_feed"]
        assert db.query(Review).filter_by(decision="APPROVED").count() == 2
        refused = client.post(f"/review/{awaiting_video.id}/add-destination", data={"csrf_token": token, "platforms": "youtube", "watched": "true"}, follow_redirects=False)
        assert refused.status_code == 409 and "only_facebook_feed" in refused.text
    finally:
        app.dependency_overrides.clear()
