"""Facebook resumable chunked upload and Instagram's long container poll + container reconcile."""

import httpx
import pytest

from app.config import get_settings
from app.db.models import AuditEvent, Publication
from app.pipeline import platforms
from app.pipeline.approvals import approve
from app.pipeline.platforms import FacebookPublisher, InstagramPublisher, PublishError


class Response:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code
        self.headers = {}

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


def facebook_ready(db, video, monkeypatch, payload=b"0123456789", aspect="16:9"):
    settings = get_settings()
    video.features_json = {**(video.features_json or {}), "aspect_ratio": aspect}
    db.commit()
    for name, value in {"dry_run": False, "publish_enabled": True, "meta_page_access_token": "test-page-token", "meta_page_id": "page-1", "meta_graph_version": "v27.0"}.items():
        monkeypatch.setattr(settings, name, value)
    with open(video.video_path, "wb") as handle:
        handle.write(payload)
    approve(db, video, "owner", "facebook", "page-1", True)
    monkeypatch.setattr(platforms.time, "sleep", lambda *_a: None)


def chunked_graph(calls, size, chunk=4, finish=None, transfer_errors=()):
    errors = list(transfer_errors)

    def post(url, **kwargs):
        calls.append((url, kwargs))
        phase = kwargs["data"]["upload_phase"]
        if phase == "start":
            return Response({"upload_session_id": "session-1", "video_id": "fb-video-1", "start_offset": "0", "end_offset": str(min(chunk, size))})
        if phase == "transfer":
            if errors:
                raise errors.pop(0)
            start = int(kwargs["data"]["start_offset"]) + len(kwargs["files"]["video_file_chunk"][1])
            return Response({"start_offset": str(start), "end_offset": str(min(start + chunk, size))})
        return finish(kwargs) if finish else Response({"success": True})

    return post


def test_facebook_uploads_large_video_in_resumable_chunks(db, awaiting_video, monkeypatch):
    payload = b"0123456789"
    facebook_ready(db, awaiting_video, monkeypatch, payload)
    calls = []
    monkeypatch.setattr(platforms.httpx, "post", chunked_graph(calls, len(payload)))
    publication = FacebookPublisher().publish(db, awaiting_video, "page-1")
    assert publication.status == "PUBLISHED" and publication.remote_id == "fb-video-1"
    phases = [call[1]["data"]["upload_phase"] for call in calls]
    assert phases == ["start", "transfer", "transfer", "transfer", "finish"]
    assert all(call[0] == "https://graph-video.facebook.com/v27.0/page-1/videos" for call in calls)
    assert calls[0][1]["data"]["file_size"] == "10"
    assert b"".join(call[1]["files"]["video_file_chunk"][1] for call in calls[1:4]) == payload
    assert calls[-1][1]["data"]["description"] and calls[-1][1]["data"]["upload_session_id"] == "session-1"
    assert publication.response_json["chunks"] == 3 and awaiting_video.status == "PUBLISHED"


def test_facebook_retries_a_timed_out_chunk(db, awaiting_video, monkeypatch):
    facebook_ready(db, awaiting_video, monkeypatch)
    calls = []
    monkeypatch.setattr(platforms.httpx, "post", chunked_graph(calls, 10, transfer_errors=[httpx.ReadTimeout("slow")]))
    assert FacebookPublisher().publish(db, awaiting_video, "page-1").status == "PUBLISHED"


def test_facebook_failure_before_finish_is_failed_and_retryable(db, awaiting_video, monkeypatch):
    facebook_ready(db, awaiting_video, monkeypatch)
    calls = []
    errors = [httpx.ReadTimeout("slow")] * 3
    monkeypatch.setattr(platforms.httpx, "post", chunked_graph(calls, 10, transfer_errors=errors))
    with pytest.raises(PublishError, match="facebook_chunk_transfer_failed"):
        FacebookPublisher().publish(db, awaiting_video, "page-1")
    publication = db.query(Publication).one()
    assert publication.status == "FAILED" and publication.remote_id is None


def test_facebook_unreadable_error_is_reported_with_status(db, awaiting_video, monkeypatch):
    facebook_ready(db, awaiting_video, monkeypatch)
    monkeypatch.setattr(platforms.httpx, "post", lambda *_a, **_k: Response(ValueError("html"), 413))
    with pytest.raises(PublishError, match="facebook_graph_error:start:unreadable_graph_error:http_413"):
        FacebookPublisher().publish(db, awaiting_video, "page-1")
    assert db.query(Publication).one().status == "FAILED"


def test_facebook_timeout_at_finish_requires_reconcile(db, awaiting_video, monkeypatch):
    facebook_ready(db, awaiting_video, monkeypatch)

    def finish(_kwargs):
        raise httpx.ReadTimeout("maybe published")

    monkeypatch.setattr(platforms.httpx, "post", chunked_graph([], 10, finish=finish))
    with pytest.raises(PublishError, match="facebook_reconcile_required"):
        FacebookPublisher().publish(db, awaiting_video, "page-1")
    assert db.query(Publication).one().status == "RECONCILE_REQUIRED"
    assert awaiting_video.status == "RECONCILE_REQUIRED"


def instagram_ready(db, video, monkeypatch):
    settings = get_settings()
    for name, value in {"dry_run": False, "publish_enabled": True, "meta_access_token": "token", "meta_instagram_account_id": "instagram-1", "meta_graph_version": "v27.0", "public_base_url": "https://example.com"}.items():
        monkeypatch.setattr(settings, name, value)
    approve(db, video, "owner", "instagram", "instagram-1", True)
    monkeypatch.setattr("app.pipeline.platforms.create_link", lambda *_a, asset="video": f"https://example.com/{asset}")


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_instagram_waits_minutes_with_backoff_for_container(db, awaiting_video, monkeypatch):
    instagram_ready(db, awaiting_video, monkeypatch)
    clock = Clock()
    monkeypatch.setattr(platforms.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(platforms.time, "sleep", clock.sleep)
    monkeypatch.setattr(platforms.httpx, "post", lambda url, **_k: Response({"id": "media-1" if "media_publish" in url else "container-1"}))
    # FINISHED only after ~4 minutes; the old 60 s window gave up here.
    monkeypatch.setattr(platforms.httpx, "get", lambda *_a, **_k: Response({"status_code": "FINISHED" if clock.now >= 240 else "IN_PROGRESS"}))
    publication = InstagramPublisher().publish(db, awaiting_video, "instagram-1")
    assert publication.status == "PUBLISHED" and publication.remote_id == "media-1"
    assert clock.sleeps[0] == 2.0 and max(clock.sleeps) == platforms.INSTAGRAM_POLL_MAX_DELAY
    assert 240 <= clock.now <= platforms.INSTAGRAM_POLL_SECONDS


def test_instagram_poll_window_ends_in_reconcile_then_retry_publishes_existing_container(db, awaiting_video, monkeypatch):
    instagram_ready(db, awaiting_video, monkeypatch)
    clock = Clock()
    monkeypatch.setattr(platforms.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(platforms.time, "sleep", clock.sleep)
    posts = []

    def post(url, **kwargs):
        posts.append(url)
        return Response({"id": "media-1" if "media_publish" in url else "container-1"})

    monkeypatch.setattr(platforms.httpx, "post", post)
    status = {"value": "IN_PROGRESS"}
    monkeypatch.setattr(platforms.httpx, "get", lambda *_a, **_k: Response({"status_code": status["value"]}))
    with pytest.raises(PublishError, match="instagram_reconcile_required"):
        InstagramPublisher().publish(db, awaiting_video, "instagram-1")
    publication = db.query(Publication).one()
    assert publication.status == "RECONCILE_REQUIRED" and publication.upload_session == "container-1"
    assert clock.now <= platforms.INSTAGRAM_POLL_SECONDS
    status["value"] = "FINISHED"
    result = InstagramPublisher().publish(db, awaiting_video, "instagram-1")
    assert result.status == "PUBLISHED" and result.remote_id == "media-1" and awaiting_video.status == "PUBLISHED"
    assert sum("/media_publish" in url for url in posts) == 1 and sum(url.endswith("/media") for url in posts) == 1
    assert db.query(AuditEvent).filter_by(action="PUBLICATION_RECONCILED").count() == 1


def test_instagram_reconcile_never_republishes_a_published_container(db, awaiting_video, monkeypatch):
    instagram_ready(db, awaiting_video, monkeypatch)
    monkeypatch.setattr(platforms.time, "sleep", lambda *_a: None)
    publication = Publication(video_version_id=awaiting_video.id, platform="instagram", account="instagram-1", idempotency_key=f"video:{awaiting_video.id}:platform:instagram:account:instagram-1", status="RECONCILE_REQUIRED", upload_session="container-9")
    awaiting_video.status = "RECONCILE_REQUIRED"
    db.add(publication)
    db.commit()
    monkeypatch.setattr(platforms.httpx, "post", lambda *_a, **_k: pytest.fail("must not publish again"))
    monkeypatch.setattr(platforms.httpx, "get", lambda *_a, **_k: Response({"status_code": "PUBLISHED"}))
    with pytest.raises(PublishError, match="already_published_manual_reconcile"):
        InstagramPublisher().publish(db, awaiting_video, "instagram-1")
    assert db.get(Publication, publication.id).status == "RECONCILE_REQUIRED"


def test_instagram_expired_container_is_failed_so_a_retry_starts_fresh(db, awaiting_video, monkeypatch):
    instagram_ready(db, awaiting_video, monkeypatch)
    publication = Publication(video_version_id=awaiting_video.id, platform="instagram", account="instagram-1", idempotency_key=f"video:{awaiting_video.id}:platform:instagram:account:instagram-1", status="RECONCILE_REQUIRED", upload_session="container-9")
    awaiting_video.status = "RECONCILE_REQUIRED"
    db.add(publication)
    db.commit()
    monkeypatch.setattr(platforms.httpx, "get", lambda *_a, **_k: Response({"status_code": "EXPIRED"}))
    with pytest.raises(PublishError, match="instagram_container_expired"):
        InstagramPublisher().publish(db, awaiting_video, "instagram-1")
    assert db.get(Publication, publication.id).status == "FAILED"


# --- Facebook Reels for 9:16 (owner rule 13) ---------------------------------------------------


def reel_graph(calls, finish_success=True, upload_status=200):
    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.startswith("https://rupload.facebook.com/"):
            return Response({"success": True} if upload_status < 400 else {"error": {"message": "bad"}}, upload_status)
        phase = kwargs["data"]["upload_phase"]
        if phase == "start":
            return Response({"video_id": "reel-1", "upload_url": "https://rupload.facebook.com/video-upload/v27.0/reel-1"})
        return Response({"success": finish_success})

    return post


def test_vertical_video_is_published_as_facebook_reel(db, awaiting_video, monkeypatch):
    facebook_ready(db, awaiting_video, monkeypatch, aspect="9:16")
    calls, polls = [], []
    monkeypatch.setattr(platforms.httpx, "post", reel_graph(calls))
    states = [{"video_status": "processing", "publishing_phase": {"status": "in_progress"}}, {"video_status": "ready", "publishing_phase": {"status": "complete"}}]

    def get(url, **kwargs):
        polls.append((url, kwargs))
        return Response({"status": states.pop(0)})

    monkeypatch.setattr(platforms.httpx, "get", get)
    publication = FacebookPublisher().publish(db, awaiting_video, "page-1")
    assert publication.status == "PUBLISHED" and publication.remote_id == "reel-1"
    assert publication.response_json["format"] == "reel"
    assert calls[0][0] == "https://graph.facebook.com/v27.0/page-1/video_reels" and calls[0][1]["data"] == {"upload_phase": "start"}
    upload = calls[1]
    assert upload[0] == "https://rupload.facebook.com/video-upload/v27.0/reel-1"
    assert upload[1]["headers"]["Authorization"] == "OAuth test-page-token"
    assert upload[1]["headers"]["offset"] == "0" and upload[1]["headers"]["file_size"] == "10"
    finish = calls[2][1]["data"]
    assert finish["upload_phase"] == "finish" and finish["video_id"] == "reel-1" and finish["video_state"] == "PUBLISHED" and finish["description"]
    assert not any("/videos" in call[0] for call in calls), "a 9:16 video must never be a regular page video"
    assert polls[0][1]["params"] == {"fields": "status"}


def test_reel_upload_failure_before_finish_is_failed(db, awaiting_video, monkeypatch):
    facebook_ready(db, awaiting_video, monkeypatch, aspect="9:16")
    calls = []
    monkeypatch.setattr(platforms.httpx, "post", reel_graph(calls, upload_status=500))
    with pytest.raises(PublishError, match="reel_upload"):
        FacebookPublisher().publish(db, awaiting_video, "page-1")
    assert db.query(Publication).one().status == "FAILED"
    assert not any(call[1].get("data", {}).get("upload_phase") == "finish" for call in calls if "data" in call[1])


def test_reel_not_confirmed_after_finish_requires_reconcile(db, awaiting_video, monkeypatch):
    facebook_ready(db, awaiting_video, monkeypatch, aspect="9:16")
    clock = Clock()
    monkeypatch.setattr(platforms.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(platforms.time, "sleep", clock.sleep)
    monkeypatch.setattr(platforms.httpx, "post", reel_graph([]))
    monkeypatch.setattr(platforms.httpx, "get", lambda *_a, **_k: Response({"status": {"video_status": "processing", "publishing_phase": {"status": "in_progress"}}}))
    with pytest.raises(PublishError, match="facebook_reel_not_confirmed_reconcile"):
        FacebookPublisher().publish(db, awaiting_video, "page-1")
    publication = db.query(Publication).one()
    assert publication.status == "RECONCILE_REQUIRED" and publication.remote_id == "reel-1"
    assert clock.now <= platforms.FACEBOOK_REEL_POLL_SECONDS


def test_unknown_aspect_falls_back_to_probe_and_never_guesses(db, awaiting_video, monkeypatch):
    facebook_ready(db, awaiting_video, monkeypatch)
    awaiting_video.features_json = {"is_demo": True}
    db.commit()
    monkeypatch.setattr("app.pipeline.media.probe", lambda _path: {"streams": [{"codec_type": "video", "width": 1080, "height": 1920}]})
    assert platforms.is_vertical(awaiting_video) is True

    def broken(_path):
        raise RuntimeError("ffprobe failed")

    monkeypatch.setattr("app.pipeline.media.probe", broken)
    monkeypatch.setattr(platforms.httpx, "post", lambda *_a, **_k: pytest.fail("must not upload with an unknown format"))
    with pytest.raises(PublishError, match="facebook_video_aspect_unknown"):
        FacebookPublisher().publish(db, awaiting_video, "page-1")
    assert db.query(Publication).count() == 0


# --- owner-approved replacement of 9:16 page videos with Reels ------------------------------------


def published_page_video(db, video, monkeypatch):
    facebook_ready(db, video, monkeypatch, aspect="9:16")
    video.status = "PUBLISHED"
    old = Publication(video_version_id=video.id, platform="facebook", account="page-1", idempotency_key=f"video:{video.id}:platform:facebook:account:page-1", status="PUBLISHED", remote_id="old-page-video", response_json={"id": "old-page-video", "cover": "source_frame"})
    db.add(old)
    db.commit()
    return old


def reel_ok(monkeypatch):
    monkeypatch.setattr(platforms.httpx, "get", lambda *_a, **_k: Response({"status": {"video_status": "ready", "publishing_phase": {"status": "complete"}}}))


def test_replace_publishes_reel_first_then_deletes_old_post(db, awaiting_video, monkeypatch):
    old = published_page_video(db, awaiting_video, monkeypatch)
    order = []

    def post(url, **kwargs):
        order.append("reel:" + (kwargs.get("data") or {}).get("upload_phase", "upload"))
        return reel_graph([])(url, **kwargs)

    def delete(url, **kwargs):
        order.append("delete")
        assert url.endswith("/old-page-video") and kwargs["headers"]["Authorization"] == "Bearer test-page-token"
        return Response({"success": True})

    monkeypatch.setattr(platforms.httpx, "post", post)
    monkeypatch.setattr(platforms.httpx, "delete", delete)
    reel_ok(monkeypatch)
    dry = FacebookPublisher().replace_with_reel(db, old)
    assert dry["executed"] is False and order == []
    result = FacebookPublisher().replace_with_reel(db, old, execute=True)
    assert order == ["reel:start", "reel:upload", "reel:finish", "delete"]
    assert result["executed"] and result["reel_remote_id"] == "reel-1"
    db.refresh(old)
    assert old.status == "REPLACED" and old.response_json["replaced_by_remote_id"] == "reel-1"
    reel = db.get(Publication, result["reel_publication_id"])
    assert reel.status == "PUBLISHED" and reel.idempotency_key == f"video:{awaiting_video.id}:platform:facebook:account:page-1"
    assert db.query(AuditEvent).filter_by(action="FACEBOOK_PAGE_VIDEO_REPLACED_WITH_REEL").count() == 1
    assert awaiting_video.status == "PUBLISHED"
    with pytest.raises(PublishError, match="published_facebook_publication_required"):
        FacebookPublisher().replace_with_reel(db, old, execute=True)


def test_replace_keeps_old_post_when_reel_fails_and_rerun_continues(db, awaiting_video, monkeypatch):
    old = published_page_video(db, awaiting_video, monkeypatch)
    monkeypatch.setattr(platforms.httpx, "post", reel_graph([], upload_status=500))
    monkeypatch.setattr(platforms.httpx, "delete", lambda *_a, **_k: pytest.fail("old post must stay while the reel is not live"))
    with pytest.raises(PublishError):
        FacebookPublisher().replace_with_reel(db, old, execute=True)
    db.refresh(old)
    assert old.status == "REPLACING" and old.remote_id == "old-page-video"
    deleted = []
    monkeypatch.setattr(platforms.httpx, "post", reel_graph([]))
    monkeypatch.setattr(platforms.httpx, "delete", lambda url, **_k: deleted.append(url) or Response({"success": True}))
    reel_ok(monkeypatch)
    result = FacebookPublisher().replace_with_reel(db, old, execute=True)
    assert result["executed"] and len(deleted) == 1
    assert db.query(Publication).filter_by(platform="facebook", status="PUBLISHED").count() == 1


def test_replace_reports_failed_delete_and_rerun_only_retries_delete(db, awaiting_video, monkeypatch):
    old = published_page_video(db, awaiting_video, monkeypatch)
    calls = []
    monkeypatch.setattr(platforms.httpx, "post", reel_graph(calls))
    reel_ok(monkeypatch)
    monkeypatch.setattr(platforms.httpx, "delete", lambda *_a, **_k: Response({"error": {"type": "OAuthException", "code": 200, "message": "no permission"}}, 403))
    with pytest.raises(PublishError, match="old_post_delete_failed"):
        FacebookPublisher().replace_with_reel(db, old, execute=True)
    db.refresh(old)
    assert old.status == "REPLACING" and "no permission" in old.error_code
    uploads = len(calls)
    monkeypatch.setattr(platforms.httpx, "delete", lambda *_a, **_k: Response({"success": True}))
    FacebookPublisher().replace_with_reel(db, old, execute=True)
    assert len(calls) == uploads, "the reel must not be uploaded twice"
    db.refresh(old)
    assert old.status == "REPLACED"


def test_replace_refuses_landscape_videos(db, awaiting_video, monkeypatch):
    old = published_page_video(db, awaiting_video, monkeypatch)
    awaiting_video.features_json = {**awaiting_video.features_json, "aspect_ratio": "16:9"}
    db.commit()
    with pytest.raises(PublishError, match="only_9x16"):
        FacebookPublisher().replace_with_reel(db, old, execute=True)
