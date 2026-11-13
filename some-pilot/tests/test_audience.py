import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.db.models import IdeaSuggestion, MetricSnapshot, Publication, VideoComment, VideoVersion
from app.pipeline import audience
from app.pipeline.experiments import ExperimentSpec, create_experiment
from app.pipeline.ideas import rank_ideas

NOW = datetime.now(timezone.utc)


def test_series_registry_validation_and_idea_ranking_link():
    series = audience.load_series()
    assert {"hidden-gem-of-the-week", "amiga-corner"} <= {item["id"] for item in series}
    audience.validate_series(None, "GF02")
    audience.validate_series("hidden-gem-of-the-week", "GF02")
    with pytest.raises(ValueError, match="series_unknown"):
        audience.validate_series("made-up", None)
    with pytest.raises(ValueError, match="series_recipe_mismatch"):
        audience.validate_series("hidden-gem-of-the-week", "GF01")
    assert audience.series_by_recipe()["GF02"] == "hidden-gem-of-the-week"


def test_rank_ideas_marks_series_ideas(db):
    ranked = rank_ideas(db, 120, lane="gaming")
    gf02 = [item for item in ranked if item["recipe_id"] == "GF02"]
    assert gf02 and all(item["series_id"] == "hidden-gem-of-the-week" for item in gf02)


def test_series_report_groups_by_series(db, awaiting_video):
    for index, (series, subs) in enumerate((("hidden-gem-of-the-week", 4), ("hidden-gem-of-the-week", 6), (None, 1))):
        video = VideoVersion(script_id=awaiting_video.script_id, topic_id=awaiting_video.topic_id, status="PUBLISHED", output_dir="x", features_json={"series_id": series} if series else {})
        db.add(video)
        db.flush()
        publication = Publication(video_version_id=video.id, platform="youtube", account="a", idempotency_key=f"series{index}", status="PUBLISHED", published_at=NOW - timedelta(days=7))
        db.add(publication)
        db.flush()
        for name, value in {"views": 1000, "subscribersGained": subs, "subscribersLost": 0}.items():
            db.add(MetricSnapshot(publication_id=publication.id, collected_at=NOW, metric_definition_version="t", metric_name=name, metric_value=value, is_demo=False))
    db.commit()
    report = {row["series"]: row for row in audience.series_report(db)}
    assert report["hidden-gem-of-the-week"]["n"] == 2 and report["hidden-gem-of-the-week"]["median"] == 5
    assert report["no_series"]["n"] == 1


def test_plan_derivatives_writes_one_plan_per_variant_without_overwriting(tmp_path):
    packet = {"variants": [{"id": "v-shorts"}, {"id": "v-tiktok"}]}
    (tmp_path / "editorial-packet.json").write_text(json.dumps(packet))
    (tmp_path / "plan.json").write_text(json.dumps({"platform": "youtube", "scenes": []}))
    written = audience.plan_derivatives(tmp_path / "plan.json")
    assert sorted(path.name for path in written) == ["plan-v-shorts.json", "plan-v-tiktok.json"]
    assert json.loads((tmp_path / "plan-v-tiktok.json").read_text())["packet_variant_id"] == "v-tiktok"
    assert audience.plan_derivatives(tmp_path / "plan.json") == []


def test_packet_variant_selects_its_own_segments():
    from app.pipeline.ai import packet_narration

    packet = {"segments": [{"id": "S01", "voiceover": "One."}, {"id": "S02", "voiceover": "Two."}, {"id": "S03", "voiceover": "Three."}], "variants": [{"id": "v-cut", "segment_ids": ["S01", "S03"]}]}
    assert packet_narration(packet) == "One. Two. Three."
    assert packet_narration(packet, "v-cut") == "One. Three."


def test_comments_are_fetched_without_authors_and_questions_become_suggestions(db, awaiting_video, monkeypatch):
    monkeypatch.setattr(get_settings(), "youtube_api_key", "api-key")
    publication = Publication(video_version_id=awaiting_video.id, platform="youtube", account="a", idempotency_key="cm", status="PUBLISHED", published_at=NOW - timedelta(days=2), remote_id="vid1")
    db.add(publication)
    db.commit()
    items = [{"snippet": {"topLevelComment": {"id": f"c{index}", "snippet": {"textOriginal": text, "likeCount": likes, "authorDisplayName": "Private Person", "authorChannelId": {"value": "UCsecret"}, "publishedAt": NOW.isoformat()}}}} for index, (text, likes) in enumerate([("Does the Steam Deck run this at 60fps?", 9), ("What about the Steam Deck OLED?", 4), ("Steam Deck battery life?", 3), ("Great video", 1)])]
    monkeypatch.setattr(audience.httpx, "get", lambda url, params, timeout: SimpleNamespace(status_code=200, json=lambda: {"items": items}, raise_for_status=lambda: None))
    assert audience.fetch_youtube_comments(db, publication) == 4
    assert audience.fetch_youtube_comments(db, publication) == 0
    stored = db.query(VideoComment).all()
    assert all("Private Person" not in json.dumps(row.text) for row in stored)
    assert not hasattr(VideoComment, "author")
    insights = audience.comment_insights(db)
    assert insights["questions"] == 3 and insights["top_questions"][0]["likes"] == 9
    created = audience.suggestions_from_comments(db)
    assert any(item.query in {"steam", "deck"} for item in created)
    assert db.query(IdeaSuggestion).filter(IdeaSuggestion.title.like("Viewer FAQ:%")).count() == len(created)


def test_manual_test_and_compare_result_needs_evidence(db):
    spec = ExperimentSpec.model_validate({"name": "Thumbnail test", "hypothesis": "A close-up thumbnail earns more watch time share than a wide shot.", "variable": "thumbnail_type", "variants": [{"id": "wide", "value": "wide"}, {"id": "close", "value": "close"}], "primary_metric": "views", "guardrails": [], "rollback": "Keep wide thumbnails as default."})
    experiment = create_experiment(db, spec)
    with pytest.raises(ValueError, match="evidence_required"):
        audience.record_manual_result(db, experiment.id, "close", "")
    with pytest.raises(ValueError, match="unknown_variant"):
        audience.record_manual_result(db, experiment.id, "huge", "Studio showed a clear winner.")
    done = audience.record_manual_result(db, experiment.id, "close", "Studio Test & Compare: close won with 54 % watch time share.")
    assert done.status == "COMPLETED" and done.decision == "manual_winner:close"
    assert done.results_json["manual"]["source"].startswith("YouTube Studio")


def test_sources_comment_lists_unique_https_sources(tmp_path):
    (tmp_path / "claims.json").write_text(json.dumps([{"source_url": "https://store.steampowered.com/app/1"}, {"source_url": "https://store.steampowered.com/app/1"}, {"source_url": "http://insecure.example"}, {"source_url": "https://www.mobygames.com/game/1/x/"}]))
    text = audience.sources_comment(SimpleNamespace(output_dir=str(tmp_path)))
    assert text.count("https://") == 2 and "insecure" not in text
    assert audience.sources_comment(SimpleNamespace(output_dir=str(tmp_path / "missing"))) == ""
