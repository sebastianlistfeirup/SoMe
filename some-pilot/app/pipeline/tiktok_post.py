"""TikTok Direct Post choices the owner makes on the review page.

TikTok's Content Posting API guidelines require the posting UI to show the
creator's nickname (creator_info/query), let the user pick a privacy level from
the returned options with no default, offer comment/duet/stitch toggles that
respect the creator's disabled flags, offer commercial-content disclosure and
show the Music Usage Confirmation consent text. The normalised choices are bound
into the approval digest, and the publisher re-checks them against a fresh
creator_info response before it posts.
"""

import httpx
from sqlalchemy.orm import Session

from app.pipeline.approvals import ApprovalError

API_BASE = "https://open.tiktokapis.com/v2"
CREATOR_INFO_URL = f"{API_BASE}/post/publish/creator_info/query/"
PRIVACY_LEVELS = ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")
PRIVACY_LABELS = {"PUBLIC_TO_EVERYONE": "Everyone", "MUTUAL_FOLLOW_FRIENDS": "Friends", "FOLLOWER_OF_CREATOR": "Followers", "SELF_ONLY": "Only me"}
EXTERNAL_VISIBILITY = {"PUBLIC_TO_EVERYONE": "public", "MUTUAL_FOLLOW_FRIENDS": "friends", "FOLLOWER_OF_CREATOR": "followers", "SELF_ONLY": "private"}
MUSIC_CONSENT = "By posting, you agree to TikTok's Music Usage Confirmation"
BRANDED_CONSENT = "By posting, you agree to TikTok's Branded Content Policy and Music Usage Confirmation"
MUSIC_USAGE_URL = "https://www.tiktok.com/legal/page/global/music-usage-confirmation/en"
BRANDED_CONTENT_URL = "https://www.tiktok.com/legal/page/global/bc-policy/en"


class CreatorInfoError(RuntimeError):
    pass


def consent_text(brand_content: bool) -> str:
    return BRANDED_CONSENT if brand_content else MUSIC_CONSENT


def _flag(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "on", "yes"}
    return bool(value)


def normalize_post_settings(raw: dict | None) -> dict:
    """Validate the owner's choices; idempotent, so a stored digest normalises to itself."""
    if not isinstance(raw, dict):
        raise ApprovalError("tiktok_post_settings_required")
    privacy = raw.get("privacy_level") or ""
    if privacy not in PRIVACY_LEVELS:
        raise ApprovalError("tiktok_privacy_level_required")
    disclose = _flag(raw.get("commercial_disclosure"))
    brand_organic = disclose and _flag(raw.get("brand_organic_toggle"))
    brand_content = disclose and _flag(raw.get("brand_content_toggle"))
    if disclose and not (brand_organic or brand_content):
        raise ApprovalError("tiktok_commercial_content_type_required")
    if brand_content and privacy == "SELF_ONLY":
        raise ApprovalError("tiktok_branded_content_cannot_be_private")
    return {
        "privacy_level": privacy,
        "allow_comment": _flag(raw.get("allow_comment")),
        "allow_duet": _flag(raw.get("allow_duet")),
        "allow_stitch": _flag(raw.get("allow_stitch")),
        "commercial_disclosure": disclose,
        "brand_organic_toggle": brand_organic,
        "brand_content_toggle": brand_content,
        "consent_text": consent_text(brand_content),
    }


def from_form(privacy_level: str, allow_comment: bool, allow_duet: bool, allow_stitch: bool, disclose: bool, brand_organic: bool, brand_content: bool) -> dict:
    return normalize_post_settings({
        "privacy_level": privacy_level,
        "allow_comment": allow_comment,
        "allow_duet": allow_duet,
        "allow_stitch": allow_stitch,
        "commercial_disclosure": disclose,
        "brand_organic_toggle": brand_organic,
        "brand_content_toggle": brand_content,
    })


def creator_mismatches(options: dict, creator: dict, duration_seconds: float | None = None) -> list[str]:
    """Reasons the approved choices are not allowed by the creator's current TikTok settings."""
    problems = []
    if options["privacy_level"] not in (creator.get("privacy_level_options") or []):
        problems.append("tiktok_privacy_level_not_offered")
    for choice, flag in (("allow_comment", "comment_disabled"), ("allow_duet", "duet_disabled"), ("allow_stitch", "stitch_disabled")):
        if options.get(choice) and creator.get(flag):
            problems.append(f"tiktok_{flag}_by_creator")
    limit = creator.get("max_video_post_duration_sec")
    if limit and duration_seconds and float(duration_seconds) > float(limit):
        problems.append("tiktok_video_longer_than_creator_limit")
    return problems


def post_info(options: dict, caption: str, ai_label) -> dict:
    """The post_info body for /post/publish/video/init/, built only from approved choices."""
    info = {
        "title": caption,
        "privacy_level": options["privacy_level"],
        "disable_comment": not options["allow_comment"],
        "disable_duet": not options["allow_duet"],
        "disable_stitch": not options["allow_stitch"],
        "brand_content_toggle": bool(options["brand_content_toggle"]),
        "brand_organic_toggle": bool(options["brand_organic_toggle"]),
        "video_cover_timestamp_ms": 1000,
    }
    if ai_label is not None:
        info["is_aigc"] = bool(ai_label)
    return info


def query_creator_info(db: Session | None) -> dict:
    """Live creator_info/query; refreshes the token once on a 401. Raises CreatorInfoError with a code."""
    from app.pipeline import tiktok_auth

    try:
        token = tiktok_auth.access_token(db)
        response = httpx.post(CREATOR_INFO_URL, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}, json={}, timeout=20)
        if response.status_code == 401 and tiktok_auth.load_bundle():
            token = tiktok_auth.access_token(db, force_refresh=True)
            response = httpx.post(CREATOR_INFO_URL, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}, json={}, timeout=20)
    except tiktok_auth.TikTokAuthError as exc:
        raise CreatorInfoError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise CreatorInfoError(f"tiktok_creator_info_unreachable:{type(exc).__name__}") from exc
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get("error") or {}
    code = error.get("code") if isinstance(error, dict) else str(error)
    if response.status_code >= 400 or (code and code != "ok"):
        # e.g. scope_not_authorized (no video.publish), spam_risk_too_many_posts, reached_active_user_cap
        raise CreatorInfoError(f"tiktok_creator_info_error:{code or response.status_code}"[:160])
    data = body.get("data") or {}
    if not data.get("privacy_level_options"):
        raise CreatorInfoError("tiktok_creator_cannot_post_now")
    return data


def creator_view(db: Session | None) -> dict:
    """What the review page needs; never raises and never contains token values."""
    from app.pipeline import tiktok_auth

    if not tiktok_auth.configured():
        return {"available": False, "error": "tiktok_not_connected_login_required"}
    try:
        data = query_creator_info(db)
    except CreatorInfoError as exc:
        return {"available": False, "error": str(exc)}
    options = [level for level in data.get("privacy_level_options", []) if level in PRIVACY_LEVELS]
    return {
        "available": True,
        "nickname": data.get("creator_nickname") or "",
        "username": data.get("creator_username") or "",
        "privacy_options": [{"value": level, "label": PRIVACY_LABELS[level]} for level in options],
        "comment_disabled": bool(data.get("comment_disabled")),
        "duet_disabled": bool(data.get("duet_disabled")),
        "stitch_disabled": bool(data.get("stitch_disabled")),
        "max_video_post_duration_sec": data.get("max_video_post_duration_sec"),
        "raw": data,
    }
