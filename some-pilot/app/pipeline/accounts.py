"""Daily read-only connection checks for publishing accounts. Never stores or shows secrets.

YouTube: a Google app in "Testing" issues refresh tokens that typically expire
seven days after consent, so the first successful check after a (re)authorisation
is tracked and an expiry estimate is shown. Meta: the token debugger reports the
real expiry. TikTok: the user-info call proves the token works.
"""

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Setting
from app.pipeline.redact import redact

STATUS_KEY = "account_status"
YOUTUBE_TESTING_TOKEN_DAYS = 7


def _youtube(previous: dict, now: datetime) -> dict:
    settings = get_settings()
    configured = bool(settings.youtube_client_id and settings.youtube_client_secret and settings.youtube_refresh_token)
    if not configured:
        return {"configured": False, "ok": False}
    token = httpx.post("https://oauth2.googleapis.com/token", data={"client_id": settings.youtube_client_id, "client_secret": settings.youtube_client_secret, "refresh_token": settings.youtube_refresh_token, "grant_type": "refresh_token"}, timeout=20)
    if token.status_code >= 400:
        return {"configured": True, "ok": False, "error_code": f"token_refresh_http_{token.status_code}", "note": "Re-authorise the YouTube app; Testing-mode tokens expire."}
    body = token.json()
    channel = httpx.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "id,snippet", "mine": "true"}, headers={"Authorization": f"Bearer {body['access_token']}"}, timeout=20)
    if channel.status_code >= 400:
        return {"configured": True, "ok": False, "error_code": f"channels_http_{channel.status_code}"}
    items = channel.json().get("items", [])
    fingerprint = _hint(settings.youtube_refresh_token)
    first_ok = previous.get("first_ok_at") if previous.get("token_fingerprint_hint") == fingerprint else None
    first_ok = first_ok or now.isoformat()
    expires = datetime.fromisoformat(first_ok) + timedelta(days=YOUTUBE_TESTING_TOKEN_DAYS)
    return {"configured": True, "ok": True, "account_id": items[0]["id"] if items else None, "account_name": items[0]["snippet"].get("title") if items else None, "scopes": body.get("scope", "").split(), "first_ok_at": first_ok, "token_fingerprint_hint": fingerprint, "expires_estimate": expires.isoformat(), "expires_in_days": max(0, (expires - now).days), "note": "Estimate for an app in Google 'Testing' mode; production apps do not expire this way."}


def _hint(value: str) -> str:
    # A non-reversible marker to notice a changed token without storing it.
    import hashlib

    return hashlib.sha256(value.encode()).hexdigest()[:8]


def _meta(now: datetime) -> dict:
    settings = get_settings()
    token = settings.meta_page_access_token or settings.meta_access_token
    if not (token and settings.meta_graph_version):
        return {"configured": False, "ok": False}
    base = f"https://graph.facebook.com/{settings.meta_graph_version}"
    me = httpx.get(f"{base}/me", params={"fields": "id,name", "access_token": token}, timeout=20)
    if me.status_code >= 400:
        return {"configured": True, "ok": False, "error_code": f"me_http_{me.status_code}"}
    result = {"configured": True, "ok": True, "account_id": me.json().get("id"), "account_name": me.json().get("name")}
    if settings.meta_app_id and settings.meta_app_secret:
        debug = httpx.get(f"{base}/debug_token", params={"input_token": token, "access_token": f"{settings.meta_app_id}|{settings.meta_app_secret}"}, timeout=20)
        if debug.status_code < 400:
            data = debug.json().get("data", {})
            result["scopes"] = data.get("scopes", [])
            expires_at = data.get("expires_at") or data.get("data_access_expires_at")
            if expires_at:
                expiry = datetime.fromtimestamp(int(expires_at), timezone.utc)
                result["expires_estimate"] = expiry.isoformat()
                result["expires_in_days"] = max(0, (expiry - now).days)
            else:
                result["note"] = "Token reports no expiry (long-lived page/system user token)."
    return result


def _tiktok(now: datetime) -> dict:
    settings = get_settings()
    if not settings.tiktok_access_token:
        return {"configured": False, "ok": False}
    response = httpx.get("https://open.tiktokapis.com/v2/user/info/", params={"fields": "open_id,display_name"}, headers={"Authorization": f"Bearer {settings.tiktok_access_token}"}, timeout=20)
    if response.status_code >= 400:
        return {"configured": True, "ok": False, "error_code": f"user_info_http_{response.status_code}", "note": "TikTok access tokens are short-lived; refresh or re-authorise."}
    user = response.json().get("data", {}).get("user", {})
    return {"configured": True, "ok": True, "account_id": user.get("open_id"), "account_name": user.get("display_name"), "direct_post_eligible": all((settings.tiktok_direct_post_enabled, settings.tiktok_direct_post_reviewed, settings.tiktok_direct_post_consent_confirmed))}


def probe_accounts(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    previous = db.get(Setting, STATUS_KEY)
    previous_platforms = (previous.value_json if previous else {}).get("platforms", {})
    platforms = {}
    for name, probe in (("youtube", lambda: _youtube(previous_platforms.get("youtube", {}), now)), ("meta", lambda: _meta(now)), ("tiktok", lambda: _tiktok(now))):
        try:
            result = probe()
        except Exception as exc:
            result = {"configured": True, "ok": False, "error_code": type(exc).__name__, "note": redact(str(exc))[:200]}
        result["checked_at"] = now.isoformat()
        if result.get("ok"):
            result["last_ok_at"] = now.isoformat()
        else:
            result["last_ok_at"] = previous_platforms.get(name, {}).get("last_ok_at")
        platforms[name] = result
    value = {"checked_at": now.isoformat(), "platforms": platforms}
    db.merge(Setting(key=STATUS_KEY, value_json=value))
    db.commit()
    return value
