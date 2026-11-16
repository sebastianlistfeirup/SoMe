"""TikTok: token refresh that survives restarts, and Direct Post choices bound into the approval."""

import json
import os
import stat
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.db.models import Setting
from app.pipeline import tiktok_auth
from app.pipeline.approvals import ApprovalError, approve, approve_destinations, approved_content, destinations_digest, verify_approval
from app.pipeline.platforms import PublishError, TikTokPublisher
from app.pipeline.redact import redact
from app.pipeline.tiktok_post import BRANDED_CONSENT, MUSIC_CONSENT, creator_mismatches, normalize_post_settings, post_info

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
OLD_ACCESS = "act.old-access-token-value"
OLD_REFRESH = "rft.old-refresh-token-value"
NEW_ACCESS = "act.new-access-token-value"
NEW_REFRESH = "rft.new-refresh-token-value"
CREATOR = {"creator_nickname": "Pixel & Parameters", "creator_username": "pixelandparameters", "privacy_level_options": ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"], "comment_disabled": False, "duet_disabled": True, "stitch_disabled": False, "max_video_post_duration_sec": 600}


class Response:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def connect(monkeypatch, expires_in=timedelta(hours=20), refresh_in=timedelta(days=300)):
    settings = get_settings()
    monkeypatch.setattr(settings, "tiktok_client_key", "client-key-1")
    monkeypatch.setattr(settings, "tiktok_client_secret", "client-secret-value")
    tiktok_auth.save_bundle({
        "access_token": OLD_ACCESS,
        "refresh_token": OLD_REFRESH,
        "open_id": "open-1",
        "scope": "user.info.basic,video.publish,video.upload",
        "client_key": "client-key-1",
        "issued_at": (NOW - timedelta(hours=4)).isoformat(),
        "expires_at": (NOW + expires_in).isoformat(),
        "refresh_expires_at": (NOW + refresh_in).isoformat(),
        "authorized_at": (NOW - timedelta(days=1)).isoformat(),
    })


def refresh_endpoint(calls, access=NEW_ACCESS, refresh=NEW_REFRESH, status=200, body=None):
    def post(url, **kwargs):
        calls.append((url, kwargs))
        assert url == tiktok_auth.TOKEN_URL
        if body is not None:
            return Response(body, status)
        return Response({"access_token": access, "expires_in": 86400, "open_id": "open-1", "refresh_expires_in": 31536000, "refresh_token": refresh, "scope": "user.info.basic,video.publish,video.upload", "token_type": "Bearer"}, status)

    return post


def route(token_post, api_post):
    """httpx is one module: the token endpoint and the posting API share httpx.post in tests."""
    return lambda url, **kwargs: token_post(url, **kwargs) if url == tiktok_auth.TOKEN_URL else api_post(url, **kwargs)


def enable_direct_post(monkeypatch):
    settings = get_settings()
    for name, value in {"dry_run": False, "publish_enabled": True, "tiktok_direct_post_enabled": True, "tiktok_direct_post_reviewed": True, "tiktok_direct_post_consent_confirmed": True}.items():
        monkeypatch.setattr(settings, name, value)


def tiktok_destination(**choices):
    return {"platform": "tiktok", "account": "open-1", "visibility": "public", "publish_at": None, "digest_version": 2, "ai_label": True, "tiktok": {"privacy_level": "MUTUAL_FOLLOW_FRIENDS", "allow_comment": True, "allow_duet": False, "allow_stitch": True, **choices}}


# --- token store and refresh -------------------------------------------------------------------


def test_token_store_is_private_file_and_fresh_token_is_not_refreshed(db, monkeypatch, isolated_tiktok_token_store):
    connect(monkeypatch)
    monkeypatch.setattr(tiktok_auth.httpx, "post", lambda *a, **k: pytest.fail("fresh token must not be refreshed"))
    assert tiktok_auth.access_token(db, NOW) == OLD_ACCESS
    if os.name == "posix":
        assert stat.S_IMODE(isolated_tiktok_token_store.stat().st_mode) == 0o600
    assert tiktok_auth.open_id() == "open-1" and tiktok_auth.configured()


def test_token_near_expiry_is_refreshed_and_survives_restart(db, monkeypatch, isolated_tiktok_token_store):
    connect(monkeypatch, expires_in=timedelta(minutes=20))
    calls = []
    monkeypatch.setattr(tiktok_auth.httpx, "post", refresh_endpoint(calls))
    assert tiktok_auth.access_token(db, NOW) == NEW_ACCESS
    assert len(calls) == 1
    sent = calls[0][1]["data"]
    assert sent["grant_type"] == "refresh_token" and sent["refresh_token"] == OLD_REFRESH and sent["client_key"] == "client-key-1"
    # A restart only has the file: the rotated refresh token and new expiry must be there.
    stored = json.loads(isolated_tiktok_token_store.read_text(encoding="utf-8"))
    assert stored["access_token"] == NEW_ACCESS and stored["refresh_token"] == NEW_REFRESH
    assert stored["expires_at"] == (NOW + timedelta(seconds=86400)).isoformat()
    assert stored["refresh_expires_at"] == (NOW + timedelta(seconds=31536000)).isoformat()
    monkeypatch.setattr(tiktok_auth.httpx, "post", lambda *a, **k: pytest.fail("refreshed token is valid"))
    assert tiktok_auth.access_token(db, NOW + timedelta(hours=1)) == NEW_ACCESS
    # The DB only gets non-secret metadata.
    connection = json.dumps(db.get(Setting, "tiktok_connection").value_json)
    for secret in (OLD_ACCESS, OLD_REFRESH, NEW_ACCESS, NEW_REFRESH, "client-secret-value"):
        assert secret not in connection
    assert db.get(Setting, "tiktok_connection").value_json["oauth_verified"] is True


def test_forced_refresh_keeps_refresh_token_when_tiktok_does_not_rotate_it(db, monkeypatch, isolated_tiktok_token_store):
    connect(monkeypatch)
    calls = []
    monkeypatch.setattr(tiktok_auth.httpx, "post", refresh_endpoint(calls, refresh=None))
    assert tiktok_auth.access_token(db, NOW, force_refresh=True) == NEW_ACCESS
    assert json.loads(isolated_tiktok_token_store.read_text())["refresh_token"] == OLD_REFRESH


def test_rejected_refresh_marks_relogin_and_never_leaks_token(db, monkeypatch):
    connect(monkeypatch, expires_in=timedelta(minutes=5))
    calls = []
    monkeypatch.setattr(tiktok_auth.httpx, "post", refresh_endpoint(calls, status=400, body={"error": "invalid_grant", "error_description": "Refresh token is invalid or expired."}))
    with pytest.raises(tiktok_auth.TikTokAuthError, match="invalid_grant") as raised:
        tiktok_auth.access_token(db, NOW)
    assert OLD_REFRESH not in str(raised.value)
    state = db.get(Setting, "tiktok_connection").value_json
    assert state["relogin_required"] is True and state["oauth_verified"] is False
    assert len(calls) == 1


def test_expired_refresh_token_or_changed_app_requires_login(db, monkeypatch):
    connect(monkeypatch, expires_in=timedelta(minutes=5), refresh_in=timedelta(days=-1))
    monkeypatch.setattr(tiktok_auth.httpx, "post", lambda *a, **k: pytest.fail("expired refresh token must not be sent"))
    with pytest.raises(tiktok_auth.TikTokAuthError, match="refresh_token_expired"):
        tiktok_auth.access_token(db, NOW)
    connect(monkeypatch, expires_in=timedelta(minutes=5))
    monkeypatch.setattr(get_settings(), "tiktok_client_key", "production-client-key")
    with pytest.raises(tiktok_auth.TikTokAuthError, match="client_key_changed"):
        tiktok_auth.access_token(db, NOW)


def test_env_token_without_store_still_works_but_cannot_be_force_refreshed(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "tiktok_access_token", "legacy-env-token")
    monkeypatch.setattr(get_settings(), "tiktok_open_id", "open-env")
    assert tiktok_auth.access_token(db, NOW) == "legacy-env-token"
    with pytest.raises(tiktok_auth.TikTokAuthError, match="login_required"):
        tiktok_auth.access_token(db, NOW, force_refresh=True)


def test_redaction_covers_refreshed_tokens(monkeypatch):
    connect(monkeypatch)
    text = redact(f"failed with {OLD_ACCESS} and {OLD_REFRESH}")
    assert OLD_ACCESS not in text and OLD_REFRESH not in text


def test_probe_refreshes_tiktok_and_survives_forced_refresh(db, monkeypatch):
    from app.pipeline import accounts

    for field in ("youtube_client_id", "meta_access_token", "meta_page_access_token"):
        monkeypatch.setattr(get_settings(), field, "")
    connect(monkeypatch, expires_in=timedelta(minutes=10))
    calls = []
    monkeypatch.setattr(tiktok_auth.httpx, "post", refresh_endpoint(calls))
    seen = []

    def user_info(url, **kwargs):
        seen.append(kwargs["headers"]["Authorization"])
        return Response({"data": {"user": {"open_id": "open-1", "display_name": "Pixel & Parameters"}}})

    monkeypatch.setattr(accounts.httpx, "get", user_info)
    result = accounts.probe_accounts(db, NOW)
    tiktok = result["platforms"]["tiktok"]
    assert tiktok["ok"] and tiktok["auto_refresh"] and tiktok["account_name"] == "Pixel & Parameters"
    assert seen == [f"Bearer {NEW_ACCESS}"] and len(calls) == 1
    monkeypatch.setattr(tiktok_auth.httpx, "post", refresh_endpoint(calls, access="act.forced-token-value", refresh="rft.forced-refresh-value"))
    forced = accounts.probe_accounts(db, NOW + timedelta(minutes=5), force_tiktok_refresh=True)
    assert forced["platforms"]["tiktok"]["ok"] and forced["platforms"]["tiktok"]["forced_refresh"] is True
    assert seen[-1] == "Bearer act.forced-token-value" and len(calls) == 2
    stored = json.dumps(db.get(Setting, "account_status").value_json) + json.dumps(db.get(Setting, "tiktok_connection").value_json)
    for secret in (OLD_ACCESS, OLD_REFRESH, NEW_ACCESS, NEW_REFRESH, "act.forced-token-value", "rft.forced-refresh-value"):
        assert secret not in stored


def test_probe_retries_once_with_forced_refresh_after_401(db, monkeypatch):
    from app.pipeline import accounts

    for field in ("youtube_client_id", "meta_access_token", "meta_page_access_token"):
        monkeypatch.setattr(get_settings(), field, "")
    connect(monkeypatch)
    calls = []
    monkeypatch.setattr(tiktok_auth.httpx, "post", refresh_endpoint(calls))
    responses = [Response({"error": {"code": "access_token_invalid"}}, 401), Response({"data": {"user": {"open_id": "open-1", "display_name": "P&P"}}})]
    monkeypatch.setattr(accounts.httpx, "get", lambda *a, **k: responses.pop(0))
    assert accounts.probe_accounts(db, NOW)["platforms"]["tiktok"]["ok"]
    assert len(calls) == 1 and not responses


def test_probe_reports_missing_login(db, monkeypatch):
    from app.pipeline import accounts

    for field in ("youtube_client_id", "meta_access_token", "meta_page_access_token"):
        monkeypatch.setattr(get_settings(), field, "")
    result = accounts.probe_accounts(db, NOW)["platforms"]["tiktok"]
    assert result["configured"] is False and result["ok"] is False


# --- Direct Post choices ----------------------------------------------------------------------


def test_post_settings_have_no_default_and_validate_disclosure():
    with pytest.raises(ApprovalError, match="tiktok_post_settings_required"):
        normalize_post_settings(None)
    with pytest.raises(ApprovalError, match="tiktok_privacy_level_required"):
        normalize_post_settings({"allow_comment": True})
    with pytest.raises(ApprovalError, match="commercial_content_type_required"):
        normalize_post_settings({"privacy_level": "PUBLIC_TO_EVERYONE", "commercial_disclosure": True})
    with pytest.raises(ApprovalError, match="branded_content_cannot_be_private"):
        normalize_post_settings({"privacy_level": "SELF_ONLY", "commercial_disclosure": True, "brand_content_toggle": True})
    plain = normalize_post_settings({"privacy_level": "SELF_ONLY", "brand_content_toggle": True})
    assert plain["brand_content_toggle"] is False and plain["consent_text"] == MUSIC_CONSENT
    assert plain["allow_comment"] is plain["allow_duet"] is plain["allow_stitch"] is False
    branded = normalize_post_settings({"privacy_level": "PUBLIC_TO_EVERYONE", "commercial_disclosure": "true", "brand_content_toggle": "on"})
    assert branded["consent_text"] == BRANDED_CONSENT
    assert normalize_post_settings(branded) == branded
    assert MUSIC_CONSENT == "By posting, you agree to TikTok's Music Usage Confirmation"


def test_creator_flags_and_options_are_respected():
    options = normalize_post_settings({"privacy_level": "FOLLOWER_OF_CREATOR", "allow_duet": True})
    problems = creator_mismatches(options, CREATOR, 700)
    assert problems == ["tiktok_privacy_level_not_offered", "tiktok_duet_disabled_by_creator", "tiktok_video_longer_than_creator_limit"]
    info = post_info(normalize_post_settings({"privacy_level": "SELF_ONLY", "allow_comment": True}), "caption", None)
    assert info["privacy_level"] == "SELF_ONLY" and info["disable_comment"] is False and info["disable_duet"] is True and "is_aigc" not in info


def test_tiktok_approval_requires_choices_and_binds_them_into_digest(db, awaiting_video, monkeypatch):
    with pytest.raises(ApprovalError, match="tiktok_post_settings_required"):
        approve_destinations(db, awaiting_video, "owner", [{"platform": "tiktok", "account": "open-1", "digest_version": 2}], True)
    base = destinations_digest(awaiting_video, [tiktok_destination()])
    for change in ({"privacy_level": "SELF_ONLY"}, {"allow_comment": False}, {"allow_stitch": False}, {"commercial_disclosure": True, "brand_organic_toggle": True}):
        assert destinations_digest(awaiting_video, [tiktok_destination(**change)])["approval_sha256"] != base["approval_sha256"]
    assert base["destinations"][0]["tiktok"]["consent_text"] == MUSIC_CONSENT
    enable_direct_post(monkeypatch)
    review = approve_destinations(db, awaiting_video, "owner", [tiktok_destination()], True)
    assert approved_content(review, awaiting_video, "tiktok", "open-1")["tiktok"]["privacy_level"] == "MUTUAL_FOLLOW_FRIENDS"
    assert verify_approval(db, awaiting_video, "tiktok", "open-1").id == review.id
    # Changing the approved choice after the fact invalidates the approval.
    digest = dict(review.digest_json)
    digest["destinations"] = [{**digest["destinations"][0], "tiktok": {**digest["destinations"][0]["tiktok"], "privacy_level": "PUBLIC_TO_EVERYONE"}}]
    review.digest_json = digest
    db.commit()
    with pytest.raises(ApprovalError, match="approval_invalidated_by_change"):
        verify_approval(db, awaiting_video, "tiktok", "open-1")


def _tiktok_api(calls, creator=CREATOR, first_status=200):
    statuses = [first_status]

    def post(url, **kwargs):
        calls.append((url, kwargs))
        assert "/inbox/" not in url
        if "creator_info" in url:
            status = statuses.pop(0) if statuses else 200
            return Response({"data": creator} if status == 200 else {"error": {"code": "access_token_invalid"}}, status)
        if url.endswith("/video/init/"):
            return Response({"data": {"publish_id": "publish-1", "upload_url": "https://upload.example/file"}})
        return Response({"data": {"status": "PUBLISH_COMPLETE"}})

    return post


def test_publisher_sends_exactly_the_approved_choices_with_refreshed_token(db, awaiting_video, monkeypatch):
    connect(monkeypatch, expires_in=timedelta(minutes=10))
    enable_direct_post(monkeypatch)
    approve_destinations(db, awaiting_video, "owner", [tiktok_destination(commercial_disclosure=True, brand_organic_toggle=True)], True)
    refreshes, calls = [], []
    monkeypatch.setattr("app.pipeline.platforms.httpx.post", route(refresh_endpoint(refreshes), _tiktok_api(calls)))
    monkeypatch.setattr("app.pipeline.platforms.httpx.put", lambda *_a, **_k: Response({}))
    publication = TikTokPublisher().publish(db, awaiting_video, "open-1")
    assert publication.status == "PUBLISHED"
    assert publication.response_json["external_visibility"] == "friends"
    info = next(call for call in calls if call[0].endswith("/video/init/"))[1]["json"]["post_info"]
    assert info["privacy_level"] == "MUTUAL_FOLLOW_FRIENDS"
    assert (info["disable_comment"], info["disable_duet"], info["disable_stitch"]) == (False, True, False)
    assert info["brand_organic_toggle"] is True and info["brand_content_toggle"] is False and info["is_aigc"] is True
    assert len(refreshes) == 1
    assert all(call[1]["headers"]["Authorization"] == f"Bearer {NEW_ACCESS}" for call in calls)


def test_publisher_refreshes_once_on_401(db, awaiting_video, monkeypatch):
    connect(monkeypatch)
    enable_direct_post(monkeypatch)
    approve_destinations(db, awaiting_video, "owner", [tiktok_destination()], True)
    refreshes, calls = [], []
    monkeypatch.setattr("app.pipeline.platforms.httpx.post", route(refresh_endpoint(refreshes), _tiktok_api(calls, first_status=401)))
    monkeypatch.setattr("app.pipeline.platforms.httpx.put", lambda *_a, **_k: Response({}))
    assert TikTokPublisher().publish(db, awaiting_video, "open-1").status == "PUBLISHED"
    assert len(refreshes) == 1
    assert calls[0][1]["headers"]["Authorization"] == f"Bearer {OLD_ACCESS}" and calls[1][1]["headers"]["Authorization"] == f"Bearer {NEW_ACCESS}"


def test_publisher_refuses_legacy_approval_and_changed_creator_settings(db, awaiting_video, monkeypatch):
    connect(monkeypatch)
    enable_direct_post(monkeypatch)
    monkeypatch.setattr("app.pipeline.platforms.httpx.post", lambda *a, **k: pytest.fail("TikTok must not be called"))
    approve(db, awaiting_video, "owner", "tiktok", "open-1", True)
    with pytest.raises(PublishError, match="tiktok_post_settings_not_approved"):
        TikTokPublisher().publish(db, awaiting_video, "open-1")


def test_publisher_stops_before_upload_when_creator_disabled_an_approved_toggle(db, awaiting_video, monkeypatch):
    connect(monkeypatch)
    enable_direct_post(monkeypatch)
    approve_destinations(db, awaiting_video, "owner", [tiktok_destination()], True)
    calls = []
    monkeypatch.setattr("app.pipeline.platforms.httpx.post", _tiktok_api(calls, creator={**CREATOR, "comment_disabled": True}))
    with pytest.raises(PublishError, match="tiktok_comment_disabled_by_creator_reapprove"):
        TikTokPublisher().publish(db, awaiting_video, "open-1")
    assert not any(call[0].endswith("/video/init/") for call in calls)


def test_direct_post_gate_still_blocks_without_review_flags(db, awaiting_video, monkeypatch):
    connect(monkeypatch)
    monkeypatch.setattr(get_settings(), "dry_run", False)
    monkeypatch.setattr(get_settings(), "publish_enabled", True)
    monkeypatch.setattr("app.pipeline.platforms.httpx.post", lambda *a, **k: pytest.fail("ineligible Direct Post reached TikTok"))
    with pytest.raises(PublishError, match="tiktok_direct_post_not_eligible"):
        TikTokPublisher().publish(db, awaiting_video, "open-1")
    assert TikTokPublisher().capabilities(db)["auto_refresh"] is True


# --- review page ------------------------------------------------------------------------------


def _client(db):
    from argon2 import PasswordHasher
    from fastapi.testclient import TestClient

    from app.db.models import AuthUser
    from app.db.session import get_db
    from app.main import app

    db.add(AuthUser(username="owner", password_hash=PasswordHasher().hash("a-secure-test-password")))
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://testserver")
    assert client.post("/login", data={"username": "owner", "password": "a-secure-test-password"}, follow_redirects=False).status_code == 303
    return app, client


def test_review_page_shows_tiktok_creator_choices_and_approval_binds_them(db, awaiting_video, monkeypatch):
    import re

    connect(monkeypatch)
    monkeypatch.setattr("app.pipeline.tiktok_post.httpx.post", lambda *a, **k: Response({"data": CREATOR, "error": {"code": "ok"}}))
    app, client = _client(db)
    try:
        page = client.get(f"/review/{awaiting_video.id}").text
        assert "Pixel &amp; Parameters" in page and "@pixelandparameters" in page
        assert '<option value="" selected disabled>Select privacy level</option>' in page
        assert 'value="FOLLOWER_OF_CREATOR"' not in page and 'value="MUTUAL_FOLLOW_FRIENDS"' in page
        assert re.search(r'name="tiktok_allow_duet" value="true" disabled', page)
        assert "Disclose video content" in page and "Your brand" in page and "Branded content" in page
        assert "By posting, you agree to TikTok&#39;s Music Usage Confirmation" in page
        assert re.search(r'value="tiktok" data-tiktok-destination disabled', page), "TikTok cannot be chosen before the review flags are set"
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        form = {"csrf_token": token, "platforms": ["tiktok"], "watched": "true", "ai_labels_present": "true", "ai_labels": ["tiktok"], "tiktok_privacy_level": "MUTUAL_FOLLOW_FRIENDS", "tiktok_allow_comment": "true", "tiktok_allow_stitch": "true"}
        refused = client.post(f"/review/{awaiting_video.id}/approve", data=form, follow_redirects=False)
        assert refused.status_code == 409 and "tiktok_direct_post_not_eligible" in refused.text
        enable_direct_post(monkeypatch)
        missing = client.post(f"/review/{awaiting_video.id}/approve", data={**form, "tiktok_privacy_level": ""}, follow_redirects=False)
        assert missing.status_code == 409 and "tiktok_privacy_level_required" in missing.text
        blocked = client.post(f"/review/{awaiting_video.id}/approve", data={**form, "tiktok_allow_duet": "true"}, follow_redirects=False)
        assert blocked.status_code == 409 and "duet_disabled_by_creator" in blocked.text
        approved = client.post(f"/review/{awaiting_video.id}/approve", data=form, follow_redirects=False)
        assert approved.status_code == 303
        db.refresh(awaiting_video)
        review = verify_approval(db, awaiting_video, "tiktok", "open-1")
        choice = review.digest_json["destinations"][0]["tiktok"]
        assert choice == {"privacy_level": "MUTUAL_FOLLOW_FRIENDS", "allow_comment": True, "allow_duet": False, "allow_stitch": True, "commercial_disclosure": False, "brand_organic_toggle": False, "brand_content_toggle": False, "consent_text": MUSIC_CONSENT}
    finally:
        app.dependency_overrides.clear()


def test_review_page_without_tiktok_login_disables_tiktok(db, awaiting_video):
    app, client = _client(db)
    try:
        page = client.get(f"/review/{awaiting_video.id}").text
        assert "tiktok_not_connected_login_required" in page
        assert 'value="tiktok" data-tiktok-destination disabled' in page
    finally:
        app.dependency_overrides.clear()
