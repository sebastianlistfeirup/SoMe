"""TikTok OAuth token store with automatic refresh.

TikTok access tokens live about 24 hours; refresh tokens about 365 days. The
OAuth helper writes the first token bundle to a 0600 JSON file under the data
volume, and this module refreshes it before it expires and writes the new
bundle back atomically, so it survives restarts. The container cannot write
app.env, so the file is the source of truth once it exists; an access token in
app.env is only a short-lived fallback without refresh.

Token values never leave this module: callers get the bearer string for one
request, and every status/metadata view is built from non-secret fields only.
The DB Setting ``tiktok_connection`` holds the non-secret metadata.
"""

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Setting

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TOKEN_FILE_NAME = "tiktok_oauth.json"
# Refresh this long before the access token expires, so a long upload never starts on a dying token.
REFRESH_MARGIN = timedelta(minutes=60)
CONNECTION_KEY = "tiktok_connection"


class TikTokAuthError(RuntimeError):
    pass


def token_path() -> Path:
    return Path(get_settings().data_dir) / "secrets" / TOKEN_FILE_NAME


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def load_bundle() -> dict | None:
    path = token_path()
    if not path.is_file():
        return None
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return bundle if isinstance(bundle, dict) and bundle.get("access_token") else None


def save_bundle(bundle: dict) -> None:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    descriptor, temporary = tempfile.mkstemp(prefix=".tiktok-", dir=path.parent)  # created 0600
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(bundle, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


@contextmanager
def _refresh_lock():
    """Web and worker share the file; only one of them may rotate the refresh token at a time."""
    path = token_path().with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl
    except ImportError:  # Windows development machines: single process, no lock needed.
        yield
        return
    with path.open("a+") as handle:
        os.chmod(path, 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def bundle_from_token_response(body: dict, client_key: str, now: datetime | None = None, previous: dict | None = None) -> dict:
    """Normalise a /v2/oauth/token/ response (authorization_code or refresh_token grant)."""
    now = _now(now)
    data = body.get("data", body) if isinstance(body.get("data"), dict) else body
    if not data.get("access_token"):
        raise TikTokAuthError("tiktok_token_response_missing_access_token")
    previous = previous or {}
    refresh_token = data.get("refresh_token") or previous.get("refresh_token")
    if not refresh_token:
        raise TikTokAuthError("tiktok_token_response_missing_refresh_token")
    expires_in = int(data.get("expires_in") or 0)
    refresh_expires_in = data.get("refresh_expires_in")
    refresh_expires_at = (now + timedelta(seconds=int(refresh_expires_in))).isoformat() if refresh_expires_in else previous.get("refresh_expires_at")
    return {
        "access_token": data["access_token"],
        "refresh_token": refresh_token,
        "open_id": data.get("open_id") or previous.get("open_id", ""),
        "scope": data.get("scope") or previous.get("scope", ""),
        "token_type": data.get("token_type", "Bearer"),
        "client_key": client_key,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=expires_in)).isoformat() if expires_in else now.isoformat(),
        "refresh_expires_at": refresh_expires_at,
        "authorized_at": previous.get("authorized_at") or now.isoformat(),
    }


def public_view(bundle: dict | None, now: datetime | None = None) -> dict:
    """Non-secret facts about the stored token, safe for the DB, the UI and logs."""
    if not bundle:
        return {"token_store": "missing"}
    now = _now(now)
    expires = _parse_time(bundle.get("expires_at"))
    refresh_expires = _parse_time(bundle.get("refresh_expires_at"))
    return {
        "token_store": "file",
        "open_id": bundle.get("open_id", ""),
        "scopes": sorted(filter(None, (bundle.get("scope") or "").replace(" ", ",").split(","))),
        "access_expires_at": expires.isoformat() if expires else None,
        "access_expires_in_minutes": max(0, int((expires - now).total_seconds() // 60)) if expires else None,
        "refresh_expires_at": refresh_expires.isoformat() if refresh_expires else None,
        "refresh_expires_in_days": max(0, (refresh_expires - now).days) if refresh_expires else None,
        "last_refresh_at": bundle.get("last_refresh_at"),
        "authorized_at": bundle.get("authorized_at"),
    }


def _record(db: Session | None, values: dict) -> None:
    if db is None:
        return
    setting = db.get(Setting, CONNECTION_KEY)
    state = dict(setting.value_json) if setting else {}
    state.update(values)
    if setting:
        setting.value_json = state
    else:
        db.add(Setting(key=CONNECTION_KEY, value_json=state))
    db.commit()


def _needs_refresh(bundle: dict, now: datetime) -> bool:
    expires = _parse_time(bundle.get("expires_at"))
    return expires is None or expires - REFRESH_MARGIN <= now


def _token_error(response: httpx.Response) -> str | None:
    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            return f"http_{response.status_code}"
        return f"http_{response.status_code}:{body.get('error') or (body.get('data') or {}).get('error_code') or ''}"[:120]
    try:
        body = response.json()
    except ValueError:
        return "unreadable_token_response"
    error = body.get("error")
    if isinstance(error, dict):
        error = error.get("code") if error.get("code") not in {None, "", "ok"} else None
    return str(error)[:120] if error else None


def refresh(db: Session | None = None, now: datetime | None = None, force: bool = False) -> dict:
    """Refresh the stored token if it is near expiry (or always when ``force``); returns the bundle."""
    settings = get_settings()
    now = _now(now)
    with _refresh_lock():
        bundle = load_bundle()
        if bundle is None:
            raise TikTokAuthError("tiktok_not_connected_login_required")
        if not force and not _needs_refresh(bundle, now):
            return bundle  # another process refreshed it while we waited for the lock
        refresh_expires = _parse_time(bundle.get("refresh_expires_at"))
        if not bundle.get("refresh_token") or (refresh_expires and refresh_expires <= now):
            _record(db, {"oauth_verified": False, "relogin_required": True, "last_refresh_error": "refresh_token_expired"})
            raise TikTokAuthError("tiktok_refresh_token_expired_login_required")
        if not (settings.tiktok_client_key and settings.tiktok_client_secret):
            raise TikTokAuthError("tiktok_client_credentials_missing")
        if bundle.get("client_key") and bundle["client_key"] != settings.tiktok_client_key:
            _record(db, {"oauth_verified": False, "relogin_required": True, "last_refresh_error": "client_key_changed"})
            raise TikTokAuthError("tiktok_client_key_changed_login_required")
        response = httpx.post(
            TOKEN_URL,
            data={"client_key": settings.tiktok_client_key, "client_secret": settings.tiktok_client_secret, "grant_type": "refresh_token", "refresh_token": bundle["refresh_token"]},
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
            timeout=30,
        )
        error = _token_error(response)
        if error:
            # invalid_grant and friends mean the owner must log in again; never retry in a loop.
            relogin = "invalid" in error or response.status_code in {400, 401}
            _record(db, {"oauth_verified": not relogin and bool(bundle), "relogin_required": relogin, "last_refresh_error": error, "last_refresh_attempt_at": now.isoformat()})
            raise TikTokAuthError(f"tiktok_token_refresh_failed:{error}")
        renewed = bundle_from_token_response(response.json(), settings.tiktok_client_key, now, previous=bundle)
        renewed["last_refresh_at"] = now.isoformat()
        save_bundle(renewed)
    _record(db, {**public_view(renewed, now), "oauth_verified": True, "relogin_required": False, "last_refresh_error": None})
    return renewed


def access_token(db: Session | None = None, now: datetime | None = None, force_refresh: bool = False) -> str:
    """A bearer token valid for at least REFRESH_MARGIN, refreshing it first when needed."""
    now = _now(now)
    bundle = load_bundle()
    if bundle is None:
        token = get_settings().tiktok_access_token
        if not token:
            raise TikTokAuthError("tiktok_not_connected_login_required")
        if force_refresh:
            raise TikTokAuthError("tiktok_no_refresh_token_login_required")
        return token  # legacy env token: works until it expires, then the owner logs in again
    if force_refresh or _needs_refresh(bundle, now):
        bundle = refresh(db, now, force=force_refresh)
    return bundle["access_token"]


def open_id() -> str:
    bundle = load_bundle()
    return (bundle or {}).get("open_id") or get_settings().tiktok_open_id


def configured() -> bool:
    return bool(load_bundle() or get_settings().tiktok_access_token) and bool(open_id())


def secret_values() -> list[str]:
    """Current token strings, for the redaction filter only."""
    bundle = load_bundle() or {}
    return [value for value in (bundle.get("access_token"), bundle.get("refresh_token")) if value]
