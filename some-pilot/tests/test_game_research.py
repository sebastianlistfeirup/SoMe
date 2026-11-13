from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.pipeline.game_research import GamePreparation, game_preparation_blockers, normalize_game_platform


def preparation(now, platforms=("PS5", "PC", "Switch 2")):
    return GamePreparation.model_validate({
        "mobygames_url": "https://www.mobygames.com/game/104222/into-the-breach/",
        "review_score": None,
        "review_note": "No score is claimed by this synthetic test.",
        "fun_facts": ["A documented trivia item from the inspected game entry."],
        "fun_facts_note": "",
        "observed_at": now.isoformat(),
        "release_platforms": [
            {
                "platform": platform,
                "source_url": "https://publisher.example/release",
                "evidence_note": "Synthetic release evidence for platform-gate testing.",
                "verified_at": now.isoformat(),
            }
            for platform in platforms
        ],
    })


def test_platform_aliases_do_not_use_folder_spelling_as_a_release_rule():
    assert normalize_game_platform("PlayStation 5") == "ps5"
    assert normalize_game_platform("Nintendo Switch 2") == "switch 2"
    assert normalize_game_platform("PC games") == "pc"
    assert normalize_game_platform("X box Series X") == "xbox series x"


def test_ps5_footage_can_support_a_pc_post_when_pc_release_is_verified():
    now = datetime.now(timezone.utc)
    research = preparation(now, platforms=("PS5", "PC"))
    assert game_preparation_blockers("Example game", research, "PC", now) == []


def test_switch_2_post_is_blocked_without_a_verified_switch_2_release():
    now = datetime.now(timezone.utc)
    research = preparation(now, platforms=("PS5", "PC"))
    assert game_preparation_blockers("Example game", research, "Switch 2", now) == ["Example game:platform_release_unverified:Switch 2"]


def test_cross_platform_post_does_not_require_one_target_console():
    now = datetime.now(timezone.utc)
    research = preparation(now, platforms=("PS5",))
    assert game_preparation_blockers("Example game", research, "cross-platform", now) == []


def test_mobygames_score_and_trivia_require_values_or_explicit_not_found_notes():
    now = datetime.now(timezone.utc)
    research = preparation(now).model_copy(update={"review_note": "", "fun_facts": [], "fun_facts_note": ""})
    blockers = game_preparation_blockers("Example game", research, "PC", now)
    assert "Example game:mobygames_review_score_or_not_found_note_required" in blockers
    assert "Example game:mobygames_fun_facts_or_not_found_note_required" in blockers


def test_only_specific_mobygames_game_entries_are_accepted():
    payload = preparation(datetime.now(timezone.utc)).model_dump(mode="json")
    payload["mobygames_url"] = "https://example.com/game/104222/into-the-breach/"
    with pytest.raises(ValidationError, match="specific_mobygames_game_entry_required"):
        GamePreparation.model_validate(payload)


def test_old_research_and_release_evidence_must_be_refreshed():
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=31)
    research = preparation(old)
    blockers = game_preparation_blockers("Example game", research, "PC", now)
    assert "Example game:mobygames_refresh_required" in blockers
    assert "Example game:platform_release_refresh_required:PC" in blockers


def test_ranking_gate_uses_target_game_platform_not_social_destination():
    from app.pipeline.production_ranking import evaluate_ranking_editorial
    from tests.test_ranking import plan

    now = datetime.now(timezone.utc)
    payload = plan().model_dump(mode="json")
    payload["target_game_platform"] = "Switch 2"
    payload["quality_dimensions"] = {name: 5 for name in ("viewer_promise", "opening", "evidence", "visual_match", "payoff", "platform_fit", "voice")}
    ranking = type(plan()).model_validate(payload)
    result = evaluate_ranking_editorial(ranking, ranking.hook, now)
    assert all("platform_release_unverified:Switch 2" in blocker for blocker in result["blockers"] if "platform_release_unverified" in blocker)
    assert sum("platform_release_unverified:Switch 2" in blocker for blocker in result["blockers"]) == 10


def test_editorial_packet_allows_ps5_footage_for_pc_but_blocks_unverified_switch_2_target():
    from app.pipeline.editorial import evaluate_editorial_packet
    from tests.test_editorial import complete_packet, full_quality

    now = datetime.now(timezone.utc)
    packet = complete_packet(now)
    game = packet["games"][0]
    game["footage_platform"] = "PS5"
    narration = " ".join(segment["voiceover"] for segment in packet["segments"])
    assert evaluate_editorial_packet(packet, narration, full_quality(), now)["decision"] == "ALLOW"

    game["reviewed_platform"] = "Switch 2"
    result = evaluate_editorial_packet(packet, narration, full_quality(), now)
    assert result["decision"] == "BLOCK"
    assert "Into the Breach:platform_release_unverified:Switch 2" in result["blockers"]
