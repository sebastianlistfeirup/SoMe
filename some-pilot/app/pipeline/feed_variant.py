"""Attach the native 4:5 render of a video as its organic Facebook feed variant.

The 4:5 file is rendered by scripts/produce_local.py --format 4x5 from the same plan and narration as
the 9:16/16:9 version. Attaching copies it next to the video as feed_4x5.mp4 + feed_thumbnail.jpg and
records what was checked. The owner then chooses "Facebook-feed (4:5)" on the review page; the approval
binds both files by SHA-256, so the feed post can never differ from what the owner watched.
"""

import json
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Review, VideoVersion
from app.pipeline.approvals import FEED_THUMBNAIL, FEED_VIDEO, ApprovalError, sha256_file
from app.pipeline.media import probe

FEED_SIZE = (1080, 1350)
MAX_DURATION_DRIFT_SECONDS = 3.0
MIN_REAL_MEDIA_RATIO = 0.8


def _approved_feed(db: Session, video: VideoVersion) -> bool:
    return any(item.get("platform") == "facebook_feed" for review in db.query(Review).filter(Review.video_version_id == video.id, Review.decision == "APPROVED").all() for item in (review.digest_json or {}).get("destinations", []))


def inspect_render(source: Path) -> dict:
    """Validate a 4x5 render folder; raises ApprovalError with the first problem."""
    video_file, thumbnail = source / "final.mp4", source / "thumbnail.jpg"
    if not video_file.is_file() or not thumbnail.is_file():
        raise ApprovalError("feed_render_files_missing")
    metadata = probe(video_file)
    stream = next((item for item in metadata.get("streams", []) if item.get("codec_type") == "video"), {})
    audio = any(item.get("codec_type") == "audio" for item in metadata.get("streams", []))
    size = (int(stream.get("width") or 0), int(stream.get("height") or 0))
    if size != FEED_SIZE:
        raise ApprovalError(f"feed_render_not_4x5:{size[0]}x{size[1]}")
    if stream.get("codec_name") != "h264" or not audio:
        raise ApprovalError("feed_render_codec_unsupported")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    if manifest.get("format") not in {None, "4x5"}:
        raise ApprovalError("feed_render_manifest_not_4x5")
    checks = manifest.get("checks") or {}
    if manifest and not checks.get("pass"):
        raise ApprovalError("feed_render_checks_failed")
    real = manifest.get("real_media_ratio")
    if real is not None and float(real) < MIN_REAL_MEDIA_RATIO:
        raise ApprovalError("feed_render_real_media_below_minimum")
    return {"duration": float(metadata.get("format", {}).get("duration") or 0), "checks": {key: checks.get(key) for key in ("pass", "integrated_lufs", "true_peak_dbtp", "duration_s") if key in checks}, "real_media_ratio": real}


def attach_feed_variant(db: Session, video: VideoVersion, source: Path) -> dict:
    if _approved_feed(db, video):
        raise ApprovalError("feed_variant_already_approved")  # replacing it would invalidate an approval
    if video.status in {"BLOCKED", "REJECTED"}:
        raise ApprovalError("video_not_publishable")
    facts = inspect_render(Path(source))
    if video.duration_seconds and abs(facts["duration"] - float(video.duration_seconds)) > MAX_DURATION_DRIFT_SECONDS:
        raise ApprovalError("feed_render_duration_differs_from_video")
    root = Path(video.output_dir)
    shutil.copy2(Path(source) / "final.mp4", root / FEED_VIDEO)
    shutil.copy2(Path(source) / "thumbnail.jpg", root / FEED_THUMBNAIL)
    info = {"video": FEED_VIDEO, "thumbnail": FEED_THUMBNAIL, "aspect_ratio": "4:5", "width": FEED_SIZE[0], "height": FEED_SIZE[1], "duration_seconds": round(facts["duration"], 2), "video_sha256": sha256_file(str(root / FEED_VIDEO)), "thumbnail_sha256": sha256_file(str(root / FEED_THUMBNAIL)), "render_checks": facts["checks"], "real_media_ratio": facts["real_media_ratio"]}
    video.features_json = {**(video.features_json or {}), "feed_variant": info}
    db.add(AuditEvent(actor="claude-import", action="ATTACH_FEED_VARIANT", entity_type="video_version", entity_id=str(video.id), details_json={key: info[key] for key in ("aspect_ratio", "duration_seconds", "video_sha256", "thumbnail_sha256")}))
    db.commit()
    return {"video_id": video.id, "status": video.status, **info}
