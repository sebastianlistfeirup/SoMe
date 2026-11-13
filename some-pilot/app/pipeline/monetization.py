"""Progress toward the YouTube Partner Program and affiliate disclosure checks.

Progress uses the channel's own data: subscribers (Data API), long-form watch
hours over 365 days and Shorts views over 90 days split by the Analytics
dimension creatorContentType, and public uploads in the last 90 days.
Thresholds come from content/MONETIZATION.json with their source and date.
Watch hours from the API approximate YouTube's "qualified" hours; YouTube Studio
is authoritative.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Publication, Setting

CONTENT = Path(__file__).resolve().parents[2] / "content"
PROGRESS_KEY = "ypp_progress"


def thresholds() -> dict:
    return json.loads((CONTENT / "MONETIZATION.json").read_text(encoding="utf-8"))


def _analytics_by_type(token: str, start: str, end: str) -> dict[str, dict[str, float]]:
    response = httpx.get("https://youtubeanalytics.googleapis.com/v2/reports", headers={"Authorization": f"Bearer {token}"}, params={"ids": "channel==MINE", "startDate": start, "endDate": end, "metrics": "views,estimatedMinutesWatched", "dimensions": "creatorContentType"}, timeout=30)
    response.raise_for_status()
    result = {}
    for row in response.json().get("rows", []):
        result[str(row[0]).upper()] = {"views": float(row[1]), "minutes": float(row[2])}
    return result


def collect_progress(db: Session, now: datetime | None = None) -> dict:
    from app.pipeline.metrics import _youtube_access_token

    settings = get_settings()
    if not all((settings.youtube_client_id, settings.youtube_client_secret, settings.youtube_refresh_token)):
        return {"status": "not_configured"}
    now = now or datetime.now(timezone.utc)
    token = _youtube_access_token()
    channel = httpx.get("https://www.googleapis.com/youtube/v3/channels", headers={"Authorization": f"Bearer {token}"}, params={"part": "statistics", "mine": "true"}, timeout=20)
    channel.raise_for_status()
    items = channel.json().get("items", [])
    stats = items[0]["statistics"] if items else {}
    today = now.date().isoformat()
    year = _analytics_by_type(token, (now - timedelta(days=365)).date().isoformat(), today)
    quarter = _analytics_by_type(token, (now - timedelta(days=90)).date().isoformat(), today)
    since = now - timedelta(days=90)
    uploads = [row for row in db.query(Publication).filter(Publication.platform == "youtube", Publication.status == "PUBLISHED").all() if row.published_at and (row.published_at.replace(tzinfo=timezone.utc) if row.published_at.tzinfo is None else row.published_at) >= since and (row.response_json or {}).get("status", {}).get("privacyStatus", "public") == "public"]
    observed = {
        "subscribers": None if stats.get("hiddenSubscriberCount") else int(stats.get("subscriberCount", 0)),
        "watch_hours_365d": round(year.get("VIDEO_ON_DEMAND", {}).get("minutes", 0) / 60, 1),
        "shorts_views_90d": int(quarter.get("SHORTS", {}).get("views", 0)),
        "public_uploads_90d": len(uploads),
    }
    progress = evaluate(observed)
    value = {"collected_at": now.isoformat(), "observed": observed, **progress}
    db.merge(Setting(key=PROGRESS_KEY, value_json=value))
    db.commit()
    return value


def evaluate(observed: dict) -> dict:
    config = thresholds()
    tiers = []
    for tier in config["tiers"]:
        subs_ok = observed.get("subscribers") is not None and observed["subscribers"] >= tier["subscribers"]
        uploads_ok = observed.get("public_uploads_90d", 0) >= tier.get("public_uploads_90d", 0)
        hours = observed.get("watch_hours_365d", 0) / tier["watch_hours_365d"]
        shorts = observed.get("shorts_views_90d", 0) / tier["shorts_views_90d"]
        tiers.append({
            "id": tier["id"], "name": tier["name"],
            "subscribers_share": round(min(1.0, (observed.get("subscribers") or 0) / tier["subscribers"]), 4),
            "watch_hours_share": round(min(1.0, hours), 4),
            "shorts_views_share": round(min(1.0, shorts), 4),
            "uploads_ok": uploads_ok,
            "eligible_by_numbers": subs_ok and uploads_ok and (hours >= 1 or shorts >= 1),
            "best_path": "watch_hours" if hours >= shorts else "shorts_views",
        })
    return {"tiers": tiers, "source_url": config["source_url"], "thresholds_observed_at": config["observed_at"], "note": config["note"]}


# --- affiliate disclosure ------------------------------------------------------

def affiliate_register() -> dict:
    return json.loads((CONTENT / "AFFILIATE_PROGRAMS.json").read_text(encoding="utf-8"))


def affiliate_blockers(post: dict) -> list[str]:
    """Links to a registered programme need its disclosure text; unregistered affiliate-looking links are refused."""
    register = affiliate_register()
    text = f"{post.get('caption', '')}\n{post.get('text', '')}".casefold()
    blockers = []
    for link in post.get("links", []):
        lowered = link.casefold()
        program = next((item for item in register["programs"] if any(domain.casefold() in lowered for domain in item.get("domains", []))), None)
        if program:
            if program.get("disclosure_text", "").casefold() not in text:
                blockers.append(f"affiliate_disclosure_missing:{program['name']}")
        elif any(pattern in lowered for pattern in register["generic_affiliate_patterns"]):
            blockers.append(f"affiliate_link_unregistered:{link[:80]}")
    return blockers
