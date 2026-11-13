from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db.models import MetricSnapshot, Publication, Setting, VideoVersion
from app.pipeline.learning import MULTIPLIER_CEILING, MULTIPLIER_FLOOR, weekly_learning

NOW = datetime.now(timezone.utc)


def _video(db, base, hook):
    video = VideoVersion(script_id=base.script_id, topic_id=base.topic_id, status="PUBLISHED", output_dir=base.output_dir, hook_type=hook, format="vertical_explainer", duration_seconds=30, features_json={"is_demo": True})
    db.add(video)
    db.flush()
    return video


def _publish(db, video, metrics, key, age_days=7.0, platform="youtube"):
    publication = Publication(video_version_id=video.id, platform=platform, account="demo", idempotency_key=key, status="PUBLISHED", published_at=NOW - timedelta(days=age_days))
    db.add(publication)
    db.flush()
    for name, value in metrics.items():
        db.add(MetricSnapshot(publication_id=publication.id, collected_at=NOW, metric_definition_version="test-v1", metric_name=name, metric_value=value, is_demo=True))
    return publication


def _old_views_formula(group_median, overall_median, n):
    target = 1 + (group_median / overall_median - 1) * (n / (n + 5))
    return round(max(0.75, min(1.25, target)), 4)


def _model(db):
    return db.get(Setting, "learning_model_demo").value_json


def test_views_only_matches_previous_damped_formula(db, awaiting_video):
    a, b = _video(db, awaiting_video, "question"), _video(db, awaiting_video, "comparison")
    for index, views in enumerate((100, 120)):
        _publish(db, a, {"views": views}, f"a{index}")
    for index, views in enumerate((300, 340)):
        _publish(db, b, {"views": views}, f"b{index}")
    db.commit()
    report = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    multipliers = _model(db)["hook_multipliers"]
    assert multipliers["question"] == _old_views_formula(110, 210, 2)
    assert multipliers["comparison"] == _old_views_formula(320, 210, 2)
    assert {update["hook"]: update["groups"][0]["weights_used"] for update in report["model_updates"]} == {"question": {"views": 1.0}, "comparison": {"views": 1.0}}


def test_retention_and_subscribers_can_outweigh_views(db, awaiting_video):
    loud, loyal = _video(db, awaiting_video, "bold_claim"), _video(db, awaiting_video, "story")
    for index in range(4):
        _publish(db, loud, {"views": 1000, "averageViewPercentage": 30, "averageViewDuration": 9, "likes": 10, "comments": 1, "shares": 1, "subscribersGained": 1, "subscribersLost": 1}, f"loud{index}")
        _publish(db, loyal, {"views": 700, "averageViewPercentage": 75, "averageViewDuration": 22, "likes": 40, "comments": 8, "shares": 6, "subscribersGained": 9, "subscribersLost": 1}, f"loyal{index}")
    db.commit()
    report = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    multipliers = _model(db)["hook_multipliers"]
    assert multipliers["story"] > 1 > multipliers["bold_claim"]
    story = next(update for update in report["model_updates"] if update["hook"] == "story")["groups"][0]
    assert story["signals"]["views"]["damped"] < 1
    assert set(story["signals"]) == {"views", "retention_pct", "watch_seconds_per_view", "engagement_per_1k_views", "net_subscribers_per_1k_views"}
    assert abs(sum(story["weights_used"].values()) - 1) < 1e-3
    assert report["signal_weights"]["version"] == "learning-signals-v1"


def test_one_sample_per_publication_closest_to_day_seven(db, awaiting_video):
    video = _video(db, awaiting_video, "surprising_fact")
    publication = _publish(db, video, {"views": 100}, "dedup")
    db.add(MetricSnapshot(publication_id=publication.id, collected_at=NOW - timedelta(hours=10), metric_definition_version="test-v1", metric_name="views", metric_value=90, is_demo=True))
    db.add(MetricSnapshot(publication_id=publication.id, collected_at=NOW - timedelta(days=4), metric_definition_version="test-v1", metric_name="views", metric_value=40, is_demo=True))
    _publish(db, video, {"views": 200}, "other")
    db.commit()
    report = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    views = report["observed"][0]["signals"]["views"]
    assert views["sample_size"] == 2
    assert views["min"] == 100 and views["max"] == 200


def test_sparse_signals_are_skipped_and_weights_renormalised(db, awaiting_video):
    a, b = _video(db, awaiting_video, "question"), _video(db, awaiting_video, "challenge")
    _publish(db, a, {"views": 100, "averageViewPercentage": 40}, "a0")
    _publish(db, a, {"views": 120}, "a1")
    _publish(db, b, {"views": 300, "averageViewPercentage": 60}, "b0")
    _publish(db, b, {"views": 320, "averageViewPercentage": 70}, "b1")
    db.commit()
    report = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    updates = {update["hook"]: update["groups"][0] for update in report["model_updates"]}
    assert set(updates["question"]["signals"]) == {"views"}
    assert set(updates["challenge"]["signals"]) == {"views", "retention_pct"}
    assert updates["challenge"]["weights_used"] == {"views": round(0.30 / 0.55, 4), "retention_pct": round(0.25 / 0.55, 4)}


def test_extreme_and_non_positive_values_stay_bounded(db, awaiting_video):
    a, b = _video(db, awaiting_video, "question"), _video(db, awaiting_video, "challenge")
    for index in range(30):
        _publish(db, a, {"views": 1, "averageViewPercentage": 1, "subscribersGained": 0, "subscribersLost": 0}, f"a{index}")
        _publish(db, b, {"views": 1_000_000, "averageViewPercentage": 99, "subscribersGained": 0, "subscribersLost": 0}, f"b{index}")
    db.commit()
    report = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    for update in report["model_updates"]:
        assert MULTIPLIER_FLOOR <= update["multiplier"] <= MULTIPLIER_CEILING
        assert all("net_subscribers_per_1k_views" not in group["signals"] for group in update["groups"])


def test_platform_aliases_and_publications_outside_window(db, awaiting_video):
    video = _video(db, awaiting_video, "story")
    _publish(db, video, {"views": 500, "follows": 5}, "r0", platform="instagram")
    _publish(db, video, {"views": 400, "followers_gained": 2}, "r1", platform="instagram")
    _publish(db, video, {"views": 9999, "follows": 99}, "late", age_days=20, platform="instagram")
    db.commit()
    report = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    row = report["observed"][0]
    assert row["group"].startswith("instagram|")
    assert row["signals"]["views"]["sample_size"] == 2
    assert row["signals"]["net_subscribers_per_1k_views"]["median"] == 7.5
    markdown = Path(report["files"]["markdown"]).read_text(encoding="utf-8")
    assert "net_subscribers_per_1k_views" in markdown and "## Model updates" in markdown
    assert report["model_updates"] == []
    assert report["groups_without_comparable_hook"] == [row["group"]]


def test_hook_multiplier_pools_all_cohorts_instead_of_last_group(db, awaiting_video):
    q, other = _video(db, awaiting_video, "question"), _video(db, awaiting_video, "comparison")
    for index, views in enumerate((300, 320, 340, 360)):
        _publish(db, q, {"views": views}, f"yt-q{index}")
    for index, views in enumerate((100, 120, 140, 160)):
        _publish(db, other, {"views": views}, f"yt-l{index}")
    for index, views in enumerate((50, 60)):
        _publish(db, q, {"views": views}, f"ig-q{index}", platform="instagram")
    for index, views in enumerate((100, 120)):
        _publish(db, other, {"views": views}, f"ig-l{index}", platform="instagram")
    db.commit()
    report = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    question = next(update for update in report["model_updates"] if update["hook"] == "question")
    by_platform = {group["group"].split("|")[0]: group for group in question["groups"]}
    assert set(by_platform) == {"youtube", "instagram"}
    assert by_platform["youtube"]["multiplier"] > 1 > by_platform["instagram"]["multiplier"]
    expected = (by_platform["youtube"]["multiplier"] ** 4 * by_platform["instagram"]["multiplier"] ** 2) ** (1 / 6)
    assert question["sample_size"] == 6
    assert abs(question["multiplier"] - expected) < 1e-3
    assert _model(db)["hook_multipliers"]["question"] == question["multiplier"]


def test_platform_reach_differences_are_not_credited_to_hooks(db, awaiting_video):
    a, b = _video(db, awaiting_video, "question"), _video(db, awaiting_video, "challenge")
    for index in range(3):
        _publish(db, a, {"views": 10_000}, f"yt-a{index}")
        _publish(db, b, {"views": 10_000}, f"yt-b{index}")
        _publish(db, b, {"views": 100}, f"tt-b{index}", platform="tiktok")
    db.commit()
    report = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    multipliers = _model(db)["hook_multipliers"]
    assert multipliers["question"] == 1.0 and multipliers["challenge"] == 1.0
    assert report["cohort_medians"]["youtube|vertical_explainer|short"]["views"] == 10_000
    assert any(group.startswith("tiktok|") for group in report["groups_without_comparable_hook"])
