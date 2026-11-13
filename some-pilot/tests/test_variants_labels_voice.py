import pytest

from app.config import get_settings
from app.pipeline.approvals import ApprovalError, approve, approve_destinations, approved_content, destinations_digest
from app.pipeline.platforms import TikTokPublisher, YouTubePublisher
from app.pipeline.variants import AI_LABEL_DEFAULTS, PLATFORM_TEXT_RULES, all_variants, platform_variant
from tests.test_publish_reconcile import JsonResponse, StartResponse

POST = {"title": "One Small Board, One Big Decision " * 4, "caption": "Why a tiny tactics board can hold a real decision. " * 80, "hashtags": ["gaming", "strategy", "intothebreach", "indiegames", "tactics", "pcgaming", "roguelike", "puzzle", "turnbased"], "links": []}


def test_variants_respect_each_platform_rules():
    variants = all_variants(POST)
    assert set(variants) == set(PLATFORM_TEXT_RULES)
    for platform, variant in variants.items():
        rules = PLATFORM_TEXT_RULES[platform]
        assert len(variant["text"]) <= rules["caption_max"]
        assert len(variant["hashtags"]) == min(rules["hashtags"], 9)
        assert rules["cta"] in variant["text"]
    assert len(variants["youtube"]["title"]) <= 100 and variants["tiktok"]["title"] == ""
    assert platform_variant(POST, "instagram") == platform_variant(POST, "instagram")


def _destinations(**labels):
    return [{"platform": platform, "account": f"{platform}-acct", "visibility": "public", "publish_at": None, "digest_version": 2, "ai_label": labels.get(platform)} for platform in ("youtube", "tiktok")]


def test_v2_digest_binds_variant_text_and_ai_label(awaiting_video):
    base = destinations_digest(awaiting_video, _destinations())
    flipped = destinations_digest(awaiting_video, _destinations(youtube=True))
    assert base["approval_sha256"] != flipped["approval_sha256"]
    youtube = next(item for item in base["destinations"] if item["platform"] == "youtube")
    assert youtube["ai_label"] is AI_LABEL_DEFAULTS["youtube"] and youtube["variant"]["platform"] == "youtube"
    legacy = destinations_digest(awaiting_video, [{"platform": "youtube", "account": "youtube-acct"}])
    assert "variant" not in legacy["destinations"][0]


def test_youtube_and_tiktok_send_approved_variant_and_label(db, awaiting_video, monkeypatch):
    settings = get_settings()
    for name, value in {"dry_run": False, "publish_enabled": True, "tiktok_access_token": "token", "tiktok_open_id": "open-1", "tiktok_direct_post_enabled": True, "tiktok_direct_post_reviewed": True, "tiktok_direct_post_consent_confirmed": True}.items():
        monkeypatch.setattr(settings, name, value)
    destinations = [{"platform": "youtube", "account": "channel", "visibility": "private", "publish_at": None, "digest_version": 2, "ai_label": True}, {"platform": "tiktok", "account": "open-1", "visibility": "public", "publish_at": None, "digest_version": 2, "ai_label": True}]
    review = approve_destinations(db, awaiting_video, "owner", destinations, True)
    expected = approved_content(review, awaiting_video, "tiktok", "open-1")
    assert expected["digest_version"] == 2 and expected["ai_label"] is True
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if "creator_info" in url:
            return JsonResponse({"data": {"privacy_level_options": ["PUBLIC_TO_EVERYONE"]}})
        if url.endswith("/init/"):
            return JsonResponse({"data": {"publish_id": "p1", "upload_url": "https://upload.example/file"}})
        if "thumbnails/set" in url:
            return JsonResponse({"items": [{}]})
        if "tiktok" in url:
            return JsonResponse({"data": {"status": "PUBLISH_COMPLETE"}})
        return StartResponse()

    monkeypatch.setattr("app.pipeline.platforms.httpx.post", post)
    monkeypatch.setattr("app.pipeline.platforms.httpx.put", lambda *_args, **_kwargs: JsonResponse({"id": "yt-1", "status": {}}))
    monkeypatch.setattr("app.pipeline.platforms.httpx.get", lambda *_args, **_kwargs: JsonResponse({"items": [{"processingDetails": {"processingStatus": "succeeded"}}]}))
    TikTokPublisher().publish(db, awaiting_video, "open-1")
    init = next(call for call in calls if call[0].endswith("/video/init/"))
    assert init[1]["json"]["post_info"]["is_aigc"] is True
    assert init[1]["json"]["post_info"]["title"] == expected["text"]
    publisher = YouTubePublisher()
    monkeypatch.setattr(publisher, "_access_token", lambda: "test-token")
    publisher.publish(db, awaiting_video, "channel", "private")
    start = next(call for call in calls if "uploadType=resumable" in call[0])
    assert start[1]["json"]["status"]["containsSyntheticMedia"] is True
    assert start[1]["json"]["snippet"]["description"] == approved_content(review, awaiting_video, "youtube", "channel")["text"]


def test_legacy_single_destination_publish_sends_no_label_field(db, awaiting_video, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dry_run", False)
    monkeypatch.setattr(settings, "publish_enabled", True)
    review = approve(db, awaiting_video, "owner", "youtube", "channel", True)
    assert approved_content(review, awaiting_video, "youtube", "channel")["ai_label"] is None


def test_videos_with_rejected_kokoro_voice_can_never_be_approved(db, awaiting_video):
    awaiting_video.features_json = {**awaiting_video.features_json, "voice_provider": "kokoro"}
    db.commit()
    with pytest.raises(ApprovalError, match="rejected_voice"):
        approve(db, awaiting_video, "owner", "youtube", "channel", True)
    with pytest.raises(ApprovalError, match="rejected_voice"):
        approve_destinations(db, awaiting_video, "owner", [{"platform": "youtube", "account": "c"}], True)


def test_rejected_tools_are_not_defaults():
    # Check the code default, not the server's environment (which may still say kokoro until the owner updates it).
    fields = type(get_settings()).model_fields
    assert fields["voice_provider"].default == "elevenlabs"
    assert fields["demo_voice_provider"].default == "kokoro"
    assert not any(name.startswith("heygen") for name in fields)
    import importlib.util

    assert importlib.util.find_spec("app.pipeline.avatar") is None
