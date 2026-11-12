import json
import re
from datetime import datetime, timedelta, timezone
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


def evaluate_editorial_packet(packet: dict, narration: str, quality_dimensions: dict[str, float] | None, now: datetime | None = None) -> dict:
    from jsonschema import ValidationError as SchemaValidationError, validate

    now = now or datetime.now(timezone.utc)
    blockers = []
    root = Path(__file__).resolve().parents[2] / "content"
    try:
        validate(packet, json.loads((root / "schemas" / "packet.schema.json").read_text(encoding="utf-8")))
    except SchemaValidationError as exc:
        return {"decision": "BLOCK", "score": 0, "blockers": [f"editorial_packet_schema:{exc.message}"], "source_valid_until": None}
    if packet["state"] not in {"needs_owner_review", "approved_draft"}:
        blockers.append(f"editorial_packet_not_production_ready:{packet['state']}")
    try:
        EditorialRegistry(root).recipe(packet["recipe_id"])
    except ValueError as exc:
        blockers.append(str(exc))
    try:
        score = editorial_score(quality_dimensions or {})
    except ValueError as exc:
        score = 0
        blockers.append(str(exc))
    if score < 85:
        blockers.append("editorial_quality_below_85")
    sources = {item["id"]: item for item in packet["sources"]}
    claims = []
    valid_until = []
    for item in packet["claims"]:
        linked = [sources[source_id] for source_id in item["source_ids"] if source_id in sources]
        if len(linked) != len(item["source_ids"]) or not linked:
            blockers.append(f"claim_{item['id']}:inspected_source_missing")
            continue
        for source in linked:
            if source["access_status"] != "inspected":
                blockers.append(f"claim_{item['id']}:source_{source['id']}_{source['access_status']}")
        observed = max(datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00")) for source in linked)
        expiries = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in [item["expires_at"], *[source["expires_at"] for source in linked]] if value]
        expiry = min(expiries) if expiries else observed + timedelta(hours=168)
        valid_until.append(expiry)
        claims.append(EvidenceClaim(
            id=item["id"],
            text=item["text"],
            source_url=linked[0]["url"],
            evidence_type=item["evidence_type"],
            scope=item["scope"],
            observed_at=observed,
            expires_at=expiry,
            status="not_checked" if item["status"] == "proposed" else item["status"],
        ))
    blockers.extend(freshness_blockers(claims, now))
    games = []
    for item in packet["games"]:
        source_ids = [item["official_description_source_id"], *item["critic"]["source_ids"], *item["steam"]["source_ids"]]
        linked = [sources[source_id] for source_id in source_ids if source_id in sources]
        observed = max((datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00")) for source in linked), default=now)
        valid_until.append(observed + timedelta(hours=24))
        for kind in ("critic", "steam"):
            status = item[kind]["status"]
            if status not in {"verified", "not_found_after_search", "not_applicable"}:
                blockers.append(f"{item['title']}:{kind}_{status}")
        reception_segments = [segment for segment in packet["segments"] if item["id"] in segment["reception_for"]]
        exception = "" if reception_segments else " ".join(filter(None, [item["critic"]["reason"] if item["critic"]["status"] == "not_found_after_search" else "", item["steam"]["reason"] if item["steam"]["status"] == "not_found_after_search" else ""]))
        games.append(GameReception(
            game=item["title"],
            platform=item["reviewed_platform"],
            observed_at=observed,
            spoken_line=" ".join(segment["voiceover"] for segment in reception_segments),
            coverage_exception=exception,
        ))
    blockers.extend(reception_blockers(games, narration))
    expiry = min(valid_until) if valid_until else None
    return {
        "decision": "ALLOW" if not blockers else "BLOCK",
        "score": score,
        "threshold": 85,
        "blockers": blockers,
        "source_refresh_checked_at": now.isoformat(),
        "source_valid_until": expiry.isoformat() if expiry else None,
        "claims_checked": len(claims),
        "games_checked": len(games),
    }
