from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Job, Review, VideoVersion
from app.pipeline.approvals import ApprovalError, latest_approval, verify_approval
from app.pipeline.jobs import enqueue
from app.pipeline.platforms import FacebookPublisher, InstagramPublisher, PublishError, TikTokPublisher, YouTubePublisher


def normalize_publish_at(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(get_settings().app_timezone))
        parsed = parsed.astimezone(timezone.utc)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ApprovalError("invalid_publication_time") from exc
    if parsed <= datetime.now(timezone.utc):
        raise ApprovalError("publication_time_must_be_future")
    return parsed.isoformat()


def enqueue_publication_jobs(db: Session, review: Review) -> list[Job]:
    if review.decision != "APPROVED":
        return []
    current = latest_approval(db, review.video_version_id)
    if not current or current.id != review.id:
        raise ApprovalError("approval_superseded")
    jobs = []
    for destination in review.digest_json.get("destinations", []):
        payload = {
            "video_id": review.video_version_id,
            "review_id": review.id,
            "platform": destination["platform"],
            "account": destination["account"],
            "visibility": destination.get("visibility", "public"),
            "publish_at": destination.get("publish_at"),
        }
        due_at = (
            datetime.fromisoformat(destination["publish_at"].replace("Z", "+00:00"))
            if destination.get("publish_at")
            else None
        )
        job, _created = enqueue(
            db,
            "publish",
            payload,
            f"publish:video:{review.video_version_id}:platform:{destination['platform']}:account:{destination['account']}:review:{review.id}",
            due_at=due_at,
            max_attempts=3,
        )
        jobs.append(job)
    return jobs


def publish_destination(db: Session, payload: dict) -> dict:
    video = db.get(VideoVersion, payload["video_id"])
    if not video:
        raise PublishError("video_not_found")
    review = db.get(Review, payload["review_id"])
    current_approval = latest_approval(db, video.id)
    if not review or not current_approval or current_approval.id != review.id:
        raise PublishError("approval_superseded")
    platform = payload["platform"]
    account = payload["account"]
    visibility = payload.get("visibility", "public")
    publish_at = payload.get("publish_at")
    destination = next(
        (
            item
            for item in review.digest_json.get("destinations", [])
            if item["platform"] == platform and item["account"] == account
        ),
        None,
    )
    if destination and (
        visibility != destination.get("visibility", "public")
        or publish_at != destination.get("publish_at")
    ):
        raise PublishError("approval_publication_options_mismatch")
    verify_approval(db, video, platform, account)
    if platform == "youtube":
        publication = YouTubePublisher().publish(db, video, account, visibility)
    elif platform == "instagram":
        publication = InstagramPublisher().publish(db, video, account)
    elif platform == "facebook":
        publication = FacebookPublisher().publish(db, video, account)
    elif platform == "tiktok":
        publication = TikTokPublisher().publish(db, video, account)
    else:
        raise PublishError("unsupported_platform")
    return {
        "publication_id": publication.id,
        "status": publication.status,
        "remote_id": publication.remote_id,
        "platform": platform,
        "external_visibility": publication.response_json.get("external_visibility", visibility),
    }
