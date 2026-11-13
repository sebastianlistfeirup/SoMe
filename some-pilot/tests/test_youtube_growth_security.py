import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import AuthUser, IdeaSuggestion, Observation, Publication, Setting
from app.pipeline import monetization, pronunciation, releases, totp, youtube_extras

NOW = datetime.now(timezone.utc)


class Response:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text or json.dumps(self._body)
        self.headers = {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


# --- captions, playlists, chapters --------------------------------------------

def test_captions_are_shifted_by_the_brand_intro():
    srt = "1\n00:00:00,000 --> 00:00:02,500\nHello\n\n2\n00:00:59,900 --> 00:01:01,000\nWorld\n"
    shifted = youtube_extras.shifted_srt(srt, 3.5)
    assert "00:00:03,500 --> 00:00:06,000" in shifted and "00:01:03,400 --> 00:01:04,500" in shifted


def test_upload_captions_reports_missing_scope(tmp_path, monkeypatch):
    (tmp_path / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n")
    video = SimpleNamespace(output_dir=str(tmp_path), features_json={"intro_seconds": 3.5}, language="en")
    sent = {}

    def ok(url, params, headers, files, timeout):
        sent["media"] = files["media"][1].decode()
        sent["metadata"] = json.loads(files["metadata"][1])
        return Response(200, {"id": "cap1"})

    monkeypatch.setattr(youtube_extras.httpx, "post", ok)
    assert youtube_extras.upload_captions(video, "vid", "t") == {"status": "uploaded", "caption_id": "cap1", "offset_seconds": 3.5}
    assert "00:00:03,500" in sent["media"] and sent["metadata"]["snippet"]["videoId"] == "vid"
    monkeypatch.setattr(youtube_extras.httpx, "post", lambda *a, **k: Response(403, text='{"error":{"errors":[{"reason":"insufficientPermissions"}]}}'))
    assert youtube_extras.upload_captions(video, "vid", "t")["status"] == "scope_missing_reauthorize"


def test_series_playlist_is_created_once_and_reused(db, monkeypatch):
    calls = []

    def post(url, params, headers, json, timeout):
        calls.append(url)
        return Response(200, {"id": "PL123"} if url.endswith("/playlists") else {"id": "item"})

    monkeypatch.setattr(youtube_extras.httpx, "post", post)
    first = youtube_extras.add_to_series_playlist(db, "hidden-gem-of-the-week", "v1", "t")
    second = youtube_extras.add_to_series_playlist(db, "hidden-gem-of-the-week", "v2", "t")
    assert first == {"status": "added", "playlist_id": "PL123", "playlist": "created"} and second["playlist"] == "existing"
    assert sum(url.endswith("/playlists") for url in calls) == 1
    assert db.get(Setting, youtube_extras.PLAYLISTS_KEY).value_json == {"hidden-gem-of-the-week": "PL123"}


def test_post_publish_never_raises_and_records_results(db, awaiting_video, monkeypatch):
    publication = Publication(video_version_id=awaiting_video.id, platform="youtube", account="a", idempotency_key="pp", status="PUBLISHED", remote_id="vid")
    db.add(publication)
    db.commit()
    monkeypatch.setattr(youtube_extras, "upload_captions", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr("app.pipeline.alerts.immediate", lambda *a, **k: {})
    results = youtube_extras.run_post_publish(db, awaiting_video, publication, "t", {"captions": True})
    assert results["captions"] == {"status": "error", "error": "RuntimeError"}
    assert publication.response_json["post_publish"]["captions"]["status"] == "error"


def test_chapters_follow_youtube_rules():
    packet = {"segments": [{"id": "S01", "voiceover": "First part about the board."}, {"id": "S02", "voiceover": "Second part about the choice."}, {"id": "S03", "voiceover": "Third part about the payoff."}]}
    narration = " ".join(segment["voiceover"] for segment in packet["segments"])
    captions = [{"start": 0.0, "text": packet["segments"][0]["voiceover"]}, {"start": 20.0, "text": packet["segments"][1]["voiceover"]}, {"start": 45.0, "text": packet["segments"][2]["voiceover"]}]
    titles = [{"segment_id": "S01", "title": "The board"}, {"segment_id": "S02", "title": "The choice"}, {"segment_id": "S03", "title": "The payoff"}]
    result = youtube_extras.build_chapters(packet, narration, captions, titles, 3.5, 75)
    assert result["status"] == "ok"
    assert result["text"].splitlines() == ["0:00 The board", "0:23 The choice", "0:48 The payoff"]
    tight = youtube_extras.build_chapters(packet, narration, [{**row, "start": index * 2.0} for index, row in enumerate(captions)], titles, 3.5, 75)
    assert tight["status"] == "chapter_shorter_than_10_seconds"
    assert youtube_extras.build_chapters(packet, narration, captions, [], 3.5, 75)["status"] == "not_requested"


def test_youtube_variant_includes_chapters_text():
    from app.pipeline.variants import platform_variant

    post = {"title": "T", "caption": "Body", "hashtags": [], "links": [], "chapters_text": "0:00 Intro\n0:12 Part"}
    assert "0:12 Part" in platform_variant(post, "youtube")["text"]
    assert "0:12 Part" not in platform_variant(post, "tiktok")["text"]


def test_v2_youtube_destination_binds_post_publish_plan(awaiting_video, tmp_path):
    from app.pipeline.approvals import destinations_digest

    Path(awaiting_video.output_dir, "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n")
    awaiting_video.features_json = {**awaiting_video.features_json, "series_id": "hidden-gem-of-the-week"}
    digest = destinations_digest(awaiting_video, [{"platform": "youtube", "account": "c", "digest_version": 2}])
    assert digest["destinations"][0]["post_publish"] == {"captions": True, "series_playlist": "hidden-gem-of-the-week"}


# --- long form -----------------------------------------------------------------

def test_long_form_plan_is_youtube_only_and_renders_1920x1080(tmp_path):
    from app.pipeline.media import probe
    from app.pipeline.real_media import RealMediaPlan, load_media_plan, media_coverage, prepare_media, render_real_media
    from tests.test_real_media import make_media, scene_payload, write_srt

    with pytest.raises(ValueError, match="long_form_is_youtube_only"):
        RealMediaPlan.model_validate({"platform": "tiktok", "video_format": "long_16x9", "scenes": [scene_payload()]})
    _image, _video, narration = make_media(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"platform": "youtube", "video_format": "long_16x9", "scenes": [scene_payload("real_image", "photo.jpg", "zoom_in"), scene_payload()]}))
    plan = load_media_plan(plan_path)
    prepared = prepare_media(plan, plan_path, tmp_path)
    captions = tmp_path / "captions.srt"
    write_srt([{"start": 0, "end": 1, "text": "One"}, {"start": 1, "end": 2, "text": "Two"}], captions)
    coverage = media_coverage(plan, [1, 1], prepared)
    output = tmp_path / "long.mp4"
    layout = render_real_media(prepared, narration, captions, "A long title", output, coverage, landscape=True)
    stream = next(item for item in probe(output)["streams"] if item["codec_type"] == "video")
    assert (stream["width"], stream["height"]) == (1920, 1080) and layout["resolution"] == "1920x1080"


def test_long_form_cannot_be_approved_for_shorts_platforms(awaiting_video, db):
    from app.pipeline.approvals import ApprovalError, approve_destinations

    awaiting_video.features_json = {**awaiting_video.features_json, "allowed_platforms": ["youtube"]}
    db.commit()
    with pytest.raises(ApprovalError, match="format_not_for_platform:tiktok"):
        approve_destinations(db, awaiting_video, "owner", [{"platform": "tiktok", "account": "t"}], True)


# --- outliers and releases -------------------------------------------------------

def test_youtube_adapter_adds_views_per_subscriber_outlier_rows():
    from app.adapters.youtube import YouTubeAdapter

    adapter = YouTubeAdapter(api_key="k")
    responses = {
        "search": {"items": [{"id": {"videoId": "a"}}, {"id": {"videoId": "b"}}]},
        "videos": {"items": [{"id": "a", "snippet": {"title": "Small channel hit", "channelId": "c1", "publishedAt": NOW.isoformat()}, "statistics": {"viewCount": "50000"}}, {"id": "b", "snippet": {"title": "Big channel", "channelId": "c2"}, "statistics": {"viewCount": "50000"}}]},
        "channels": {"items": [{"id": "c1", "statistics": {"subscriberCount": "5000"}}, {"id": "c2", "statistics": {"subscriberCount": "2000000"}}]},
    }
    adapter._get = lambda path, params: responses[path]
    rows = adapter.discover("hidden gem", "en")
    ratios = {row["topic"].split(":", 1)[1]: row["metric_value"] for row in rows if row["metric_name"] == "views_per_subscriber"}
    assert ratios == {"Small channel hit": 10.0, "Big channel": 0.025}


def test_outliers_reach_idea_suggestions(db):
    from app.pipeline.ideas import suggestions_from_research

    plan = [{"idea_id": "GI001", "lane": "gaming", "title": "Idea", "query": "soldier", "allocation": "exploit"}]
    db.add_all([
        Observation(source_url="https://www.youtube.com/watch?v=a", platform="youtube", topic="soldier:Hit", metric_name="views", metric_value=50000, method="t", confidence="high"),
        Observation(source_url="https://www.youtube.com/watch?v=a", platform="youtube", topic="soldier:Hit", metric_name="views_per_subscriber", metric_value=10.0, method="t", confidence="high"),
    ])
    db.commit()
    created = suggestions_from_research(db, plan)
    assert created[0].evidence_json["outliers"][0]["views_per_subscriber"] == 10.0 and "outlier" in created[0].rationale


def test_release_calendar_manual_entries_become_timed_suggestions(db, tmp_path, monkeypatch):
    today = date(2026, 11, 13)
    calendar = tmp_path / "calendar.json"
    calendar.write_text(json.dumps({"releases": [
        {"game": "Handheld Hero", "release_date": "2026-12-01", "platforms": ["Steam Deck", "Switch 2"], "source_url": "https://example.com/hh", "checked_at": "2026-11-13"},
        {"game": "Too Soon", "release_date": "2026-11-15", "platforms": ["PC"], "source_url": "https://example.com/ts", "checked_at": "2026-11-13"},
        {"game": "No Source", "release_date": "2026-12-05", "platforms": ["PC"]},
    ]}))
    monkeypatch.setattr(releases, "CALENDAR", calendar)
    upcoming = releases.upcoming(db, today)
    assert [item["game"] for item in upcoming] == ["Too Soon", "Handheld Hero"]
    created = releases.suggestions_from_releases(db, today)
    assert [item.query for item in created] == ["Handheld Hero"]
    assert created[0].evidence_json["recipe_hint"] == "GF05"
    assert releases.suggestions_from_releases(db, today) == []


def test_igdb_requires_terms_confirmation(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "igdb_client_id", "id")
    monkeypatch.setattr(settings, "igdb_client_secret", "secret")
    monkeypatch.setattr(settings, "igdb_terms_confirmed", False)
    assert releases.igdb_configured() is False
    monkeypatch.setattr(settings, "igdb_terms_confirmed", True)
    assert releases.igdb_configured() is True


# --- pronunciation --------------------------------------------------------------

def test_pronunciation_dictionary_sync_and_tts_locator(tmp_path, monkeypatch):
    from app.pipeline.voice import _tts_body

    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "elevenlabs_api_key", "")
    assert pronunciation.sync()["status"] == "not_configured"
    assert "pronunciation_dictionary_locators" not in _tts_body("Hades", "m")
    monkeypatch.setattr(settings, "elevenlabs_api_key", "el-key")
    sent = {}
    monkeypatch.setattr(pronunciation.httpx, "post", lambda url, headers, json, timeout: sent.update(json) or Response(200, {"id": "pd1", "version_id": "v1"}))
    assert pronunciation.sync()["status"] == "created"
    assert all(rule["type"] == "alias" for rule in sent["rules"])
    assert pronunciation.sync()["status"] == "unchanged"
    assert _tts_body("Hades", "m")["pronunciation_dictionary_locators"] == [{"pronunciation_dictionary_id": "pd1", "version_id": "v1"}]
    monkeypatch.setattr(pronunciation, "load_rules", lambda path=None: [{"string_to_replace": "New", "alias": "Noo"}])
    assert pronunciation.current_locator() is None  # stale dictionary is never sent


def test_pronunciation_rules_are_validated(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"rules": [{"string_to_replace": "A", "alias": "a"}, {"string_to_replace": "A", "alias": "b"}]}))
    with pytest.raises(ValueError, match="duplicate"):
        pronunciation.load_rules(path)
    assert {rule["string_to_replace"] for rule in pronunciation.load_rules()} >= {"Hades", "Amiga"}


# --- monetization ---------------------------------------------------------------

def test_ypp_progress_shares_and_eligibility():
    result = monetization.evaluate({"subscribers": 600, "watch_hours_365d": 1500, "shorts_views_90d": 3_200_000, "public_uploads_90d": 9})
    tiers = {tier["id"]: tier for tier in result["tiers"]}
    assert tiers["expanded_fan_funding"]["eligible_by_numbers"] is True and tiers["expanded_fan_funding"]["best_path"] == "shorts_views"
    assert tiers["full_ypp"]["eligible_by_numbers"] is False and tiers["full_ypp"]["subscribers_share"] == 0.6
    assert result["source_url"].startswith("https://support.google.com/youtube")


def test_collect_progress_uses_content_type_split(db, monkeypatch):
    settings = get_settings()
    for name in ("youtube_client_id", "youtube_client_secret", "youtube_refresh_token"):
        monkeypatch.setattr(settings, name, "x")
    monkeypatch.setattr("app.pipeline.metrics._youtube_access_token", lambda: "t")

    def get(url, headers, params, timeout):
        if "channels" in url:
            return Response(200, {"items": [{"statistics": {"subscriberCount": "420"}}]})
        assert params["dimensions"] == "creatorContentType"
        return Response(200, {"rows": [["SHORTS", 120000, 900], ["VIDEO_ON_DEMAND", 8000, 30000]]})

    monkeypatch.setattr(monetization.httpx, "get", get)
    result = monetization.collect_progress(db, NOW)
    assert result["observed"] == {"subscribers": 420, "watch_hours_365d": 500.0, "shorts_views_90d": 120000, "public_uploads_90d": 0}
    assert db.get(Setting, monetization.PROGRESS_KEY).value_json["observed"]["subscribers"] == 420


def test_affiliate_links_need_registration_and_disclosure(monkeypatch):
    monkeypatch.setattr(monetization, "affiliate_register", lambda: {"generic_affiliate_patterns": ["amzn.to/", "tag="], "programs": [{"name": "Shop", "domains": ["shop.example"], "disclosure_text": "Affiliate link: we may earn a commission."}]})
    assert monetization.affiliate_blockers({"caption": "Buy", "links": ["https://shop.example/x"]}) == ["affiliate_disclosure_missing:Shop"]
    assert monetization.affiliate_blockers({"caption": "Affiliate link: we may earn a commission.", "links": ["https://shop.example/x"]}) == []
    assert monetization.affiliate_blockers({"caption": "", "links": ["https://amzn.to/abc"]})[0].startswith("affiliate_link_unregistered")
    assert monetization.affiliate_blockers({"caption": "", "links": ["https://store.steampowered.com/app/1"]}) == []


# --- notifications ---------------------------------------------------------------

def test_awaiting_owner_notice_links_to_review_page(db, awaiting_video, monkeypatch):
    from app.pipeline import alerts

    monkeypatch.setattr(get_settings(), "public_dashboard_url", "https://dash.example.test/")
    sent = []
    monkeypatch.setattr(alerts, "notify", lambda db, items, subject, *a, **k: sent.append((items, subject)) or {"sent": ["webhook"]})
    alerts.notify_awaiting_owner(db, awaiting_video)
    assert f"https://dash.example.test/review/{awaiting_video.id}" in sent[0][0][0]["message"]


# --- 2FA ----------------------------------------------------------------------------

def test_totp_matches_rfc6238_vector_and_blocks_replay():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32 of "12345678901234567890"
    assert totp.code_at(secret, 1) == "287082"  # RFC 6238 T=59 -> 94287082, last six digits
    assert totp.verify(secret, "287082", now=59) == 1
    assert totp.verify(secret, "287082", last_step=1, now=59) is None
    assert totp.verify(secret, "000000", now=59) is None


def _client(db, monkeypatch, require=False):
    from app.db.session import get_db
    from app.main import app

    settings = get_settings()
    monkeypatch.setattr(settings, "app_secret_key", "a-test-secret-key-that-is-long-enough")
    monkeypatch.setattr(settings, "require_totp", require)
    db.add(AuthUser(username="owner", password_hash=PasswordHasher().hash("a-secure-test-password")))
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, base_url="https://testserver"), app


def _csrf(text):
    return text.split('name="csrf_token" value="')[1].split('"')[0]


def test_two_factor_enrolment_and_login_flow(db, monkeypatch):
    client, app = _client(db, monkeypatch)
    client.post("/login", data={"username": "owner", "password": "a-secure-test-password"})
    page = client.get("/account/security")
    assert page.status_code == 200 and "Nøgle" in page.text
    secret = totp.decrypt_secret(db.query(AuthUser).one().totp_secret_encrypted)
    import time as clock

    now = clock.time()
    enabled = client.post("/account/2fa/enable", data={"csrf_token": _csrf(page.text), "code": totp.code_at(secret, int(now // 30))})
    assert enabled.status_code == 200 and "gendannelseskoder" in enabled.text
    recovery = enabled.text.split("<pre>")[1].split("</pre>")[0].split()[0]
    client.cookies.clear()
    step1 = client.post("/login", data={"username": "owner", "password": "a-secure-test-password", "next": "/operations"}, follow_redirects=False)
    assert step1.headers["location"].startswith("/login/2fa")
    assert client.get("/review", follow_redirects=False).headers["location"].startswith("/login/2fa")
    form = client.get(step1.headers["location"])
    assert client.post("/login/2fa", data={"csrf_token": _csrf(form.text), "code": "000000", "next": "/operations"}, follow_redirects=False).status_code == 401
    ok = client.post("/login/2fa", data={"csrf_token": _csrf(form.text), "code": recovery, "next": "/operations"}, follow_redirects=False)
    assert ok.status_code == 303 and ok.headers["location"] == "/operations"
    assert client.get("/review").status_code == 200
    assert len(db.query(AuthUser).one().recovery_codes_json) == 7
    app.dependency_overrides.clear()


def test_required_two_factor_blocks_unenrolled_login(db, monkeypatch):
    client, app = _client(db, monkeypatch, require=True)
    response = client.post("/login", data={"username": "owner", "password": "a-secure-test-password"}, follow_redirects=False)
    assert response.status_code == 403 and "2-faktor" in response.text
    app.dependency_overrides.clear()


def test_login_next_cannot_redirect_off_site(db, monkeypatch):
    from app.main import safe_next

    assert safe_next("https://evil.example") == "/review"
    assert safe_next("//evil.example") == "/review"
    assert safe_next("/review/7") == "/review/7"
    client, app = _client(db, monkeypatch)
    response = client.post("/login", data={"username": "owner", "password": "a-secure-test-password", "next": "//evil.example"}, follow_redirects=False)
    assert response.headers["location"] == "/review"
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    app.dependency_overrides.clear()


def test_enrolment_page_shows_qr_and_errors_render_as_html(db, monkeypatch):
    client, app = _client(db, monkeypatch)
    client.post("/login", data={"username": "owner", "password": "a-secure-test-password"})
    page = client.get("/account/security")
    assert "<svg" in page.text and "tidsbaseret" in page.text
    wrong = client.post("/account/2fa/enable", data={"csrf_token": _csrf(page.text), "code": "000000"})
    assert wrong.status_code == 422 and "text/html" in wrong.headers["content-type"] and "Scan QR-koden igen" in wrong.text
    before = db.query(AuthUser).one().totp_secret_encrypted
    assert client.post("/account/2fa/reset", data={"csrf_token": _csrf(page.text)}, follow_redirects=False).status_code == 303
    db.expire_all()
    assert db.query(AuthUser).one().totp_secret_encrypted != before
    app.dependency_overrides.clear()


def test_enrolment_tolerates_one_minute_of_clock_drift():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp.verify(secret, totp.code_at(secret, 100 - 2), now=100 * 30, window=2) == 98
    assert totp.verify(secret, totp.code_at(secret, 100 - 2), now=100 * 30) is None
