import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


PLANNING_WEIGHTS = {
    "viewer_value": 20,
    "footage_fit": 20,
    "evidence_readiness": 20,
    "distinctiveness": 15,
    "timeliness": 10,
    "platform_fit": 10,
    "learning_value": 5,
}

EDITORIAL_WEIGHTS = {
    "viewer_promise": 15,
    "opening": 10,
    "evidence": 20,
    "visual_match": 20,
    "payoff": 15,
    "platform_fit": 10,
    "voice": 10,
}

DEFAULT_DESTINATIONS = ("facebook", "instagram", "youtube", "tiktok")


class EvidenceClaim(BaseModel):
    id: str
    text: str
    source_url: str
    evidence_type: str
    scope: str
    observed_at: datetime
    expires_at: datetime | None = None
    status: str = "verified"


class GameReception(BaseModel):
    game: str
    platform: str
    critic_provider: str | None = None
    critic_score: float | None = None
    steam_rating: str | None = None
    steam_positive_share: float | None = Field(default=None, ge=0, le=100)
    steam_review_count: int | None = Field(default=None, ge=0)
    review_window: str = "all_time"
    observed_at: datetime
    spoken_line: str = ""
    coverage_exception: str = ""


def planning_score(dimensions: dict[str, float]) -> float:
    if set(dimensions) != set(PLANNING_WEIGHTS):
        raise ValueError("planning_dimensions_required")
    if any(score < 0 or score > 5 for score in dimensions.values()):
        raise ValueError("planning_scores_must_be_between_0_and_5")
    return round(sum(PLANNING_WEIGHTS[name] * score / 5 for name, score in dimensions.items()), 2)


def planning_decision(score: float) -> str:
    if score >= 75:
        return "prioritize"
    if score >= 60:
        return "improve_weakest_component"
    return "park"


def editorial_score(dimensions: dict[str, float]) -> float:
    if set(dimensions) != set(EDITORIAL_WEIGHTS):
        raise ValueError("editorial_dimensions_required")
    if any(score < 0 or score > 5 for score in dimensions.values()):
        raise ValueError("editorial_scores_must_be_between_0_and_5")
    return round(sum(EDITORIAL_WEIGHTS[name] * score / 5 for name, score in dimensions.items()), 2)


def freshness_blockers(claims: list[EvidenceClaim], now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    blockers = []
    for claim in claims:
        if claim.status in {"unsupported", "disputed", "expired", "not_checked"}:
            blockers.append(f"claim_{claim.id}:{claim.status}")
        if claim.expires_at and claim.expires_at <= now:
            blockers.append(f"claim_{claim.id}:expired")
    return blockers


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def reception_blockers(games: list[GameReception], narration: str) -> list[str]:
    normalized_narration = _normalize(narration)
    blockers = []
    for game in games:
        if not game.spoken_line.strip() and not game.coverage_exception.strip():
            blockers.append(f"{game.game}:spoken_reception_missing")
            continue
        if game.spoken_line and _normalize(game.spoken_line) not in normalized_narration:
            blockers.append(f"{game.game}:spoken_reception_not_in_narration")
        if game.coverage_exception and _normalize(game.coverage_exception) not in normalized_narration:
            blockers.append(f"{game.game}:coverage_exception_not_in_narration")
        if game.steam_rating and game.steam_review_count is None:
            blockers.append(f"{game.game}:steam_review_count_missing")
        if game.steam_positive_share is not None and not game.steam_rating:
            blockers.append(f"{game.game}:steam_rating_missing")
    return blockers


class EditorialRegistry:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parents[2] / "content"
        import json
        self._json = json
        self.recipes = self._json.loads((self.root / "RECIPE_INDEX.json").read_text(encoding="utf-8"))
        self.ideas = self._json.loads((self.root / "IDEA_BANK.json").read_text(encoding="utf-8"))
        self.sources = self._json.loads((self.root / "SOURCE_REGISTER.json").read_text(encoding="utf-8"))
        self.config = self._json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        if len(self.recipes) != 20 or len(self.ideas) != 120 or len(self.sources) != 57:
            raise ValueError("editorial_registry_counts_invalid")
        if len({item["id"] for item in self.recipes}) != 20 or len({item["id"] for item in self.ideas}) != 120 or len({item["id"] for item in self.sources}) != 57:
            raise ValueError("editorial_registry_duplicate_ids")

    def recipe(self, recipe_id: str) -> dict:
        item = next((item for item in self.recipes if item["id"] == recipe_id), None)
        if not item:
            raise ValueError("recipe_not_found")
        return item

    def idea(self, idea_id: str) -> dict:
        item = next((item for item in self.ideas if item["id"] == idea_id), None)
        if not item:
            raise ValueError("idea_not_found")
        return item

    def source(self, source_id: str) -> dict:
        item = next((item for item in self.sources if item["id"] == source_id), None)
        if not item:
            raise ValueError("source_not_found")
        return item

    def ideas_for_lane(self, lane: str) -> list[dict]:
        return [item for item in self.ideas if item["lane"] == lane]
