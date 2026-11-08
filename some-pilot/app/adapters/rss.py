from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.adapters.base import ResearchAdapter


class RSSAdapter(ResearchAdapter):
    name = "rss"

    def __init__(self, feed_url: str, topic: str):
        self.feed_url = feed_url
        self.topic = topic

    def discover(self, query: str, language: str, days: int = 30) -> list[dict[str, Any]]:
        response = httpx.get(self.feed_url, timeout=20, follow_redirects=False, headers={"User-Agent": "SoMePilot/0.1 research"})
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        rows = []
        for entry in feed.entries[:20]:
            title = entry.get("title", "")
            if query.lower() not in title.lower():
                continue
            rows.append({
                "source_url": entry.get("link", self.feed_url),
                "platform": "rss",
                "collected_at_utc": datetime.now(timezone.utc),
                "published_at": entry.get("published"),
                "country": None,
                "language": language,
                "topic": f"{self.topic}:{title}",
                "metric_name": "publication",
                "metric_value": 1,
                "unit": "item",
                "method": "public RSS; untrusted editorial signal",
                "confidence": "medium",
                "limitations": "Publication is not popularity. Content is research input only, not production rights.",
            })
        return rows

    def fetch_metadata(self, external_id: str) -> dict[str, Any]:
        raise NotImplementedError("RSS entries are discovered as a feed")

    def refresh_metrics(self, external_id: str) -> dict[str, Any]:
        raise NotImplementedError("RSS has no metrics")

    def capabilities(self) -> dict[str, Any]:
        return {"data_mode": "rss", "discover": True, "metadata": False, "refresh": False, "metrics": False}
