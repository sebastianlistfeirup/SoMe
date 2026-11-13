import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, model_validator


PREPARATION_FRESHNESS = timedelta(hours=168)
RELEASE_FRESHNESS = timedelta(hours=720)
GENERIC_TARGETS = {"", "all", "any", "cross platform", "multi platform", "multiple platforms"}


def normalize_game_platform(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    aliases = {
        "pc games": "pc",
        "windows": "pc",
        "playstation 1": "ps1",
        "playstation one": "ps1",
        "playstation 2": "ps2",
        "playstation 3": "ps3",
        "playstation 4": "ps4",
        "playstation 5": "ps5",
        "nintendo switch": "switch",
        "nintendo switch 2": "switch 2",
        "x box series x": "xbox series x",
        "xbox series x s": "xbox series x",
    }
    return aliases.get(normalized, normalized)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class PlatformRelease(BaseModel):
    platform: str = Field(min_length=1, max_length=80)
    source_url: HttpUrl
    evidence_note: str = Field(min_length=5, max_length=1000)
    verified_at: datetime


class GamePreparation(BaseModel):
    mobygames_url: HttpUrl
    review_score: str | None = Field(default=None, max_length=100)
    review_note: str = Field(default="", max_length=1000)
    fun_facts: list[str] = Field(default_factory=list, max_length=20)
    fun_facts_note: str = Field(default="", max_length=1000)
    observed_at: datetime
    release_platforms: list[PlatformRelease] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def valid_mobygames_entry(self):
        parsed = urlparse(str(self.mobygames_url))
        if parsed.scheme != "https" or parsed.hostname not in {"mobygames.com", "www.mobygames.com"} or not parsed.path.startswith("/game/"):
            raise ValueError("specific_mobygames_game_entry_required")
        if any(len(fact.strip()) < 5 or len(fact) > 500 for fact in self.fun_facts):
            raise ValueError("mobygames_fun_fact_length_invalid")
        return self


def game_preparation_blockers(game: str, preparation: GamePreparation, target_platform: str = "cross-platform", now: datetime | None = None) -> list[str]:
    now = as_utc(now or datetime.now(timezone.utc))
    observed = as_utc(preparation.observed_at)
    blockers = []
    if observed > now + timedelta(minutes=5):
        blockers.append(f"{game}:mobygames_observed_at_in_future")
    if now - observed > PREPARATION_FRESHNESS:
        blockers.append(f"{game}:mobygames_refresh_required")
    if not (preparation.review_score or "").strip() and not preparation.review_note.strip():
        blockers.append(f"{game}:mobygames_review_score_or_not_found_note_required")
    if not preparation.fun_facts and not preparation.fun_facts_note.strip():
        blockers.append(f"{game}:mobygames_fun_facts_or_not_found_note_required")
    for release in preparation.release_platforms:
        verified = as_utc(release.verified_at)
        if verified > now + timedelta(minutes=5) or now - verified > RELEASE_FRESHNESS:
            blockers.append(f"{game}:platform_release_refresh_required:{release.platform}")
    target = normalize_game_platform(target_platform)
    if target not in GENERIC_TARGETS:
        released = any(normalize_game_platform(release.platform) == target for release in preparation.release_platforms)
        if not released:
            blockers.append(f"{game}:platform_release_unverified:{target_platform}")
    return blockers
