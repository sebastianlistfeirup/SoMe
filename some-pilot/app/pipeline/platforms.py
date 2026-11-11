import json
import re
import time
import zipfile
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Publication, Setting, VideoVersion, utcnow
from app.pipeline.approvals import transition, verify_approval
from app.pipeline.signed_media import create_link


class PublishError(RuntimeError):
    pass


def new_publication(db: Session, video: VideoVersion, platform: str, account: str) -> Publication:
    key = f"video:{video.id}:platform:{platform}:account:{account}"
    existing = db.query(Publication).filter(Publication.idempotency_key == key).first()
    if existing:
        if existing.status == "FAILED" and video.status == "APPROVED":
            existing.status = "SCHEDULED"
            transition(video, "SCHEDULED")
            db.commit()
        return existing
    verify_approval(db, video, platform, account)
    publication = Publication(video_version_id=video.id, platform=platform, account=account, idempotency_key=key)
    db.add(publication)
    transition(video, "SCHEDULED")
    db.commit()
    db.refresh(publication)
    return publication


def manual_export(video: VideoVersion, platform: str, output_root: Path) -> Path:
    source = Path(video.output_dir)
    required = ["video.mp4", "thumbnail.jpg", "captions.srt", "post.json", "manifest.json", "rights.json", "checks.json"]
    optional = ["clip_plan.json", "storyboard.jpg"]
    missing = [name for name in required if not (source / name).exists()]
    if missing:
        raise PublishError("export_missing:" + ",".join(missing))
    target_dir = output_root / "exports"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"video-{video.id}-{platform}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in required + optional:
            if (source / name).exists():
                archive.write(source / name, arcname=name)
        instructions = {"platform": platform, "status": "MANUAL_EXPORT_NOT_PUBLISHED", "steps": ["Watch the entire video.", "Verify account, rights, text, links and disclosure.", f"Upload manually to {platform}.", "Record the resulting URL/remote ID in the dashboard or metrics import."], "demo": video.features_json.get("is_demo", False)}
        archive.writestr("PUBLISHING_INSTRUCTIONS.json", json.dumps(instructions, indent=2))
    return target


def _mark_timeout(db: Session, publication: Publication, video: VideoVersion) -> None:
    publication.status = "RECONCILE_REQUIRED"
    publication.error_code = "upload_timeout_reconcile_required"
    transition(video, "RECONCILE_REQUIRED")
    db.commit()


def _mark_failure(db: Session, publication: Publication, video: VideoVersion, exc: Exception) -> None:
    publication.status = "FAILED"
    publication.error_code = type(exc).__name__
    transition(video, "FAILED")
    db.commit()


class YouTubePublisher:
    def __init__(self):
        self.settings = get_settings()

    def capabilities(self, db: Session | None = None) -> dict:
        configured = bool(self.settings.youtube_client_id and self.settings.youtube_client_secret and self.settings.youtube_refresh_token)
        connection = db.get(Setting, "youtube_connection") if db is not None else None
        state = connection.value_json if connection else {}
        return {"publishing_configured": configured, "oauth_verified": bool(state.get("oauth_verified")), "private_upload_verified": bool(state.get("private_upload_verified")), "channel_id": state.get("channel_id"), "manual_export": True}

    def _access_token(self) -> str:
        response = httpx.post("https://oauth2.googleapis.com/token", data={"client_id": self.settings.youtube_client_id, "client_secret": self.settings.youtube_client_secret, "refresh_token": self.settings.youtube_refresh_token, "grant_type": "refresh_token"}, timeout=30)
        if response.status_code in {401, 403}:
            raise PublishError("youtube_authorization_required")
        response.raise_for_status()
        return response.json()["access_token"]

    def publish(self, db: Session, video: VideoVersion, account: str, privacy: str = "private") -> Publication:
        if privacy not in {"private", "public", "unlisted"}:
            raise PublishError("explicit_valid_privacy_required")
        publication = new_publication(db, video, "youtube", account)
        if publication.status == "PUBLISHED":
            return publication
        if publication.status == "RECONCILE_REQUIRED":
            raise PublishError("reconcile_required_before_retry")
        verify_approval(db, video, "youtube", account)
        publication.status = "PUBLISHING"
        transition(video, "PUBLISHING")
        db.commit()
        try:
            token = self._access_token()
            metadata = {"snippet": {"title": video.post_json.get("text", "")[:95], "description": video.post_json.get("text", "")}, "status": {"privacyStatus": privacy}}
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4"}
            start = httpx.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", headers=headers, json=metadata, timeout=30)
            if start.status_code in {401, 403}:
                raise PublishError("youtube_authorization_or_audit_required")
            start.raise_for_status()
            session_url = start.headers.get("location")
            if not session_url:
                raise PublishError("youtube_upload_session_missing")
            publication.upload_session = session_url
            db.commit()
            with Path(video.video_path).open("rb") as handle:
                uploaded = httpx.put(session_url, content=handle, headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"}, timeout=120)
            uploaded.raise_for_status()
            body = uploaded.json()
            publication.remote_id = body.get("id")
            publication.response_json = {"id": body.get("id"), "status": body.get("status", {})}
            publication.status = "PUBLISHED"
            publication.published_at = utcnow()
            transition(video, "PUBLISHED")
            db.commit()
            return publication
        except httpx.TimeoutException:
            _mark_timeout(db, publication, video)
            raise PublishError("upload_timeout_reconcile_required")
        except Exception as exc:
            _mark_failure(db, publication, video, exc)
            raise


class InstagramPublisher:
    def capabilities(self, db: Session | None = None) -> dict:
        settings = get_settings()
        configured = bool(settings.meta_access_token and settings.meta_instagram_account_id and settings.meta_graph_version and settings.public_base_url)
        connection = db.get(Setting, "meta_connection") if db is not None else None
        state = connection.value_json if connection else {}
        return {"publishing_configured": configured, "oauth_verified": bool(state.get("oauth_verified")), "profile_verified": bool(state.get("instagram_profile_verified")), "test_publication_verified": bool(state.get("instagram_test_publication_verified")), "private_upload_verified": False, "private_upload_supported": False, "manual_export": True, "public_media_url_required": True}

    def publish(self, db: Session, video: VideoVersion, account: str, media_url: str = "") -> Publication:
        settings = get_settings()
        if not all((settings.meta_access_token, settings.meta_instagram_account_id, settings.meta_graph_version, settings.public_base_url)):
            raise PublishError("instagram_not_configured; use_manual_export")
        if not re.fullmatch(r"v\d+\.\d+", settings.meta_graph_version):
            raise PublishError("explicit_valid_meta_graph_version_required")
        if account != settings.meta_instagram_account_id:
            raise PublishError("instagram_account_mismatch")
        media_url = media_url or create_link(db, video, "instagram", account)
        if not media_url.startswith("https://"):
            raise PublishError("signed_https_media_url_required")
        publication = new_publication(db, video, "instagram", account)
        if publication.status == "PUBLISHED":
            return publication
        if publication.status == "RECONCILE_REQUIRED":
            raise PublishError("reconcile_required_before_retry")
        verify_approval(db, video, "instagram", account)
        publication.status = "PUBLISHING"
        transition(video, "PUBLISHING")
        db.commit()
        base = f"https://graph.facebook.com/{settings.meta_graph_version}"
        headers = {"Authorization": f"Bearer {settings.meta_access_token}"}
        try:
            created = httpx.post(f"{base}/{account}/media", headers=headers, data={"media_type": "REELS", "video_url": media_url, "caption": video.post_json.get("text", "")}, timeout=30)
            if created.status_code in {401, 403}:
                raise PublishError("instagram_authorization_required")
            created.raise_for_status()
            container_id = created.json()["id"]
            publication.upload_session = container_id
            db.commit()
            status = ""
            for _ in range(30):
                polled = httpx.get(f"{base}/{container_id}", headers=headers, params={"fields": "status_code"}, timeout=20)
                polled.raise_for_status()
                status = polled.json().get("status_code", "")
                if status == "FINISHED":
                    break
                if status == "ERROR":
                    raise PublishError("instagram_media_processing_failed")
                time.sleep(2)
            if status != "FINISHED":
                raise PublishError("instagram_media_processing_not_finished_reconcile")
            published = httpx.post(f"{base}/{account}/media_publish", headers=headers, data={"creation_id": container_id}, timeout=30)
            published.raise_for_status()
            remote_id = published.json().get("id")
            publication.remote_id = remote_id
            publication.response_json = {"container_id": container_id, "id": remote_id}
            publication.status = "PUBLISHED"
            publication.published_at = utcnow()
            transition(video, "PUBLISHED")
            db.commit()
            return publication
        except (httpx.TimeoutException, PublishError) as exc:
            if isinstance(exc, httpx.TimeoutException) or "not_finished_reconcile" in str(exc):
                _mark_timeout(db, publication, video)
                raise PublishError("instagram_reconcile_required") from exc
            _mark_failure(db, publication, video, exc)
            raise
        except Exception as exc:
            _mark_failure(db, publication, video, exc)
            raise


class FacebookPublisher:
    def capabilities(self, db: Session | None = None) -> dict:
        settings = get_settings()
        configured = bool(settings.meta_page_access_token and settings.meta_page_id and settings.meta_graph_version)
        connection = db.get(Setting, "meta_connection") if db is not None else None
        state = connection.value_json if connection else {}
        return {"publishing_configured": configured, "oauth_verified": bool(state.get("oauth_verified")), "page_verified": bool(state.get("facebook_page_verified")), "test_publication_verified": bool(state.get("facebook_test_publication_verified")), "page_id": state.get("facebook_page_id"), "manual_export": True, "public_media_url_required": False}

    def publish(self, db: Session, video: VideoVersion, account: str) -> Publication:
        settings = get_settings()
        if not all((settings.meta_page_access_token, settings.meta_page_id, settings.meta_graph_version)):
            raise PublishError("facebook_not_configured; use_manual_export")
        if not re.fullmatch(r"v\d+\.\d+", settings.meta_graph_version):
            raise PublishError("explicit_valid_meta_graph_version_required")
        if account != settings.meta_page_id:
            raise PublishError("facebook_page_mismatch")
        verify_approval(db, video, "facebook", account)
        publication = new_publication(db, video, "facebook", account)
        if publication.status == "PUBLISHED":
            return publication
        if publication.status == "RECONCILE_REQUIRED":
            raise PublishError("reconcile_required_before_retry")
        publication.status = "PUBLISHING"
        transition(video, "PUBLISHING")
        db.commit()
        try:
            with Path(video.video_path).open("rb") as handle:
                response = httpx.post(
                    f"https://graph.facebook.com/{settings.meta_graph_version}/{account}/videos",
                    headers={"Authorization": f"Bearer {settings.meta_page_access_token}"},
                    data={"description": video.post_json.get("text", "")},
                    files={"file": (Path(video.video_path).name, handle, "video/mp4")},
                    timeout=120,
                )
            if response.status_code >= 400:
                try:
                    error = response.json().get("error", {})
                    detail = f"{error.get('type', '')}:{error.get('code', '')}:{error.get('message', '')}"
                except (ValueError, AttributeError):
                    detail = "unreadable_graph_error"
                raise PublishError(f"facebook_graph_error:{detail[:300]}")
            response.raise_for_status()
            remote_id = response.json().get("id")
            if not remote_id:
                raise PublishError("facebook_remote_video_id_missing")
            publication.remote_id = remote_id
            publication.response_json = {"id": remote_id}
            publication.status = "PUBLISHED"
            publication.published_at = utcnow()
            transition(video, "PUBLISHED")
            db.commit()
            return publication
        except httpx.TimeoutException:
            _mark_timeout(db, publication, video)
            raise PublishError("facebook_reconcile_required")
        except Exception as exc:
            _mark_failure(db, publication, video, exc)
            raise


class TikTokPublisher:
    def capabilities(self) -> dict:
        return {"publishing_configured": False, "oauth_verified": False, "audit_status": "not_evaluated", "manual_export": True}

    def publish(self, *_args, **_kwargs) -> Publication:
        raise PublishError("tiktok_requires_current_content_posting_audit; use_manual_export")
