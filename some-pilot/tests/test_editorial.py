from datetime import datetime, timedelta, timezone

import pytest

from app.pipeline.editorial import EditorialRegistry, EvidenceClaim, GameReception, editorial_score, freshness_blockers, planning_decision, planning_score, reception_blockers


def test_registry_has_all_recipes_ideas_sources_and_default_destinations():
    registry = EditorialRegistry()
    assert len(registry.recipes) == 20
    assert len(registry.ideas) == 120
    assert len(registry.sources) == 57
    assert registry.recipe("GF01")["title"] == "The Amiga Corner"
    assert registry.idea("GI001")["lane"] == "gaming"
    assert registry.source("G01")["url"].startswith("https://")
    assert registry.config["publish_mode"] == "automatic_after_owner_approval"
    assert set(registry.config["publishing"]["default_destinations"]) == {"facebook", "instagram", "youtube", "tiktok"}


def test_planning_and_editorial_scores_use_bible_weights():
    dimensions = {name: 5 for name in ("viewer_value", "footage_fit", "evidence_readiness", "distinctiveness", "timeliness", "platform_fit", "learning_value")}
    assert planning_score(dimensions) == 100
    assert planning_decision(75) == "prioritize"
    assert planning_decision(60) == "improve_weakest_component"
    assert planning_decision(59) == "park"
    quality = {name: 4.25 for name in ("viewer_promise", "opening", "evidence", "visual_match", "payoff", "platform_fit", "voice")}
    assert editorial_score(quality) == 85


def test_freshness_expiry_is_a_hard_blocker():
    now = datetime.now(timezone.utc)
    claim = EvidenceClaim(id="price-1", text="Price is $10", source_url="https://example.com", evidence_type="retailer", scope="US", observed_at=now - timedelta(days=1), expires_at=now - timedelta(seconds=1))
    assert freshness_blockers([claim], now) == ["claim_price-1:expired"]


def test_every_game_reception_must_be_spoken_and_match_narration():
    game = GameReception(game="Into the Breach", platform="pc", observed_at=datetime.now(timezone.utc), spoken_line="On PC, Metacritic lists it at 90, and Steam's English reviews are Very Positive.")
    assert reception_blockers([game], "On PC, Metacritic lists it at 90, and Steam's English reviews are Very Positive.") == []
    assert "Into the Breach:spoken_reception_not_in_narration" in reception_blockers([game], "A different sentence")
    missing = GameReception(game="XCOM 2", platform="pc", observed_at=datetime.now(timezone.utc))
    assert "XCOM 2:spoken_reception_missing" in reception_blockers([missing], "No reception")
    retro = GameReception(game="Cannon Fodder", platform="amiga", observed_at=datetime.now(timezone.utc), coverage_exception="I couldn't verify comparable modern coverage for the original Amiga release.")
    assert reception_blockers([retro], "I couldn't verify comparable modern coverage for the original Amiga release.") == []
