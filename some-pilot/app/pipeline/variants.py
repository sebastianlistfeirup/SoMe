"""Per-destination post variants and AI-disclosure labels.

One rendered short-form 9:16 video is valid for YouTube Shorts, Instagram Reels,
TikTok and Facebook Reels, but each platform gets its own title, caption length,
hashtag count and call to action. Variants are a pure function of the stored
post, so the approval hash is reproducible, and they are shown side by side
before approval. The approved digest binds the exact variant text and the AI
label each publisher will send.
"""

from app.pipeline.posts import compose_post_text, normalize_hashtags, post_view

PLATFORM_TEXT_RULES = {
    "youtube": {"title_max": 100, "caption_max": 4500, "hashtags": 3, "cta": "Subscribe for more gaming and AI breakdowns."},
    "instagram": {"title_max": 0, "caption_max": 2000, "hashtags": 8, "cta": "Follow for more."},
    "tiktok": {"title_max": 0, "caption_max": 2000, "hashtags": 5, "cta": "Follow for more."},
    "facebook": {"title_max": 0, "caption_max": 2000, "hashtags": 3, "cta": "Follow the page for more."},
}

# Defaults follow each platform's own rule, and the owner can change them per approval.
# YouTube's containsSyntheticMedia is for *realistic* altered or synthetic depictions of people,
# places or events. A clearly narrated explainer using a library voice is usually outside it, so the
# default is off. TikTok's is_aigc label is the conservative default for AI-generated narration.
# Meta has no API flag; its label must be set manually in the app.
AI_LABEL_DEFAULTS = {"youtube": False, "tiktok": True, "instagram": True, "facebook": True}
AI_LABEL_API = {"youtube": "status.containsSyntheticMedia", "tiktok": "post_info.is_aigc", "instagram": None, "facebook": None}


def _trim(text: str, limit: int) -> str:
    text = text.strip()
    if limit <= 0 or len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:") + "…"


def platform_variant(post: dict, platform: str, fallback_title: str = "") -> dict:
    rules = PLATFORM_TEXT_RULES[platform]
    view = post_view(post, fallback_title)
    tags = normalize_hashtags(view["hashtags"])[: rules["hashtags"]]
    cta = rules["cta"]
    tag_room = sum(len(tag) + 2 for tag in tags) + len(cta) + 4
    caption = _trim(view["caption"], rules["caption_max"] - tag_room)
    body = f"{caption}\n\n{cta}" if cta and cta.casefold() not in caption.casefold() else caption
    if platform == "youtube" and post.get("chapters_text"):
        body = f"{body}\n\n{post['chapters_text']}"
    return {
        "platform": platform,
        "title": _trim(view["title"], rules["title_max"]) if rules["title_max"] else "",
        "caption": caption,
        "cta": cta,
        "hashtags": tags,
        "text": compose_post_text(body, tags),
    }


def all_variants(post: dict, fallback_title: str = "") -> dict:
    return {platform: platform_variant(post, platform, fallback_title) for platform in PLATFORM_TEXT_RULES}


def ai_label_for(platform: str, override: bool | None = None) -> dict:
    value = AI_LABEL_DEFAULTS[platform] if override is None else bool(override)
    api_field = AI_LABEL_API[platform]
    return {"ai_label": value, "api_field": api_field, "applied_by": "api" if api_field else "manual_in_app"}
