import json
import re
import time
import zipfile
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AuditEvent, Publication, Setting, VideoVersion, utcnow
from app.pipeline.approvals import approved_content, transition, verify_approval
from app.pipeline.signed_media import create_link


class PublishError(RuntimeError):
    pass


def new_publication(db: Session, video: VideoVersion, platform: str, account: str) -> Publication:
    key = f"video:{video.id}:platform:{platform}:account:{account}"
    existing = db.query(Publication).filter(Publication.idempotency_key == key).first()
    if existing:
        if existing.status == "FAILED":
            if video.status == "FAILED":
                transition(video, "AWAITING_OWNER", "retry")
                transition(video, "APPROVED", "retry")
            if video.status == "APPROVED":
                existing.status = "SCHEDULED"
                transition(video, "SCHEDULED")
                db.commit()
        return existing
    verify_approval(db, video, platform, account)
    publication = Publication(video_version_id=video.id, platform=platform, account=account, idempotency_key=key)
    db.add(publication)
    if video.status == "APPROVED":
        transition(video, "SCHEDULED")
    else:
        publication.status = "PUBLISHING"
    db.commit()
    db.refresh(publication)
    return publication


def manual_export(video: VideoVersion, platform: str, output_root: Path) -> Path:
    source = Path(video.output_dir)
    required = ["video.mp4", "thumbnail.jpg", "captions.srt", "post.json", "manifest.json", "rights.json", "checks.json", "media_composition.json"]
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


def _enter_publishing(video: VideoVersion) -> None:
    """Multi-destination approvals publish one destination at a time; later ones find the video already PUBLISHING."""
    if video.status != "PUBLISHING":
        transition(video, "PUBLISHING")


def _mark_success(db: Session, publication: Publication, video: VideoVersion) -> None:
    from app.pipeline.approvals import latest_approval
    review = latest_approval(db, video.id)
    expected = {(item["platform"], item["account"]) for item in review.digest_json.get("destinations", [])} if review else set()
    if not expected:
        expected = {(publication.platform, publication.account)}
    published = {(row.platform, row.account) for row in db.query(Publication).filter(Publication.video_version_id == video.id, Publication.status == "PUBLISHED").all()}
    if expected <= published:
        if video.status != "PUBLISHED":
            transition(video, "PUBLISHED")
    else:
        video.status = "PUBLISHING"
    db.commit()


def _mark_timeout(db: Session, publication: Publication, video: VideoVersion, error_code: str = "upload_timeout_reconcile_required") -> None:
    publication.status = "RECONCILE_REQUIRED"
    publication.error_code = error_code
    review = __import__("app.pipeline.approvals", fromlist=["latest_approval"]).latest_approval(db, video.id)
    if review and len(review.digest_json.get("destinations", [])) > 1:
        video.status = "PUBLISHING"
    else:
        transition(video, "RECONCILE_REQUIRED")
    db.commit()


def _mark_failure(db: Session, publication: Publication, video: VideoVersion, exc: Exception) -> None:
    publication.status = "FAILED"
    publication.error_code = type(exc).__name__
    review = __import__("app.pipeline.approvals", fromlist=["latest_approval"]).latest_approval(db, video.id)
    if review and len(review.digest_json.get("destinations", [])) > 1:
        video.status = "PUBLISHING"
    else:
        transition(video, "FAILED")
    db.commit()


# Long videos can need several minutes of processing before YouTube reports "succeeded".
YOUTUBE_PROCESSING_SECONDS = 600


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

    def _wait_for_processing(self, token: str, remote_id: str) -> str:
        """Poll processingDetails for up to YOUTUBE_PROCESSING_SECONDS with backoff (long videos need minutes)."""
        deadline = time.monotonic() + YOUTUBE_PROCESSING_SECONDS
        delay = 2.0
        while True:
            status_response = httpx.get(
                "https://www.googleapis.com/youtube/v3/videos",
                headers={"Authorization": f"Bearer {token}"},
                params={"part": "status,processingDetails", "id": remote_id},
                timeout=20,
            )
            status_response.raise_for_status()
            items = status_response.json().get("items", [])
            processing = items[0].get("processingDetails", {}).get("processingStatus", "") if items else ""
            if processing in {"succeeded", "failed", "terminated"} or time.monotonic() + delay > deadline:
                return processing
            time.sleep(delay)
            delay = min(delay * 1.5, 20)

    def set_thumbnail(self, db: Session, publication: Publication, video: VideoVersion, token: str | None = None) -> dict:
        """Upload the approved thumbnail to a published video; records the outcome, never raises for a rejection."""
        token = token or self._access_token()
        outcome = {"cover": "custom_thumbnail_set"}
        try:
            with Path(video.thumbnail_path).open("rb") as handle:
                cover = httpx.post(
                    "https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"videoId": publication.remote_id},
                    files={"media": (Path(video.thumbnail_path).name, handle, "image/jpeg")},
                    timeout=60,
                )
            if cover.status_code >= 400:
                try:
                    error = cover.json().get("error", {})
                    reasons = ",".join(item.get("reason", "") for item in error.get("errors", [])) or str(error.get("code", ""))
                except (ValueError, AttributeError):
                    reasons = "unreadable"
                outcome = {"cover": "custom_thumbnail_failed", "cover_error": f"http_{cover.status_code}:{reasons}"[:160], "cover_retry": "python -m app.cli youtube-thumbnail --publication " + str(publication.id)}
        except httpx.HTTPError as exc:
            outcome = {"cover": "custom_thumbnail_failed", "cover_error": type(exc).__name__, "cover_retry": "python -m app.cli youtube-thumbnail --publication " + str(publication.id)}
        publication.response_json = {**{key: value for key, value in (publication.response_json or {}).items() if key not in {"cover_error", "cover_retry"}}, **outcome}
        db.add(AuditEvent(actor="system", action="YOUTUBE_THUMBNAIL_SET" if outcome["cover"] == "custom_thumbnail_set" else "YOUTUBE_THUMBNAIL_FAILED", entity_type="publication", entity_id=str(publication.id), details_json={"remote_id": publication.remote_id, **{key: value for key, value in outcome.items() if key != "cover_retry"}}))
        db.commit()
        return outcome

    def publish(self, db: Session, video: VideoVersion, account: str, privacy: str = "private") -> Publication:
        if privacy not in {"private", "public", "unlisted"}:
            raise PublishError("explicit_valid_privacy_required")
        publication = new_publication(db, video, "youtube", account)
        if publication.status == "PUBLISHED":
            return publication
        if publication.status == "RECONCILE_REQUIRED":
            raise PublishError("reconcile_required_before_retry")
        content = approved_content(verify_approval(db, video, "youtube", account), video, "youtube", account)
        publication.status = "PUBLISHING"
        _enter_publishing(video)
        db.commit()
        try:
            token = self._access_token()
            status = {"privacyStatus": privacy}
            if content["ai_label"] is not None:
                status["containsSyntheticMedia"] = bool(content["ai_label"])
            metadata = {"snippet": {"title": content["title"][:100], "description": content["text"]}, "status": status}
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
            remote_id = body.get("id")
            if not remote_id:
                raise PublishError("youtube_remote_video_id_missing")
            publication.remote_id = remote_id
            db.commit()
            processing = self._wait_for_processing(token, remote_id)
            if processing in {"failed", "terminated"}:
                raise PublishError("youtube_processing_failed_reconcile_required")
            if processing != "succeeded":
                raise PublishError("youtube_processing_not_finished_reconcile_required")
            # The video is live from here on. A rejected custom thumbnail (e.g. a channel without phone
            # verification) is a warning with a retry command, never a reason to treat the upload as uncertain.
            publication.response_json = {"id": remote_id, "status": body.get("status", {}), "processing_status": processing, "cover": "pending"}
            publication.status = "PUBLISHED"
            publication.published_at = utcnow()
            _mark_success(db, publication, video)
            db.commit()
            self.set_thumbnail(db, publication, video, token)
        except httpx.TimeoutException:
            _mark_timeout(db, publication, video)
            raise PublishError("upload_timeout_reconcile_required")
        except Exception as exc:
            if publication.remote_id:
                _mark_timeout(db, publication, video, "youtube_cover_or_processing_reconcile_required")
            else:
                _mark_failure(db, publication, video, exc)
            raise
        if content.get("post_publish"):
            from app.pipeline.youtube_extras import run_post_publish

            run_post_publish(db, video, publication, token, content["post_publish"])
        return publication


# Reels containers often need several minutes; poll with backoff instead of giving up after 60 s.
INSTAGRAM_POLL_SECONDS = 600
INSTAGRAM_POLL_MAX_DELAY = 20


class InstagramPublisher:
    def capabilities(self, db: Session | None = None) -> dict:
        settings = get_settings()
        configured = bool(settings.meta_access_token and settings.meta_instagram_account_id and settings.meta_graph_version and settings.public_base_url)
        connection = db.get(Setting, "meta_connection") if db is not None else None
        state = connection.value_json if connection else {}
        return {"publishing_configured": configured, "oauth_verified": bool(state.get("oauth_verified")), "profile_verified": bool(state.get("instagram_profile_verified")), "test_publication_verified": bool(state.get("instagram_test_publication_verified")), "private_upload_verified": False, "private_upload_supported": False, "manual_export": True, "public_media_url_required": True}

    def _container_status(self, base: str, headers: dict, container_id: str, seconds: float = INSTAGRAM_POLL_SECONDS) -> str:
        """Poll until the container leaves IN_PROGRESS or the window closes; returns the last status_code."""
        deadline = time.monotonic() + seconds
        delay = 2.0
        while True:
            polled = httpx.get(f"{base}/{container_id}", headers=headers, params={"fields": "status_code"}, timeout=20)
            polled.raise_for_status()
            status = polled.json().get("status_code", "")
            if status in {"FINISHED", "PUBLISHED", "ERROR", "EXPIRED"} or time.monotonic() + delay > deadline:
                return status
            time.sleep(delay)
            delay = min(delay * 1.5, INSTAGRAM_POLL_MAX_DELAY)

    def _publish_container(self, db: Session, publication: Publication, video: VideoVersion, base: str, headers: dict, account: str, container_id: str) -> Publication:
        published = httpx.post(f"{base}/{account}/media_publish", headers=headers, data={"creation_id": container_id}, timeout=30)
        published.raise_for_status()
        remote_id = published.json().get("id")
        publication.remote_id = remote_id
        publication.response_json = {"container_id": container_id, "id": remote_id}
        publication.status = "PUBLISHED"
        publication.published_at = utcnow()
        _mark_success(db, publication, video)
        db.commit()
        return publication

    def reconcile(self, db: Session, publication: Publication, video: VideoVersion, account: str) -> Publication:
        """Finish a publication whose container outlived the poll window, without uploading again.

        FINISHED: the container was never published, so media_publish it now. PUBLISHED: it may
        already be live and the media id is unknown, so a human must confirm. ERROR/EXPIRED: the
        container is dead, and the next retry creates a new one.
        """
        settings = get_settings()
        base = f"https://graph.facebook.com/{settings.meta_graph_version}"
        headers = {"Authorization": f"Bearer {settings.meta_access_token}"}
        container_id = publication.upload_session
        status = self._container_status(base, headers, container_id)
        if status == "FINISHED":
            try:
                self._publish_container(db, publication, video, base, headers, account, container_id)
            except Exception as exc:
                db.rollback()
                raise PublishError("instagram_reconcile_publish_unconfirmed") from exc
            db.add(AuditEvent(actor="system", action="PUBLICATION_RECONCILED", entity_type="publication", entity_id=str(publication.id), details_json={"platform": "instagram", "container_status": status, "remote_id": publication.remote_id}))
            db.commit()
            return publication
        if status in {"ERROR", "EXPIRED"}:
            publication.status = "FAILED"
            publication.error_code = f"instagram_container_{status.lower()}"
            db.commit()
            raise PublishError(f"instagram_container_{status.lower()}_retry_creates_new_container")
        if status == "PUBLISHED":
            raise PublishError("instagram_container_already_published_manual_reconcile")
        raise PublishError(f"instagram_reconcile_required:{status or 'unknown'}")

    def publish(self, db: Session, video: VideoVersion, account: str, media_url: str = "") -> Publication:
        settings = get_settings()
        if not all((settings.meta_access_token, settings.meta_instagram_account_id, settings.meta_graph_version, settings.public_base_url)):
            raise PublishError("instagram_not_configured; use_manual_export")
        if not re.fullmatch(r"v\d+\.\d+", settings.meta_graph_version):
            raise PublishError("explicit_valid_meta_graph_version_required")
        if account != settings.meta_instagram_account_id:
            raise PublishError("instagram_account_mismatch")
        existing = db.query(Publication).filter(Publication.idempotency_key == f"video:{video.id}:platform:instagram:account:{account}").first()
        if existing and existing.status == "RECONCILE_REQUIRED":
            verify_approval(db, video, "instagram", account)
            if existing.upload_session and not existing.remote_id:
                return self.reconcile(db, existing, video, account)
            raise PublishError("reconcile_required_before_retry")
        media_url = media_url or create_link(db, video, "instagram", account)
        cover_url = create_link(db, video, "instagram", account, asset="thumbnail")
        if not media_url.startswith("https://") or not cover_url.startswith("https://"):
            raise PublishError("signed_https_media_url_required")
        publication = new_publication(db, video, "instagram", account)
        if publication.status == "PUBLISHED":
            return publication
        if publication.status == "RECONCILE_REQUIRED":
            raise PublishError("reconcile_required_before_retry")
        content = approved_content(verify_approval(db, video, "instagram", account), video, "instagram", account)
        publication.status = "PUBLISHING"
        publication.upload_session = None
        _enter_publishing(video)
        db.commit()
        base = f"https://graph.facebook.com/{settings.meta_graph_version}"
        headers = {"Authorization": f"Bearer {settings.meta_access_token}"}
        try:
            created = httpx.post(f"{base}/{account}/media", headers=headers, data={"media_type": "REELS", "video_url": media_url, "cover_url": cover_url, "caption": content["text"]}, timeout=30)
            if created.status_code in {401, 403}:
                raise PublishError("instagram_authorization_required")
            created.raise_for_status()
            container_id = created.json()["id"]
            publication.upload_session = container_id
            db.commit()
            status = self._container_status(base, headers, container_id)
            if status in {"ERROR", "EXPIRED"}:
                raise PublishError("instagram_media_processing_failed")
            if status != "FINISHED":
                raise PublishError("instagram_media_processing_not_finished_reconcile")
            return self._publish_container(db, publication, video, base, headers, account, container_id)
        except (httpx.TimeoutException, PublishError) as exc:
            if isinstance(exc, httpx.TimeoutException) or "not_finished_reconcile" in str(exc):
                _mark_timeout(db, publication, video, "instagram_reconcile_required")
                raise PublishError("instagram_reconcile_required") from exc
            _mark_failure(db, publication, video, exc)
            raise
        except Exception as exc:
            if publication.upload_session:
                _mark_timeout(db, publication, video, "instagram_reconcile_required")
            else:
                _mark_failure(db, publication, video, exc)
            raise


# Graph resumable video upload: a single multipart POST failed for videos of several hundred MB.
# Facebook decides the chunk boundaries (start_offset/end_offset) in each response.
FACEBOOK_CHUNK_TIMEOUT = 300
FACEBOOK_CHUNK_ATTEMPTS = 3


# Owner rule 13 (2026-11-16): 9:16 videos go to the Page as Reels. As regular page videos they
# show in the feed as a narrow pillarboxed strip.
FACEBOOK_REEL_UPLOAD_TIMEOUT = 600
FACEBOOK_REEL_POLL_SECONDS = 600
FACEBOOK_REEL_POLL_MAX_DELAY = 20


def is_vertical(video: VideoVersion) -> bool:
    aspect = (video.features_json or {}).get("aspect_ratio")
    if aspect in {"9:16", "16:9", "1:1", "4:5"}:
        return aspect == "9:16"
    from app.pipeline.media import probe

    try:
        stream = next((item for item in probe(Path(video.video_path)).get("streams", []) if item.get("codec_type") == "video"), {})
        return int(stream["width"]) < int(stream["height"])
    except Exception as exc:  # never guess the format: a 9:16 video posted as a page video breaks rule 13
        raise PublishError("facebook_video_aspect_unknown") from exc


def _graph_error_detail(response: httpx.Response) -> str:
    try:
        error = response.json().get("error", {})
        return f"{error.get('type', '')}:{error.get('code', '')}:{error.get('message', '')}"
    except (ValueError, AttributeError):
        return f"unreadable_graph_error:http_{response.status_code}"


class FacebookPublisher:
    def capabilities(self, db: Session | None = None) -> dict:
        settings = get_settings()
        configured = bool(settings.meta_page_access_token and settings.meta_page_id and settings.meta_graph_version)
        connection = db.get(Setting, "meta_connection") if db is not None else None
        state = connection.value_json if connection else {}
        return {"publishing_configured": configured, "oauth_verified": bool(state.get("oauth_verified")), "page_verified": bool(state.get("facebook_page_verified")), "test_publication_verified": bool(state.get("facebook_test_publication_verified")), "page_id": state.get("facebook_page_id"), "manual_export": True, "public_media_url_required": False, "upload": "resumable_chunked"}

    def _graph_post(self, url: str, headers: dict, step: str, timeout: int, **kwargs) -> dict:
        response = httpx.post(url, headers=headers, timeout=timeout, **kwargs)
        if response.status_code >= 400:
            raise PublishError(f"facebook_graph_error:{step}:{_graph_error_detail(response)[:300]}")
        try:
            return response.json()
        except ValueError as exc:
            raise PublishError(f"facebook_graph_error:{step}:unreadable_response") from exc

    def _transfer(self, url: str, headers: dict, session_id: str, start_offset: int, chunk: bytes, name: str) -> dict:
        for attempt in range(FACEBOOK_CHUNK_ATTEMPTS):
            try:
                return self._graph_post(url, headers, "transfer", FACEBOOK_CHUNK_TIMEOUT, data={"upload_phase": "transfer", "upload_session_id": session_id, "start_offset": str(start_offset)}, files={"video_file_chunk": (name, chunk, "application/octet-stream")})
            except (httpx.TimeoutException, httpx.TransportError):
                # A chunk transfer is idempotent for its offset, so it is safe to send again.
                if attempt == FACEBOOK_CHUNK_ATTEMPTS - 1:
                    raise PublishError("facebook_chunk_transfer_failed")
                time.sleep(2 * (attempt + 1))
        raise PublishError("facebook_chunk_transfer_failed")

    def publish(self, db: Session, video: VideoVersion, account: str) -> Publication:
        settings = get_settings()
        if not all((settings.meta_page_access_token, settings.meta_page_id, settings.meta_graph_version)):
            raise PublishError("facebook_not_configured; use_manual_export")
        if not re.fullmatch(r"v\d+\.\d+", settings.meta_graph_version):
            raise PublishError("explicit_valid_meta_graph_version_required")
        if account != settings.meta_page_id:
            raise PublishError("facebook_page_mismatch")
        content = approved_content(verify_approval(db, video, "facebook", account), video, "facebook", account)
        vertical = is_vertical(video)
        publication = new_publication(db, video, "facebook", account)
        if publication.status == "PUBLISHED":
            return publication
        if publication.status == "RECONCILE_REQUIRED":
            raise PublishError("reconcile_required_before_retry")
        publication.status = "PUBLISHING"
        _enter_publishing(video)
        db.commit()
        if vertical:
            return self._publish_reel(db, publication, video, account, content["text"])
        return self._page_video(db, publication, video, account, Path(video.video_path), content["text"], {"cover": "source_frame", "custom_cover_supported": False})

    def publish_feed(self, db: Session, video: VideoVersion, account: str) -> Publication:
        """Organic Page feed post with the native 4:5 render: always a regular page video, never a Reel."""
        from app.pipeline.approvals import feed_variant

        settings = get_settings()
        if not all((settings.meta_page_access_token, settings.meta_page_id, settings.meta_graph_version)):
            raise PublishError("facebook_not_configured; use_manual_export")
        if not re.fullmatch(r"v\d+\.\d+", settings.meta_graph_version):
            raise PublishError("explicit_valid_meta_graph_version_required")
        if account != settings.meta_page_id:
            raise PublishError("facebook_page_mismatch")
        # verify_approval recomputes the digest, which binds the 4:5 file and thumbnail hashes.
        content = approved_content(verify_approval(db, video, "facebook_feed", account), video, "facebook_feed", account)
        feed = feed_variant(video)
        if feed is None:
            raise PublishError("facebook_feed_variant_missing")
        publication = new_publication(db, video, "facebook_feed", account)
        if publication.status == "PUBLISHED":
            return publication
        if publication.status == "RECONCILE_REQUIRED":
            raise PublishError("reconcile_required_before_retry")
        publication.status = "PUBLISHING"
        _enter_publishing(video)
        db.commit()
        published = self._page_video(db, publication, video, account, Path(feed["video_path"]), content["text"], {"format": "feed_4x5", "cover": "pending"})
        self._set_page_video_thumbnail(db, published, Path(feed["thumbnail_path"]))
        return published

    def _set_page_video_thumbnail(self, db: Session, publication: Publication, thumbnail: Path) -> None:
        """Best effort: the post is live either way; a rejected thumbnail is recorded, not fatal."""
        settings = get_settings()
        outcome = {"cover": "custom_thumbnail_set"}
        try:
            with thumbnail.open("rb") as handle:
                response = httpx.post(f"https://graph.facebook.com/{settings.meta_graph_version}/{publication.remote_id}/thumbnails", headers={"Authorization": f"Bearer {settings.meta_page_access_token}"}, data={"is_preferred": "true"}, files={"source": (thumbnail.name, handle, "image/jpeg")}, timeout=60)
            if response.status_code >= 400:
                outcome = {"cover": "custom_thumbnail_failed", "cover_error": _graph_error_detail(response)[:160]}
        except httpx.HTTPError as exc:
            outcome = {"cover": "custom_thumbnail_failed", "cover_error": type(exc).__name__}
        publication.response_json = {**(publication.response_json or {}), **outcome}
        db.add(AuditEvent(actor="system", action="FACEBOOK_THUMBNAIL_SET" if outcome["cover"] == "custom_thumbnail_set" else "FACEBOOK_THUMBNAIL_FAILED", entity_type="publication", entity_id=str(publication.id), details_json={"remote_id": publication.remote_id, **outcome}))
        db.commit()

    def _page_video(self, db: Session, publication: Publication, video: VideoVersion, account: str, video_path: Path, description: str, extra: dict) -> Publication:
        """Graph resumable upload of a regular page video (start/transfer/finish on graph-video)."""
        settings = get_settings()
        url = f"https://graph-video.facebook.com/{settings.meta_graph_version}/{account}/videos"
        headers = {"Authorization": f"Bearer {settings.meta_page_access_token}"}
        size = video_path.stat().st_size
        finishing = False
        try:
            started = self._graph_post(url, headers, "start", 60, data={"upload_phase": "start", "file_size": str(size)})
            session_id = started.get("upload_session_id")
            video_id = started.get("video_id")
            if not session_id or not video_id:
                raise PublishError("facebook_upload_session_missing")
            # An unfinished session publishes nothing, so failures before "finish" are plain
            # FAILED and a retry starts a new session; only an unconfirmed finish needs reconciling.
            publication.upload_session = session_id
            publication.response_json = {"video_id": video_id, "upload": "resumable"}
            db.commit()
            start_offset, end_offset = int(started["start_offset"]), int(started["end_offset"])
            chunks = 0
            with video_path.open("rb") as handle:
                while start_offset < end_offset:
                    handle.seek(start_offset)
                    moved = self._transfer(url, headers, session_id, start_offset, handle.read(end_offset - start_offset), video_path.name)
                    next_start, next_end = int(moved["start_offset"]), int(moved["end_offset"])
                    if next_start <= start_offset and next_start != next_end:
                        raise PublishError("facebook_upload_not_advancing")
                    start_offset, end_offset = next_start, next_end
                    chunks += 1
            finishing = True
            finished = self._graph_post(url, headers, "finish", 120, data={"upload_phase": "finish", "upload_session_id": session_id, "description": description})
            if not finished.get("success"):
                raise PublishError("facebook_finish_not_confirmed_reconcile")
            publication.remote_id = video_id
            publication.response_json = {"id": video_id, **extra, "upload": "resumable", "chunks": chunks, "bytes": size}
            publication.status = "PUBLISHED"
            publication.published_at = utcnow()
            _mark_success(db, publication, video)
            db.commit()
            return publication
        except httpx.TimeoutException as exc:
            if finishing:
                _mark_timeout(db, publication, video, "facebook_reconcile_required")
                raise PublishError("facebook_reconcile_required") from exc
            _mark_failure(db, publication, video, exc)
            raise PublishError("facebook_upload_timeout") from exc
        except PublishError as exc:
            if "reconcile" in str(exc):
                _mark_timeout(db, publication, video, "facebook_reconcile_required")
            else:
                _mark_failure(db, publication, video, exc)
            raise
        except Exception as exc:
            if finishing:
                _mark_timeout(db, publication, video, "facebook_reconcile_required")
            else:
                _mark_failure(db, publication, video, exc)
            raise


    def replace_with_reel(self, db: Session, old: Publication, execute: bool = False) -> dict:
        """Owner-approved fix for 9:16 videos posted before rule 13 as regular page videos.

        Order matters: publish the Reel first and delete the old page video only after the Reel is
        confirmed live, so a failure never leaves the Page without the post. Safe to re-run: an old
        publication in REPLACING continues where it stopped (retry the Reel, or retry the delete).
        """
        settings = get_settings()
        if old.platform != "facebook" or old.status not in {"PUBLISHED", "REPLACING"} or not old.remote_id:
            raise PublishError("published_facebook_publication_required")
        if (old.response_json or {}).get("format") == "reel":
            raise PublishError("already_a_reel")
        video = db.get(VideoVersion, old.video_version_id)
        if not is_vertical(video):
            raise PublishError("only_9x16_videos_are_replaced_with_reels")
        if execute and old.status == "REPLACING" and video.status == "FAILED":
            video.status = "PUBLISHING"  # a re-run after a failed Reel attempt continues the same replacement
            video.updated_at = utcnow()
            db.commit()
        verify_approval(db, video, "facebook", old.account)  # same approved file and text as the post being replaced
        plan = {"publication_id": old.id, "video_id": video.id, "old_remote_id": old.remote_id, "steps": ["publish_reel", "delete_old_page_video"]}
        if not execute:
            return {**plan, "executed": False}
        if old.status == "PUBLISHED":
            original_key = old.idempotency_key
            old.idempotency_key = f"{original_key}:replaced-by-reel:{old.id}"
            old.status = "REPLACING"
            old.response_json = {**(old.response_json or {}), "original_idempotency_key": original_key}
            db.add(AuditEvent(actor="owner-approved", action="FACEBOOK_REPLACE_WITH_REEL_STARTED", entity_type="publication", entity_id=str(old.id), details_json={"old_remote_id": old.remote_id, "video_status": video.status}))
            db.commit()
        if video.status == "PUBLISHED":
            # The state machine never reopens a published video on its own; this owner-approved
            # replacement does, and _mark_success closes it again once the Reel is live.
            video.status = "PUBLISHING"
            video.updated_at = utcnow()
            db.commit()
        reel = self.publish(db, video, old.account)
        if reel.status != "PUBLISHED" or (reel.response_json or {}).get("format") != "reel":
            raise PublishError("reel_not_confirmed_old_post_kept")
        response = httpx.delete(f"https://graph.facebook.com/{settings.meta_graph_version}/{old.remote_id}", headers={"Authorization": f"Bearer {settings.meta_page_access_token}"}, timeout=30)
        try:
            deleted = response.status_code < 400 and bool(response.json().get("success"))
        except ValueError:
            deleted = False
        if not deleted:
            old.error_code = f"delete_failed:{_graph_error_detail(response)}"[:100]
            db.commit()
            raise PublishError("reel_published_but_old_post_delete_failed_rerun_to_retry")
        old.status = "REPLACED"
        old.error_code = None
        old.response_json = {**(old.response_json or {}), "deleted_at": utcnow().isoformat(), "replaced_by_publication": reel.id, "replaced_by_remote_id": reel.remote_id}
        db.add(AuditEvent(actor="owner-approved", action="FACEBOOK_PAGE_VIDEO_REPLACED_WITH_REEL", entity_type="publication", entity_id=str(old.id), details_json={"deleted_remote_id": old.remote_id, "reel_publication": reel.id, "reel_remote_id": reel.remote_id}))
        db.commit()
        return {**plan, "executed": True, "reel_publication_id": reel.id, "reel_remote_id": reel.remote_id, "old_status": old.status}

    def _reel_status(self, base: str, headers: dict, video_id: str) -> dict:
        """Poll until the reel is published, failed, or the window closes; returns the last status."""
        deadline = time.monotonic() + FACEBOOK_REEL_POLL_SECONDS
        delay = 2.0
        while True:
            polled = httpx.get(f"{base}/{video_id}", headers=headers, params={"fields": "status"}, timeout=20)
            polled.raise_for_status()
            status = polled.json().get("status", {}) or {}
            publishing = (status.get("publishing_phase") or {}).get("status")
            if status.get("video_status") == "error" or publishing in {"complete", "error"} or time.monotonic() + delay > deadline:
                return status
            time.sleep(delay)
            delay = min(delay * 1.5, FACEBOOK_REEL_POLL_MAX_DELAY)

    def _publish_reel(self, db: Session, publication: Publication, video: VideoVersion, account: str, description: str) -> Publication:
        """Reels Publishing API: start -> binary upload to rupload -> finish(PUBLISHED) -> poll status.

        Before finish nothing is public, so failures are FAILED and a retry starts over. From finish
        on, the reel may already be live: anything short of a confirmed "complete" is RECONCILE_REQUIRED.
        """
        settings = get_settings()
        base = f"https://graph.facebook.com/{settings.meta_graph_version}"
        token = settings.meta_page_access_token
        headers = {"Authorization": f"Bearer {token}"}
        video_path = Path(video.video_path)
        size = video_path.stat().st_size
        finishing = False
        try:
            started = self._graph_post(f"{base}/{account}/video_reels", headers, "reel_start", 60, data={"upload_phase": "start"})
            video_id = started.get("video_id")
            upload_url = started.get("upload_url") or f"https://rupload.facebook.com/video-upload/{settings.meta_graph_version}/{video_id}"
            if not video_id:
                raise PublishError("facebook_reel_session_missing")
            if not upload_url.startswith("https://rupload.facebook.com/"):
                raise PublishError("facebook_reel_unexpected_upload_host")
            publication.upload_session = video_id
            publication.response_json = {"video_id": video_id, "upload": "reel"}
            db.commit()
            with video_path.open("rb") as handle:
                uploaded = httpx.post(upload_url, headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}, content=handle, timeout=FACEBOOK_REEL_UPLOAD_TIMEOUT)
            if uploaded.status_code >= 400:
                raise PublishError(f"facebook_graph_error:reel_upload:{_graph_error_detail(uploaded)[:300]}")
            try:
                upload_ok = bool(uploaded.json().get("success"))
            except ValueError:
                upload_ok = False
            if not upload_ok:
                raise PublishError("facebook_reel_upload_not_confirmed")
            finishing = True
            finished = self._graph_post(f"{base}/{account}/video_reels", headers, "reel_finish", 120, data={"upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED", "description": description})
            if not finished.get("success"):
                raise PublishError("facebook_reel_finish_not_confirmed_reconcile")
            publication.remote_id = video_id
            db.commit()
            status = self._reel_status(base, headers, video_id)
            phase = (status.get("publishing_phase") or {}).get("status")
            if phase != "complete":
                raise PublishError(f"facebook_reel_not_confirmed_reconcile:{status.get('video_status') or 'unknown'}:{phase or 'unknown'}")
            publication.response_json = {"id": video_id, "format": "reel", "video_status": status.get("video_status"), "publishing_phase": phase, "bytes": size}
            publication.status = "PUBLISHED"
            publication.published_at = utcnow()
            _mark_success(db, publication, video)
            db.commit()
            return publication
        except httpx.TimeoutException as exc:
            if finishing:
                _mark_timeout(db, publication, video, "facebook_reel_reconcile_required")
                raise PublishError("facebook_reel_reconcile_required") from exc
            _mark_failure(db, publication, video, exc)
            raise PublishError("facebook_reel_upload_timeout") from exc
        except Exception as exc:
            if finishing:
                _mark_timeout(db, publication, video, "facebook_reel_reconcile_required")
            else:
                _mark_failure(db, publication, video, exc)
            raise


class TikTokPublisher:
    api_base = "https://open.tiktokapis.com/v2"

    def capabilities(self, db: Session | None = None) -> dict:
        from app.pipeline import tiktok_auth

        settings = get_settings()
        configured = tiktok_auth.configured()
        connection = db.get(Setting, "tiktok_connection") if db is not None else None
        state = connection.value_json if connection else {}
        token = tiktok_auth.public_view(tiktok_auth.load_bundle())
        direct_post_eligible = all((settings.tiktok_direct_post_enabled, settings.tiktok_direct_post_reviewed, settings.tiktok_direct_post_consent_confirmed))
        return {"publishing_configured": configured, "oauth_verified": bool(state.get("oauth_verified")), "draft_upload_verified": bool(state.get("draft_upload_verified")), "open_id_configured": bool(tiktok_auth.open_id()), "token_store": token.get("token_store"), "auto_refresh": token.get("token_store") == "file", "refresh_expires_in_days": token.get("refresh_expires_in_days"), "relogin_required": bool(state.get("relogin_required")), "direct_post_eligible": direct_post_eligible, "direct_post_blocker": None if direct_post_eligible else "tiktok_direct_post_not_eligible", "manual_export": True}

    def _post(self, db: Session, url: str, body: dict, timeout: int) -> httpx.Response:
        """POST with a fresh token; a 401 forces one refresh and one retry, never a loop."""
        from app.pipeline import tiktok_auth

        try:
            token = tiktok_auth.access_token(db)
            response = httpx.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}, json=body, timeout=timeout)
            if response.status_code == 401 and tiktok_auth.load_bundle():
                token = tiktok_auth.access_token(db, force_refresh=True)
                response = httpx.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}, json=body, timeout=timeout)
        except tiktok_auth.TikTokAuthError as exc:
            raise PublishError(str(exc)) from exc
        return response

    def publish(self, db: Session, video: VideoVersion, account: str) -> Publication:
        from app.pipeline import tiktok_auth
        from app.pipeline.tiktok_post import EXTERNAL_VISIBILITY, creator_mismatches, normalize_post_settings, post_info

        settings = get_settings()
        if not tiktok_auth.configured():
            raise PublishError("tiktok_not_configured; use_manual_export")
        if account != tiktok_auth.open_id():
            raise PublishError("tiktok_open_id_mismatch")
        if not all((settings.tiktok_direct_post_enabled, settings.tiktok_direct_post_reviewed, settings.tiktok_direct_post_consent_confirmed)):
            raise PublishError("tiktok_direct_post_not_eligible")
        content = approved_content(verify_approval(db, video, "tiktok", account), video, "tiktok", account)
        if not content.get("tiktok"):
            # Older approvals carry no owner-chosen privacy level; TikTok forbids a default.
            raise PublishError("tiktok_post_settings_not_approved_reapprove")
        options = normalize_post_settings(content["tiktok"])
        publication = new_publication(db, video, "tiktok", account)
        if publication.status == "PUBLISHED":
            return publication
        if publication.status == "RECONCILE_REQUIRED":
            raise PublishError("reconcile_required_before_retry")
        publication.status = "PUBLISHING"
        _enter_publishing(video)
        db.commit()
        video_path = Path(video.video_path)
        size = video_path.stat().st_size
        try:
            creator = self._post(db, f"{self.api_base}/post/publish/creator_info/query/", {}, 30)
            self._raise_for_tiktok_error(creator, "creator_info")
            creator_data = creator.json().get("data", {})
            problems = creator_mismatches(options, creator_data, video.duration_seconds)
            if problems:
                raise PublishError(f"{problems[0]}_reapprove")
            started = self._post(
                db,
                f"{self.api_base}/post/publish/video/init/",
                {
                    "post_info": post_info(options, content["text"], content["ai_label"]),
                    "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1},
                },
                30,
            )
            self._raise_for_tiktok_error(started, "init")
            upload = started.json().get("data", {})
            publish_id = upload.get("publish_id")
            upload_url = upload.get("upload_url")
            if not publish_id or not upload_url:
                raise PublishError("tiktok_upload_session_missing")
            publication.upload_session = publish_id
            publication.remote_id = publish_id
            db.commit()
            with video_path.open("rb") as handle:
                uploaded = httpx.put(
                    upload_url,
                    content=handle,
                    headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{size - 1}/{size}"},
                    timeout=120,
                )
            if uploaded.status_code >= 400:
                raise PublishError("tiktok_binary_upload_failed")
            status = ""
            for _ in range(30):
                checked = self._post(db, f"{self.api_base}/post/publish/status/fetch/", {"publish_id": publish_id}, 20)
                self._raise_for_tiktok_error(checked, "status")
                status = checked.json().get("data", {}).get("status", "")
                if status == "PUBLISH_COMPLETE":
                    break
                if status == "SEND_TO_USER_INBOX":
                    raise PublishError("tiktok_unexpected_inbox_status_reconcile_required")
                if status in {"FAILED", "CANCELLED"}:
                    raise PublishError("tiktok_direct_post_failed")
                time.sleep(2)
            if status != "PUBLISH_COMPLETE":
                raise PublishError(f"tiktok_direct_post_not_finished_reconcile:{status or 'unknown'}")
            publication.remote_id = publish_id
            publication.response_json = {"publish_id": publish_id, "status": status, "external_visibility": EXTERNAL_VISIBILITY[options["privacy_level"]], "privacy_level": options["privacy_level"], "cover": "source_frame_1000ms"}
            publication.status = "PUBLISHED"
            publication.published_at = utcnow()
            _mark_success(db, publication, video)
            db.commit()
            return publication
        except httpx.TimeoutException:
            _mark_timeout(db, publication, video)
            raise PublishError("tiktok_reconcile_required")
        except Exception as exc:
            if publication.upload_session:
                _mark_timeout(db, publication, video, "tiktok_reconcile_required")
            else:
                _mark_failure(db, publication, video, exc)
            raise

    def _raise_for_tiktok_error(self, response: httpx.Response, step: str) -> None:
        if response.status_code < 400:
            return
        try:
            error = response.json().get("error", {})
            detail = f"{error.get('code', '')}:{error.get('message', '')}"
        except (ValueError, AttributeError):
            detail = "unreadable_tiktok_error"
        raise PublishError(f"tiktok_{step}_error:{detail[:300]}")
