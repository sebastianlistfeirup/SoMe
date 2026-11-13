"""Remove secrets from text before it is stored, shown or sent anywhere."""

import re

from app.config import get_settings

SECRET_FIELDS = (
    "anthropic_api_key", "app_secret_key", "dashscope_api_key", "youtube_api_key", "youtube_client_secret", "youtube_refresh_token",
    "meta_app_secret", "meta_access_token", "meta_page_access_token", "tiktok_client_secret", "tiktok_access_token", "backup_key",
    "elevenlabs_api_key", "alert_webhook_url", "alert_smtp_password", "offsite_password",
)
PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)((?:access_token|refresh_token|client_secret|api_key|apikey|key|token|password|secret)=)[^&\s\"']+"),
    re.compile(r"(?i)(\"(?:access_token|refresh_token|client_secret|api_key|token|password|secret)\"\s*:\s*\")[^\"]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
)


def redact(text: str | None) -> str:
    if not text:
        return ""
    value = str(text)
    settings = get_settings()
    for field in SECRET_FIELDS:
        secret = str(getattr(settings, field, "") or "")
        if len(secret) >= 6:
            value = value.replace(secret, "[REDACTED]")
    for pattern in PATTERNS:
        value = pattern.sub(lambda match: (match.group(1) if match.groups() else "") + "[REDACTED]", value)
    return value
