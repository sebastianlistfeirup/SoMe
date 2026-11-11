import json

import pytest
from pydantic import ValidationError

from app.pipeline.ranking import RankingPlan, RankingScene, storyboard_frames


def scene(rank: int = 1) -> dict:
    return {
        "rank": rank,
        "game": "Test game",
        "kicker": "Precise and readable",
        "narration": "An original editorial explanation for this game.",
        "clip_url": "https://publisher.example/gameplay",
        "policy_url": "https://publisher.example/policy",
        "source_path": f"clips/{rank}.mp4",
        "source_duration_seconds": 90,
        "rights_holder": "Publisher",
        "rights_evidence": "Official video policy permits edited, monetized gameplay videos.",
        "music_allowed": False,
        "attribution": "Publisher and official game URL",
    }


def plan() -> RankingPlan:
    return RankingPlan.model_validate({
        "title": "10 games worth your time on Legion Go 2",
        "hook": "Ten excellent games, ranked for handheld play.",
        "post_text": "Our editorial handheld picks with original commentary.",
        "scenes": [scene(rank) for rank in range(1, 11)],
    })


def test_plan_requires_all_unique_ranks():
    payload = plan().model_dump(mode="json")
    payload["scenes"][1]["rank"] = 1
    with pytest.raises(ValidationError, match="ranks_must_be_unique"):
        RankingPlan.model_validate(payload)


def test_plan_requires_exactly_ten_real_clips():
    payload = plan().model_dump(mode="json")
    payload["scenes"] = payload["scenes"][:9]
    with pytest.raises(ValidationError):
        RankingPlan.model_validate(payload)


def test_caption_blocks_never_exceed_two_lines():
    from app.pipeline.ranking import _wrap_caption
    for chunk in _wrap_caption("This is a deliberately long narration that should wrap into multiple compact caption blocks instead of overflowing the mobile safe area."):
        assert len(chunk.splitlines()) <= 2
        assert all(len(line) <= 34 for line in chunk.splitlines())


def test_storyboard_scales_to_video_duration():
    assert storyboard_frames(100) == [1.0, 16.0, 31.0, 46.0, 61.0, 76.0, 94.0]
    with pytest.raises(ValueError):
        storyboard_frames(0)


def test_editorial_rank_direction():
    from scripts.review_steam_clips import RANKS
    assert 10 - RANKS.index("Hades II") == 1
    assert 10 - RANKS.index("Hollow Knight: Silksong") == 2
    assert 10 - RANKS.index("Transistor") == 10


def test_hook_title_fits_safe_area():
    from PIL import ImageFont
    from app.pipeline.ranking import FONT_BOLD
    face = ImageFont.truetype(FONT_BOLD, 62)
    assert face.getbbox("TOP 10: LEGION GO 2")[2] <= 940


def test_long_transcription_similarity_does_not_use_autojunk():
    from app.pipeline.production import transcription_quality
    script = "This is a longer editorial narration about excellent handheld games and precise controls. " * 20
    result = transcription_quality(script, {"language_probability": 0.99, "segments_detail": [{"text": script}]})
    assert result["similarity"] == 1.0
    assert result["decision"] == "ALLOW"


def test_production_requires_real_media_plan(db):
    from app.db.models import Topic
    from app.pipeline.production import produce
    topic = Topic(niche="handheld_gaming", language="en", title="Production")
    db.add(topic)
    db.commit()
    with pytest.raises(ValueError, match="real_media_plan_required"):
        produce(db, topic.id, False)


def test_vertical_crop_fills_the_entire_frame():
    from app.pipeline.ranking import _crop_filter, get_platform
    result = _crop_filter(RankingScene.model_validate(scene()), 1920, 1080, get_platform("tiktok"))
    assert result == "[0:v]crop=608:1080:656.000:0.000,scale=1080:1920,setsar=1[composite];"
    assert "gblur" not in result


def test_platform_safe_areas_and_landscape_are_distinct():
    from app.pipeline.ranking import _crop_filter, get_platform
    assert get_platform("tiktok").caption_bottom != get_platform("reels").caption_bottom
    result = _crop_filter(RankingScene.model_validate(scene()), 1920, 1080, get_platform("youtube"))
    assert "scale=1920:1080" in result
    assert "crop=608" not in result


def test_youtube_uses_reviewed_tempo_without_scene_truncation():
    from app.pipeline.ranking import get_platform
    assert get_platform("youtube").tempo == 1.07
    assert get_platform("tiktok").tempo == 1.0
    assert get_platform("reels").tempo == 1.0


def test_safe_mobile_layout_preserves_full_gameplay_width():
    from app.pipeline.mobile import mobile_filter
    from app.pipeline.ranking import get_platform
    result = mobile_filter(RankingScene.model_validate(scene()), 1920, 1080, get_platform("reels"), "safe", 10)
    assert "scale=1040:-2" in result
    assert "crop=608" not in result
    assert "overlay=(W-w)/2:(H-h)/2" in result


def test_zoom_mobile_layout_has_two_single_frame_zoom_phases():
    from app.pipeline.mobile import mobile_filter
    from app.pipeline.ranking import get_platform
    result = mobile_filter(RankingScene.model_validate(scene()), 1920, 1080, get_platform("reels"), "zoom", 10)
    assert result.count("zoompan=") == 2
    assert result.count(":d=1:s=1080x1920") == 2
    assert result.count("setpts=N/(30*TB)") == 4
    assert "trim=duration=1.800" in result
    assert result.count("trim=duration=2.800") == 1
    assert "trim=duration=2.000" in result
    assert result.count("trim=duration=3.400") == 1
    assert "concat=n=4:v=1:a=0" in result


def test_ranking_claim_control_documents_names_ranks_and_hades_evidence():
    from app.pipeline.ranking_claims import ranking_claim_control
    payload = plan().model_dump(mode="json")
    payload["post_text"] = "Editorial ranking, not an FPS benchmark. Independent and unsponsored."
    for item in payload["scenes"]:
        item["game"] = "Hades II" if item["rank"] == 1 else f"Game {item['rank']}"
        word = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}[item["rank"]]
        item["narration"] = f"At number {word}, {item['game']} is our editorial handheld pick."
    payload["scenes"][0]["narration"] += " It has Steam Deck Verified status."
    payload["claims"] = [{"id": "hades-2-deck-verified", "text": "Hades II is Steam Deck Verified.", "source_url": "https://publisher.example/hades-faq", "evidence_note": "Official publisher FAQ confirms the status.", "game": "Hades II", "verified": True, "verified_at": "2026-11-09"}]
    result = ranking_claim_control(RankingPlan.model_validate(payload))
    assert result["decision"] == "ALLOW"
    assert result["checked_rank_order"][0] == {"rank": 1, "game": "Hades II"}


def test_ranking_claim_control_blocks_unsupported_benchmarks_and_missing_evidence():
    from app.pipeline.ranking_claims import ranking_claim_control
    payload = plan().model_dump(mode="json")
    payload["post_text"] = "Editorial ranking, not an FPS benchmark."
    for item in payload["scenes"]:
        item["game"] = "Hades II" if item["rank"] == 1 else f"Game {item['rank']}"
        word = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}[item["rank"]]
        item["narration"] = f"At number {word}, {item['game']} is our pick."
    payload["scenes"][0]["narration"] += " It is Steam Deck Verified and we measured 90 FPS."
    result = ranking_claim_control(RankingPlan.model_validate(payload))
    assert result["decision"] == "BLOCK"
    assert "unsupported_performance_claim:fps" in result["issues"]
    assert "hades_ii_deck_verified_evidence_missing" in result["issues"]
