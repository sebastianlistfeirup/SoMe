import json
from pathlib import Path
from typing import Any

from app.adapters.base import ResearchAdapter


class FixtureAdapter(ResearchAdapter):
    name = "fixture"
    is_demo = True

    def __init__(self, path: Path):
        self.path = path
        self.rows = json.loads(path.read_text(encoding="utf-8"))["observations"]

    def discover(self, query: str, language: str, days: int = 30) -> list[dict[str, Any]]:
        return [row for row in self.rows if query.lower() in row["topic"].lower() and row.get("language") == language]

    def fetch_metadata(self, external_id: str) -> dict[str, Any]:
        for row in self.rows:
            if row["topic"] == external_id:
                return row
        raise KeyError(external_id)

    def refresh_metrics(self, external_id: str) -> dict[str, Any]:
        return self.fetch_metadata(external_id)

    def capabilities(self) -> dict[str, Any]:
        return {"data_mode": "demo", "discover": True, "metadata": True, "refresh": False, "external_changes": False}
