"""Upcoming game releases for timing 'event' stories.

Manual entries in content/RELEASE_CALENDAR.json are the default source. The
optional IGDB import uses Twitch client credentials and runs only when the owner
has confirmed IGDB's terms allow this channel's (commercial) use. Releases
become idea suggestions with a lead time, never facts: dates move and must be
re-checked before production.
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import IdeaSuggestion, Setting

CALENDAR = Path(__file__).resolve().parents[2] / "content" / "RELEASE_CALENDAR.json"
CACHE_KEY = "release_calendar_igdb"
LEAD_MIN_DAYS = 7
LEAD_MAX_DAYS = 45
RECIPE_HINTS = (
    (("steam deck", "rog ally", "legion go", "switch", "handheld"), "GF05", "The Handheld Reality Check"),
    (("remaster", "remake", "collection", "classic"), "GF02", "Great Games That Are Not New"),
    (("amiga",), "GF01", "The Amiga Corner"),
)


def load_manual(path: Path | None = None) -> list[dict]:
    releases = []
    for item in json.loads((path or CALENDAR).read_text(encoding="utf-8"))["releases"]:
        if not (item.get("source_url", "").startswith("https://") and item.get("checked_at")):
            continue
        releases.append({**item, "source": "manual"})
    return releases


def igdb_configured() -> bool:
    settings = get_settings()
    return bool(settings.igdb_client_id and settings.igdb_client_secret and settings.igdb_terms_confirmed)


def fetch_igdb(db: Session, days: int = LEAD_MAX_DAYS, now: datetime | None = None) -> list[dict]:
    if not igdb_configured():
        return []
    settings = get_settings()
    now = now or datetime.now(timezone.utc)
    token = httpx.post("https://id.twitch.tv/oauth2/token", params={"client_id": settings.igdb_client_id, "client_secret": settings.igdb_client_secret, "grant_type": "client_credentials"}, timeout=20)
    token.raise_for_status()
    start, end = int(now.timestamp()), int((now + timedelta(days=days)).timestamp())
    query = f"fields date,human,platform.name,game.name,game.hypes,game.url; where date > {start} & date < {end} & game.hypes > 5; sort date asc; limit 200;"
    response = httpx.post("https://api.igdb.com/v4/release_dates", headers={"Client-ID": settings.igdb_client_id, "Authorization": f"Bearer {token.json()['access_token']}"}, content=query, timeout=30)
    response.raise_for_status()
    grouped: dict[str, dict] = {}
    for row in response.json():
        game = (row.get("game") or {}).get("name")
        if not game or not row.get("date"):
            continue
        entry = grouped.setdefault(game, {"game": game, "release_date": datetime.fromtimestamp(row["date"], timezone.utc).date().isoformat(), "platforms": [], "source_url": (row.get("game") or {}).get("url") or "https://www.igdb.com/", "checked_at": now.isoformat(), "hype": (row.get("game") or {}).get("hypes", 0), "source": "igdb"})
        platform = (row.get("platform") or {}).get("name")
        if platform and platform not in entry["platforms"]:
            entry["platforms"].append(platform)
    releases = list(grouped.values())
    db.merge(Setting(key=CACHE_KEY, value_json={"fetched_at": now.isoformat(), "releases": releases}))
    db.commit()
    return releases


def upcoming(db: Session, today: date | None = None, horizon_days: int = 90) -> list[dict]:
    today = today or datetime.now(timezone.utc).date()
    cache = db.get(Setting, CACHE_KEY)
    releases = load_manual() + ((cache.value_json.get("releases", []) if cache else []))
    seen, result = set(), []
    for item in sorted(releases, key=lambda row: row["release_date"]):
        key = item["game"].casefold()
        when = date.fromisoformat(item["release_date"][:10])
        if key in seen or not (today <= when <= today + timedelta(days=horizon_days)):
            continue
        seen.add(key)
        result.append({**item, "days_until": (when - today).days})
    return result


def recipe_hint(release: dict) -> tuple[str, str]:
    text = " ".join([release["game"], *release.get("platforms", []), release.get("notes", "")]).casefold()
    for words, recipe_id, title in RECIPE_HINTS:
        if any(word in text for word in words):
            return recipe_id, title
    return "GF03", "The Ranked Top 10, 15 or 20"


def suggestions_from_releases(db: Session, today: date | None = None) -> list[IdeaSuggestion]:
    created = []
    for release in upcoming(db, today):
        if not LEAD_MIN_DAYS <= release["days_until"] <= LEAD_MAX_DAYS:
            continue
        title = f"Upcoming release: {release['game']} ({release['release_date'][:10]})"
        if db.query(IdeaSuggestion).filter(IdeaSuggestion.title == title).first():
            continue
        recipe_id, recipe_title = recipe_hint(release)
        rationale = f"{release['game']} releases in {release['days_until']} days on {', '.join(release.get('platforms') or ['unknown platforms'])}. Prepare an event story now (suggested recipe {recipe_id}: {recipe_title}). Re-check the date before production."
        suggestion = IdeaSuggestion(idea_id=None, lane="gaming", title=title, query=release["game"], rationale=rationale, evidence_json={"release": release, "recipe_hint": recipe_id, "limitations": "Release dates change; this is a planning signal, not a verified fact."}, score=float(LEAD_MAX_DAYS - release["days_until"]))
        db.add(suggestion)
        created.append(suggestion)
    db.commit()
    return created


def refresh(db: Session) -> dict:
    fetched = []
    error = None
    try:
        fetched = fetch_igdb(db)
    except Exception as exc:
        error = type(exc).__name__
    created = suggestions_from_releases(db)
    return {"igdb_configured": igdb_configured(), "igdb_fetched": len(fetched), "igdb_error": error, "upcoming": len(upcoming(db)), "suggestions": [item.id for item in created]}
