from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any


class ResearchAdapter(ABC):
    name: str
    is_demo: bool = False

    @abstractmethod
    def discover(self, query: str, language: str, days: int = 30) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_metadata(self, external_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def refresh_metrics(self, external_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError


def observation(**kwargs) -> dict[str, Any]:
    return {
        "source_url": "",
        "platform": "unknown",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "published_at": None,
        "country": None,
        "language": None,
        "topic": "",
        "metric_name": "",
        "metric_value": None,
        "unit": None,
        "method": "",
        "confidence": "low",
        "limitations": "",
        **kwargs,
    }
