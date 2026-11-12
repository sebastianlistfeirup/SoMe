import json
import re
from datetime import datetime, timezone

import httpx

from app.pipeline.editorial import GameReception


class ReceptionError(RuntimeError):
    pass


def steam_reception(app_id: int, platform: str = "pc", recent_days: int | None = None, now: datetime | None = None) -> GameReception:
    params = {
        "appid": app_id,
        "filter": "all",
        "language": "english",
        "review_type": "all",
        "purchase_type": "all",
        "num_per_page": 100,
    }
    if recent_days is not None:
        params["day_range"] = recent_days
    try:
        response = httpx.get(
            "https://api.steamPowered.com/IUserReviewsService/GetAppReviews/v1/",
            params={"input_json": json.dumps(params, separators=(",", ":"))},
            headers={"Accept": "application/json"},
            timeout=30,
        )
    except httpx.TimeoutException as exc:
        raise ReceptionError("steam_reception_timeout") from exc
    if response.status_code != 200:
        raise ReceptionError(f"steam_reception_unavailable:{response.status_code}")
    body = response.json()
    if body.get("success") != 1:
        raise ReceptionError("steam_reception_query_failed")
    summary = body.get("query_summary", {})
    total = summary.get("total_reviews")
    positive = summary.get("total_positive")
    rating = summary.get("review_score_desc")
    if not total or positive is None or not rating:
        raise ReceptionError("steam_reception_incomplete")
    share = round(positive / total * 100, 1)
    scope = f"last_{recent_days}_days" if recent_days is not None else "all_time"
    line = f"Steam's English reviews are {rating}, with {share}% positive reviews."
    return GameReception(
        game=f"steam_app_{app_id}",
        platform=platform,
        steam_rating=rating,
        steam_positive_share=share,
        steam_review_count=total,
        review_window=scope,
        observed_at=now or datetime.now(timezone.utc),
        spoken_line=line,
        coverage_exception="",
    )


def metacritic_reception(game_slug: str, platform: str = "pc", now: datetime | None = None) -> GameReception:
    url = f"https://www.metacritic.com/game/{game_slug}/critic-reviews/?platform={platform}"
    try:
        response = httpx.get(url, headers={"User-Agent": "SoMeResearch/1.0", "Accept": "text/html"}, timeout=30)
    except httpx.TimeoutException as exc:
        raise ReceptionError("metacritic_reception_timeout") from exc
    if response.status_code != 200:
        raise ReceptionError(f"metacritic_reception_unavailable:{response.status_code}")
    match = re.search(r'"criticScore"\s*:\s*(\d+(?:\.\d+)?)', response.text)
    if not match:
        raise ReceptionError("metacritic_score_not_found")
    score = float(match.group(1))
    return GameReception(
        game=game_slug,
        platform=platform,
        critic_provider="metacritic",
        critic_score=score,
        observed_at=now or datetime.now(timezone.utc),
        spoken_line=f"On {platform.upper()}, Metacritic lists it at {score:g}.",
        coverage_exception="",
    )
