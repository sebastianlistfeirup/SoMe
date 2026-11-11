import re


PLATFORM_LABELS = {
    "youtube": "YouTube",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "tiktok": "TikTok",
    "reels": "Instagram",
}

STATUS_LABELS = {
    "AWAITING_OWNER": "Afventer dig",
    "APPROVED": "Godkendt",
    "REJECTED": "Afvist",
    "SCHEDULED": "Planlagt",
    "PUBLISHING": "Publicerer",
    "PUBLISHED": "Sendt",
    "RECONCILE_REQUIRED": "Kræver kontrol",
    "FAILED": "Fejlet",
    "BLOCKED": "Blokeret",
}


def normalize_hashtags(values) -> list[str]:
    if isinstance(values, str):
        values = values.split()
    normalized = []
    for value in values or []:
        tag = re.sub(r"[^\w]", "", str(value).strip().lstrip("#"), flags=re.UNICODE)[:40]
        if tag and tag.casefold() not in {item.casefold() for item in normalized}:
            normalized.append(tag)
    return normalized[:15]


def compose_post_text(caption: str, hashtags: list[str]) -> str:
    caption = caption.strip()
    tags = " ".join(f"#{tag}" for tag in normalize_hashtags(hashtags))
    return f"{caption}\n\n{tags}".strip() if tags else caption


def build_post(title: str, caption: str, hashtags: list[str], links: list[str], **extra) -> dict:
    tags = normalize_hashtags(hashtags)
    return {
        "title": title.strip(),
        "caption": caption.strip(),
        "text": compose_post_text(caption, tags),
        "hashtags": tags,
        "links": links,
        **extra,
    }


def post_view(post: dict, fallback_title: str = "") -> dict:
    text = post.get("text", "")
    stored_tags = normalize_hashtags(post.get("hashtags", []))
    hashtags = stored_tags or normalize_hashtags(re.findall(r"#([\w]+)", text, flags=re.UNICODE))
    if post.get("caption") is not None:
        caption = post.get("caption", "").strip()
    elif hashtags:
        caption = re.sub(r"\s*#[\w]+", "", text, flags=re.UNICODE).strip()
    else:
        caption = text.strip()
    title = post.get("title", "").strip() or fallback_title.strip() or caption[:100]
    return {
        "title": title,
        "caption": caption,
        "hashtags": hashtags,
        "text": compose_post_text(caption, hashtags),
        "links": post.get("links", []),
    }


def preferred_platform(video) -> str:
    platform = video.post_json.get("platform") or video.features_json.get("platform") or "youtube"
    return "instagram" if platform == "reels" else platform if platform in PLATFORM_LABELS else "youtube"


def platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get(platform, platform)


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status.replace("_", " ").title())


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return "Video"
    total = round(seconds)
    return f"{total // 60}:{total % 60:02d}"
