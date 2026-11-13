from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.adapters.base import ResearchAdapter
from app.config import get_settings


MIN_SUBSCRIBERS_FOR_RATIO = 100


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
        channel_ids = sorted({item["snippet"].get("channelId") for item in metadata.get("items", []) if item.get("snippet", {}).get("channelId")})
        subscribers: dict[str, int] = {}
        if channel_ids:
            channels = self._get("channels", {"part": "statistics", "id": ",".join(channel_ids[:50])})
            for channel in channels.get("items", []):
                stats = channel.get("statistics", {})
                if not stats.get("hiddenSubscriberCount") and stats.get("subscriberCount"):
                    subscribers[channel["id"]] = int(stats["subscriberCount"])
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
            channel_subs = subscribers.get(snippet.get("channelId"))
            if "viewCount" in stats and channel_subs and channel_subs >= MIN_SUBSCRIBERS_FOR_RATIO:
                rows.append({**rows[-1], "metric_name": "views_per_subscriber", "metric_value": round(int(stats["viewCount"]) / channel_subs, 4), "unit": "ratio", "method": "videos.list viewCount / channels.list subscriberCount", "limitations": "Outlier signal: views relative to the channel's own size. Subscriber counts are rounded by YouTube; hidden counts are skipped."})
        return rows

    def fetch_metadata(self, external_id: str) -> dict[str, Any]:
        return self._get("videos", {"part": "snippet,statistics,contentDetails,status", "id": external_id})

    def refresh_metrics(self, external_id: str) -> dict[str, Any]:
        return self._get("videos", {"part": "statistics", "id": external_id})

    def capabilities(self) -> dict[str, Any]:
        return {"data_mode": "api" if self.api_key else "not_configured", "discover": bool(self.api_key), "metadata": bool(self.api_key), "refresh": bool(self.api_key), "analytics": bool(get_settings().youtube_refresh_token), "publishing": False}
