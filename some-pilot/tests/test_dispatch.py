from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.db.models import Review, VideoVersion
from app.pipeline.approvals import approve_destinations, verify_approval
from app.pipeline.dispatch import enqueue_publication_jobs, normalize_publish_at, publish_destination
from app.pipeline.jobs import claim
from app.pipeline.platforms import _mark_success, new_publication
from app.worker import execute


DESTINATIONS = [
    {"platform": "youtube", "account": "channel-1", "visibility": "private", "publish_at": None},
    {"platform": "instagram", "account": "instagram-1", "visibility": "public", "publish_at": None},
    {"platform": "facebook", "account": "page-1", "visibility": "public", "publish_at": None},
    {"platform": "tiktok", "account": "open-id-1", "visibility": "public", "publish_at": None},
]


def enable_publishing(monkeypatch):
    monkeypatch.setattr(get_settings(), "dry_run", False)
    monkeypatch.setattr(get_settings(), "publish_enabled", True)


def test_multi_approval_creates_four_unique_jobs_and_binds_payload(db, awaiting_video, monkeypatch):
    enable_publishing(monkeypatch)
    review = approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    jobs = enqueue_publication_jobs(db, review)
    assert len(jobs) == 4
    assert {job.payload["platform"] for job in jobs} == {"youtube", "instagram", "facebook", "tiktok"}
    assert review.digest_json["approval_sha256"]
    assert verify_approval(db, awaiting_video, "youtube", "channel-1").id == review.id
    assert len(enqueue_publication_jobs(db, review)) == 4
    assert db.query(Review).count() == 1
    with pytest.raises(Exception, match="approval_destination_mismatch"):
        verify_approval(db, awaiting_video, "youtube", "other-account")


def test_rejection_does_not_create_publication_job(db, awaiting_video):
    review = Review(video_version_id=awaiting_video.id, decision="REJECTED", reviewer="owner")
    db.add(review)
    db.commit()
    jobs = enqueue_publication_jobs(db, review)
    assert jobs == []


def test_each_destination_finishes_only_after_all_selected_are_complete(db, awaiting_video, monkeypatch):
    enable_publishing(monkeypatch)
    approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    expected = []
    for destination in DESTINATIONS:
        publication = new_publication(db, awaiting_video, destination["platform"], destination["account"])
        publication.status = "PUBLISHED"
        publication.remote_id = destination["platform"] + "-post"
        _mark_success(db, publication, awaiting_video)
        expected.append(publication.status)
        if destination["platform"] != "tiktok":
            assert awaiting_video.status == "PUBLISHING"
        else:
            assert awaiting_video.status == "PUBLISHED"
    assert len(expected) == 4


def test_worker_publishes_each_destination_with_idempotent_payload(db, awaiting_video, monkeypatch):
    enable_publishing(monkeypatch)
    review = approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    enqueue_publication_jobs(db, review)
    calls = []

    class Publisher:
        def __init__(self, platform):
            self.platform = platform

        def publish(self, db, video, account, *args):
            calls.append(self.platform)
            return SimpleNamespace(id=len(calls), status="PUBLISHED", remote_id=self.platform + "-post", response_json={})

    monkeypatch.setattr("app.pipeline.dispatch.YouTubePublisher", lambda: Publisher("youtube"))
    monkeypatch.setattr("app.pipeline.dispatch.InstagramPublisher", lambda: Publisher("instagram"))
    monkeypatch.setattr("app.pipeline.dispatch.FacebookPublisher", lambda: Publisher("facebook"))
    monkeypatch.setattr("app.pipeline.dispatch.TikTokPublisher", lambda: Publisher("tiktok"))
    for _ in range(4):
        job = claim(db, "publish-test")
        path = execute(db, job)
        assert path.exists()
    assert set(calls) == {"youtube", "instagram", "facebook", "tiktok"}


def test_superseded_approval_is_rejected_before_dispatch(db, awaiting_video, monkeypatch):
    enable_publishing(monkeypatch)
    review = approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    other = Review(video_version_id=awaiting_video.id, decision="APPROVED", reviewer="owner", digest_json={})
    db.add(other)
    db.commit()
    with pytest.raises(Exception, match="approval_superseded"):
        publish_destination(db, {"video_id": awaiting_video.id, "review_id": review.id, "platform": "youtube", "account": "channel-1"})


def test_schedule_is_utc_and_must_be_future(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_timezone", "Europe/Copenhagen")
    future = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    value = normalize_publish_at(future.isoformat())
    assert value.endswith("+00:00")
    with pytest.raises(Exception, match="publication_time_must_be_future"):
        normalize_publish_at("2020-01-01T00:00:00Z")


@pytest.mark.parametrize(
    "field,value",
    [("visibility", "public"), ("publish_at", "2030-01-01T00:00:00+00:00")],
)
def test_dispatch_rejects_changed_publication_options(db, awaiting_video, monkeypatch, field, value):
    enable_publishing(monkeypatch)
    review = approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    payload = {
        "video_id": awaiting_video.id,
        "review_id": review.id,
        "platform": "youtube",
        "account": "channel-1",
        "visibility": "private",
        "publish_at": None,
    }
    payload[field] = value
    with pytest.raises(Exception, match="approval_publication_options_mismatch"):
        publish_destination(db, payload)


def test_changed_video_invalidates_every_destination(db, awaiting_video, monkeypatch):
    enable_publishing(monkeypatch)
    approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    with open(awaiting_video.video_path, "ab") as handle:
        handle.write(b"changed")
    for destination in DESTINATIONS:
        with pytest.raises(Exception, match="approval_invalidated_by_change"):
            verify_approval(db, awaiting_video, destination["platform"], destination["account"])


def test_scheduled_job_is_not_claimed_before_due_time(db, awaiting_video, monkeypatch):
    enable_publishing(monkeypatch)
    future = normalize_publish_at((datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    destinations = [{**DESTINATIONS[0], "publish_at": future}]
    review = approve_destinations(db, awaiting_video, "owner", destinations, True)
    jobs = enqueue_publication_jobs(db, review)
    assert len(jobs) == 1
    assert claim(db, "too-early") is None


def test_partial_failure_does_not_mark_package_complete(db, awaiting_video, monkeypatch):
    from app.pipeline.platforms import PublishError, _mark_failure

    enable_publishing(monkeypatch)
    approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    successful = new_publication(db, awaiting_video, "youtube", "channel-1")
    successful.status = "PUBLISHED"
    successful.remote_id = "youtube-post"
    _mark_success(db, successful, awaiting_video)
    failed = new_publication(db, awaiting_video, "instagram", "instagram-1")
    _mark_failure(db, failed, awaiting_video, PublishError("test_failure"))
    assert awaiting_video.status == "PUBLISHING"
    assert successful.status == "PUBLISHED"
    assert failed.status == "FAILED"


def test_stale_approval_cannot_enqueue_more_jobs(db, awaiting_video, monkeypatch):
    enable_publishing(monkeypatch)
    review = approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    db.add(Review(video_version_id=awaiting_video.id, decision="APPROVED", reviewer="owner", digest_json={}))
    db.commit()
    with pytest.raises(Exception, match="approval_superseded"):
        enqueue_publication_jobs(db, review)


def test_invalid_schedule_is_a_controlled_approval_error():
    with pytest.raises(Exception, match="invalid_publication_time"):
        normalize_publish_at("not-a-date")


def test_expired_editorial_evidence_blocks_dispatch_after_approval(db, awaiting_video, monkeypatch):
    enable_publishing(monkeypatch)
    review = approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    review.checks_json = {**review.checks_json, "editorial": {"decision": "ALLOW", "source_valid_until": "2020-01-01T00:00:00+00:00"}}
    db.commit()
    with pytest.raises(Exception, match="editorial_source_refresh_required"):
        verify_approval(db, awaiting_video, "youtube", "channel-1")


def test_changed_narration_artifact_invalidates_approval(db, awaiting_video, monkeypatch):
    enable_publishing(monkeypatch)
    from pathlib import Path

    path = Path(awaiting_video.output_dir) / "narration.wav"
    path.write_bytes(b"original narration")
    db.commit()
    approve_destinations(db, awaiting_video, "owner", DESTINATIONS, True)
    path.write_bytes(b"changed narration")
    with pytest.raises(Exception, match="approval_invalidated_by_change"):
        verify_approval(db, awaiting_video, "youtube", "channel-1")
