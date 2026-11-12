import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Setting, VideoVersion
from app.pipeline.approvals import approval_digest, destinations_digest, latest_approval


class SignedMediaError(ValueError):
    pass


def _key(db: Session) -> bytes:
    settings = get_settings()
    if settings.app_secret_key:
        return settings.app_secret_key.encode()
    setting = db.get(Setting, "media_signing_key")
    if not setting:
        setting = Setting(key="media_signing_key", value_json={"key": secrets.token_urlsafe(48)})
        db.add(setting)
        db.commit()
    return setting.value_json["key"].encode()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _approval_digest(video: VideoVersion, review, platform: str, account: str) -> dict:
    destinations = review.digest_json.get("destinations")
    if destinations:
        if not any(item["platform"] == platform and item["account"] == account for item in destinations):
            raise SignedMediaError("approval_destination_mismatch")
        return destinations_digest(video, destinations)
    return approval_digest(video, platform, account)


def create_link(db: Session, video: VideoVersion, platform: str, account: str, asset: str = "video") -> str:
    if video.status not in {"APPROVED", "SCHEDULED", "PUBLISHING", "PUBLISHED"}:
        raise SignedMediaError("video_not_approved")
    if asset not in {"video", "thumbnail"}:
        raise SignedMediaError("unsupported_media_asset")
    review = latest_approval(db, video.id)
    if not review:
        raise SignedMediaError("owner_approval_required")
    digest = _approval_digest(video, review, platform, account)
    if digest["approval_sha256"] != review.digest_json.get("approval_sha256"):
        raise SignedMediaError("approval_invalidated_by_change")
    settings = get_settings()
    payload = {"video_id": video.id, "platform": platform, "account": account, "asset": asset, "approval": digest["approval_sha256"], "exp": int(time.time()) + settings.signed_media_ttl_seconds, "nonce": secrets.token_urlsafe(12)}
    encoded = _encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    signature = _encode(hmac.new(_key(db), encoded.encode(), hashlib.sha256).digest())
    path = f"/public-media/{encoded}.{signature}"
    return settings.public_base_url.rstrip("/") + path if settings.public_base_url else path


def resolve_link(db: Session, token: str) -> Path:
    settings = get_settings()
    try:
        encoded, signature = token.rsplit(".", 1)
        expected = _encode(hmac.new(_key(db), encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise SignedMediaError("invalid_signature")
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload["exp"] < time.time() or payload["exp"] > time.time() + settings.signed_media_ttl_seconds + 60:
            raise SignedMediaError("expired_or_invalid_expiry")
        video = db.get(VideoVersion, payload["video_id"])
        if not video or video.status not in {"APPROVED", "SCHEDULED", "PUBLISHING", "PUBLISHED"}:
            raise SignedMediaError("video_not_available")
        asset = payload.get("asset", "video")
        if asset not in {"video", "thumbnail"}:
            raise SignedMediaError("unsupported_media_asset")
        review = latest_approval(db, video.id)
        if not review:
            raise SignedMediaError("approval_changed")
        current = _approval_digest(video, review, payload["platform"], payload["account"])
        if review.digest_json.get("approval_sha256") != payload["approval"] or current["approval_sha256"] != payload["approval"]:
            raise SignedMediaError("approval_changed")
        return Path(video.thumbnail_path if asset == "thumbnail" else video.video_path)
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise SignedMediaError("invalid_or_expired_link") from exc
