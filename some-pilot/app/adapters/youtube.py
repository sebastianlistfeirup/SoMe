from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.adapters.base import ResearchAdapter
from app.config import get_settings


class YouTubeAdapter(ResearchAdapter):
    name = "youtube"
    api_url = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or get_settings().youtube_api_key

    def _get(self, path: str, params: dict) -> dict:
        if not self.api_key:
            raise RuntimeError("youtube_api_key_missing")
        response = httpx.get(f"{self.api_url}/{path}", params={**params, "key": self.api_key}, timeout=20)
        response.raise_for_status()
        return response.json()

    def discover(self, query: str, language: str, days: int = 30) -> list[dict[str, Any]]:
        published_after = datetime.now(timezone.utc) - timedelta(days=days)
        search = self._get("search", {"part": "snippet", "q": query, "type": "video", "order": "date", "maxResults": 20, "publishedAfter": published_after.isoformat(), "relevanceLanguage": language})
        ids = [item["id"]["videoId"] for item in search.get("items", [])]
        if not ids:
            return []
        metadata = self._get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids)})
        rows = []
        for item in metadata.get("items", []):
            snippet = item["snippet"]
            stats = item.get("statistics", {})
            rows.append({
                "source_url": f"https://www.youtube.com/watch?v={item['id']}",
                "platform": "youtube",
                "collected_at_utc": datetime.now(timezone.utc),
                "published_at": snippet.get("publishedAt"),
                "country": None,
                "language": language,
                "topic": f"{query}:{snippet.get('title', '')}",
                "metric_name": "views",
                "metric_value": int(stats["viewCount"]) if "viewCount" in stats else None,
                "unit": "views",
                "method": "YouTube Data API v3 search.list + videos.list",
                "confidence": "high",
                "limitations": "Cumulative views; not views/hour. Search sample is not representative. Channel and format normalization required.",
            })
        return rows

    def fetch_metadata(self, external_id: str) -> dict[str, Any]:
        return self._get("videos", {"part": "snippet,statistics,contentDetails,status", "id": external_id})

    def refresh_metrics(self, external_id: str) -> dict[str, Any]:
        return self._get("videos", {"part": "statistics", "id": external_id})

    def capabilities(self) -> dict[str, Any]:
        return {"data_mode": "api" if self.api_key else "not_configured", "discover": bool(self.api_key), "metadata": bool(self.api_key), "refresh": bool(self.api_key), "analytics": bool(get_settings().youtube_refresh_token), "publishing": False}
