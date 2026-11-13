import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.db.models import AuditEvent, MetricSnapshot, Publication, Review, Setting, VideoVersion
from app.pipeline import governance
from app.pipeline.experiments import ExperimentSpec, allocation_report, assign_variant, create_experiment, evaluate_experiment, spec_hash, stop_experiment, verify_assignment
from app.pipeline.metrics import collect_youtube_retention, retention_summary

NOW = datetime.now(timezone.utc)


def _video(db, base, hook="question", features=None, duration=30.0, output_dir=None):
    video = VideoVersion(script_id=base.script_id, topic_id=base.topic_id, status="PUBLISHED", output_dir=output_dir or base.output_dir, hook_type=hook, duration_seconds=duration, features_json={"is_demo": False, **(features or {})})
    db.add(video)
    db.flush()
    return video


def _publish(db, video, metrics, key, published_at, platform="youtube", remote_id=None):
    publication = Publication(video_version_id=video.id, platform=platform, account="acct", idempotency_key=key, status="PUBLISHED", published_at=published_at, remote_id=remote_id)
    db.add(publication)
    db.flush()
    for name, value in metrics.items():
        db.add(MetricSnapshot(publication_id=publication.id, collected_at=published_at + timedelta(days=7), metric_definition_version="t", metric_name=name, metric_value=value, is_demo=False))
    return publication


# --- retention -------------------------------------------------------------

def test_retention_summary_measures_hook_after_the_brand_intro_and_scene_drops():
    # 20 s video: watch ratio falls linearly from 1.0 to 0.0
    points = [(step / 100, 1 - step / 100) for step in range(1, 101)]
    scenes = [{"scene_id": "scene-1", "asset_id": 7, "start_ms": 0, "end_ms": 5000}, {"scene_id": "scene-2", "asset_id": 8, "start_ms": 5000, "end_ms": 10000}]
    summary = retention_summary(points, 20.0, intro_seconds=3.5, scenes=scenes)
    assert summary["retentionAt3s"] == pytest.approx(0.85, abs=0.01)
    assert summary["introRetention"] == pytest.approx(0.825 / 0.99, abs=0.01)
    assert summary["hookRetention3s"] == pytest.approx(0.675 / 0.825, abs=0.01)
    assert [row["scene_id"] for row in summary["scenes"]] == ["scene-1", "scene-2"]
    assert summary["scenes"][0]["start_seconds"] == 3.5
    assert summary["scenes"][0]["drop_per_second"] == pytest.approx(0.05, abs=0.001)


def test_collect_youtube_retention_stores_signals_and_curve(db, awaiting_video, tmp_path, monkeypatch):
    from app.config import get_settings

    for field in ("youtube_client_id", "youtube_client_secret", "youtube_refresh_token"):
        monkeypatch.setattr(get_settings(), field, "configured")
    (tmp_path / "clip_plan.json").write_text(json.dumps({"scenes": [{"scene_id": "scene-1", "asset_id": None, "start_ms": 0, "end_ms": 4000}]}))
    video = _video(db, awaiting_video, features={"intro_seconds": 3.5}, duration=20.0, output_dir=str(tmp_path))
    publication = _publish(db, video, {}, "ret", NOW - timedelta(days=8), remote_id="abc123")
    db.commit()
    captured = {}

    def fake_get(url, headers, params, timeout):
        captured.update(params)
        rows = [[step / 100, 1 - step / 200, 0.6] for step in range(1, 101)]
        return SimpleNamespace(status_code=200, json=lambda: {"rows": rows}, raise_for_status=lambda: None)

    monkeypatch.setattr("app.pipeline.metrics._youtube_access_token", lambda: "token")
    monkeypatch.setattr("app.pipeline.metrics.httpx.get", fake_get)
    assert collect_youtube_retention(db, publication) == 7
    assert captured["dimensions"] == "elapsedVideoTimeRatio"
    assert captured["filters"] == "video==abc123"
    names = {row.metric_name for row in db.query(MetricSnapshot).filter_by(publication_id=publication.id)}
    assert {"retentionAt1s", "retentionAt3s", "retentionAt5s", "introRetention", "hookRetention3s", "relativeRetentionMedian", "retentionCurve"} == names
    curve = db.query(MetricSnapshot).filter_by(metric_name="retentionCurve").one()
    assert len(curve.features_json["points"]) == 100 and curve.features_json["scenes"][0]["scene_id"] == "scene-1"


# --- experiments -----------------------------------------------------------

def _spec(**overrides):
    payload = {"name": "Opening hook test", "hypothesis": "A question opening keeps more viewers past the intro than a bold claim.", "variable": "hook_type", "variants": [{"id": "control", "value": "bold_claim"}, {"id": "question", "value": "question"}], "primary_metric": "hook_retention_3s", "guardrails": ["retention_pct"], "min_samples_per_variant": 3, "rollback": "Keep bold_claim openings as the default."}
    payload.update(overrides)
    return ExperimentSpec.model_validate(payload)


def test_experiment_spec_enforces_one_variable_and_taxonomy():
    with pytest.raises(ValueError):
        _spec(variants=[{"id": "a", "value": "question"}, {"id": "b", "value": "question"}])
    with pytest.raises(ValueError):
        _spec(variants=[{"id": "a", "value": "question"}, {"id": "b", "value": "vibes"}])
    with pytest.raises(ValueError):
        _spec(guardrails=["hook_retention_3s"])


def test_registration_is_hashed_immutable_and_one_per_variable(db):
    experiment = create_experiment(db, _spec())
    assert experiment.spec_sha256 == spec_hash(_spec())
    with pytest.raises(ValueError, match="active_experiment_already_tests"):
        create_experiment(db, _spec(name="Second hook test"))
    experiment.spec_json = {**experiment.spec_json, "min_samples_per_variant": 50}
    db.commit()
    with pytest.raises(ValueError, match="spec_changed"):
        assign_variant(db, experiment.id, "story-x")


def test_assignment_is_balanced_stable_and_verified_at_production(db):
    experiment = create_experiment(db, _spec())
    assigned = [assign_variant(db, experiment.id, f"story-{index}")["variant_id"] for index in range(6)]
    assert assigned.count("control") == assigned.count("question") == 3
    assert assign_variant(db, experiment.id, "story-0")["variant_id"] == assigned[0]
    variant = assigned[0]
    value = "bold_claim" if variant == "control" else "question"
    marker = verify_assignment(db, experiment.id, variant, "story-0", {"hook_type": value, "platform": "youtube"})
    assert marker["verified"] and marker["spec_sha256"] == experiment.spec_sha256
    wrong = "question" if variant == "control" else "control"
    with pytest.raises(ValueError, match="variant_mismatch"):
        verify_assignment(db, experiment.id, wrong, "story-0", {"hook_type": value})
    with pytest.raises(ValueError, match="variable_not_applied"):
        verify_assignment(db, experiment.id, variant, "story-0", {"hook_type": "story"})
    with pytest.raises(ValueError, match="not_assigned"):
        verify_assignment(db, experiment.id, variant, "unknown-story", {"hook_type": value})


def _experiment_publications(db, base, experiment, control_values, treatment_values, guardrail=(60, 60)):
    for variant_id, values, retention in (("control", control_values, guardrail[0]), ("question", treatment_values, guardrail[1])):
        for index, value in enumerate(values):
            video = _video(db, base, features={"experiment": {"experiment_id": experiment.id, "variant_id": variant_id}})
            _publish(db, video, {"views": 1000, "hookRetention3s": value, "averageViewPercentage": retention}, f"{variant_id}-{index}-{db.query(Publication).count()}", NOW - timedelta(days=8))
    db.commit()


def test_evaluation_waits_for_samples_then_recommends_without_adopting(db, awaiting_video):
    experiment = create_experiment(db, _spec())
    _experiment_publications(db, awaiting_video, experiment, [0.50, 0.52], [0.70, 0.72])
    assert evaluate_experiment(db, experiment.id)["decision"] == "running"
    _experiment_publications(db, awaiting_video, experiment, [0.51, 0.49, 0.50], [0.71, 0.73, 0.69])
    result = evaluate_experiment(db, experiment.id)
    assert result["decision"] == "winner:question"
    assert result["adoption"] == "owner_decision_required"
    assert result["rollback"] == "Keep bold_claim openings as the default."
    assert db.get(type(experiment), experiment.id).status == "COMPLETED"
    assert db.query(AuditEvent).filter_by(action="EXPERIMENT_COMPLETED").count() == 1


def test_guardrail_blocks_a_winner_that_hurts_retention(db, awaiting_video):
    experiment = create_experiment(db, _spec())
    _experiment_publications(db, awaiting_video, experiment, [0.5] * 4, [0.7] * 4, guardrail=(60, 40))
    assert evaluate_experiment(db, experiment.id)["decision"] == "winner_blocked_by_guardrail:question"


def test_no_difference_and_owner_stop(db, awaiting_video):
    experiment = create_experiment(db, _spec())
    _experiment_publications(db, awaiting_video, experiment, [0.5, 0.6, 0.55], [0.55, 0.5, 0.6])
    assert evaluate_experiment(db, experiment.id)["decision"] == "no_detectable_difference"
    second = create_experiment(db, _spec(name="CTA test", variable="cta_type", variants=[{"id": "control", "value": "follow"}, {"id": "save", "value": "save"}]))
    with pytest.raises(ValueError, match="stop_reason_required"):
        stop_experiment(db, second.id, "")
    assert stop_experiment(db, second.id, "Footage unavailable").status == "STOPPED"


def test_allocation_report_flags_exploration_over_twenty_percent(db, awaiting_video):
    for index in range(10):
        features = {"experiment": {"experiment_id": 1, "is_pilot": False}} if index < 4 else {}
        _video(db, awaiting_video, features=features)
    db.commit()
    report = allocation_report(db)
    assert report["experimental"] == 4 and report["over_budget"] is True
    for video in db.query(VideoVersion).all():
        if video.features_json.get("experiment"):
            video.features_json = {**video.features_json, "experiment": {"experiment_id": 1, "is_pilot": True}}
    db.commit()
    assert allocation_report(db)["over_budget"] is False


# --- governance ------------------------------------------------------------

def _week(offset):
    start = governance._week_start(NOW) - timedelta(weeks=offset)
    return start + timedelta(days=1)


def _weekly_primary(db, base, values_by_offset, retention=60):
    for offset, value in values_by_offset.items():
        for index in range(2):
            video = _video(db, base)
            _publish(db, video, {"views": 1000, "subscribersGained": value, "subscribersLost": 0, "averageViewPercentage": retention}, f"w{offset}-{index}-{value}", _week(offset))
    db.commit()


def _model(version, multipliers=None):
    return {"version": version, "hook_multipliers": multipliers or {"question": 1.1}, "data_mode": "real"}


def test_candidate_runs_in_shadow_before_activation(db, awaiting_video):
    _weekly_primary(db, awaiting_video, {3: 5, 2: 5, 1: 5})
    first = governance.weekly_step(db, _model(1), NOW)
    assert first["active_version"] is None and first["candidate_version"] == 1
    assert governance.active_learning_model(db) is None
    second = governance.weekly_step(db, _model(2), NOW + timedelta(days=7))
    assert second["active_version"] == 1 and second["candidate_version"] == 2
    assert governance.active_learning_model(db)["model"]["hook_multipliers"] == {"question": 1.1}


def test_guardrail_breach_blocks_promotion(db, awaiting_video):
    _weekly_primary(db, awaiting_video, {4: 5, 3: 5, 2: 5}, retention=60)
    _weekly_primary(db, awaiting_video, {1: 5}, retention=30)
    governance.weekly_step(db, _model(1), NOW - timedelta(days=7))
    result = governance.weekly_step(db, _model(2), NOW)
    assert "retention_pct" in result["guardrail_breaches"]
    assert result["active_version"] is None
    assert db.query(AuditEvent).filter_by(action="LEARNING_MODEL_PROMOTION_BLOCKED").count() == 1


def test_two_consecutive_weekly_declines_roll_back(db, awaiting_video):
    state = {"active": {"version": 2, "model": _model(2), "activated_at": (_week(3) - timedelta(days=1)).isoformat()}, "candidate": None, "history": [{"version": 1, "model": _model(1), "activated_at": (NOW - timedelta(weeks=8)).isoformat()}], "events": []}
    db.merge(Setting(key=governance.GOVERNANCE_KEY, value_json=state))
    _weekly_primary(db, awaiting_video, {4: 9, 3: 9, 2: 6, 1: 3})
    result = governance.weekly_step(db, _model(3), NOW)
    assert result["rolled_back"] is True
    assert governance.active_learning_model(db)["version"] == 1
    assert db.query(AuditEvent).filter_by(action="LEARNING_MODEL_ROLLED_BACK").count() == 1


def test_first_pass_approval_rate_counts_only_first_decision(db, awaiting_video):
    second = _video(db, awaiting_video)
    db.add_all([
        Review(video_version_id=awaiting_video.id, decision="REJECTED", reviewer="owner", created_at=NOW - timedelta(hours=3)),
        Review(video_version_id=awaiting_video.id, decision="APPROVED", reviewer="owner", created_at=NOW - timedelta(hours=2)),
        Review(video_version_id=second.id, decision="APPROVED", reviewer="owner", created_at=NOW - timedelta(hours=1)),
    ])
    db.commit()
    assert governance.first_pass_approval_rate(db, NOW - timedelta(days=1), NOW + timedelta(hours=1)) == {"n": 2, "rate": 0.5}


def test_prompt_guidance_uses_only_the_active_model(db, monkeypatch):
    from app.db.models import Topic
    from app.pipeline import ai

    db.merge(Setting(key="learning_model", value_json=_model(9, {"story": 1.2})))
    db.merge(Setting(key=governance.GOVERNANCE_KEY, value_json={"active": {"version": 4, "model": _model(4, {"question": 1.1}), "activated_at": NOW.isoformat()}, "candidate": None, "history": [], "events": []}))
    db.commit()
    prompts = []
    monkeypatch.setattr(ai, "_call_json", lambda _db, model_class, prompt, *_args, **_kwargs: prompts.append(prompt) or ai.ScriptDraft(title="t", narration="x" * 30, hook_type="question", post_text="p"))
    topic = Topic(niche="gaming", language="en", title="Topic")
    db.add(topic)
    db.commit()
    ai.claude_draft(db, topic, [], "job")
    assert '"question": 1.1' in prompts[0] and "story" not in prompts[0].split("Evidence-derived")[1]
    assert ai.current_prompt_version(db).endswith("learning-v4")


def test_cli_experiment_lifecycle_and_scorecard(db, tmp_path):
    from app.cli import build_parser, run_extended

    spec_path = tmp_path / "spec.json"
    spec_path.write_text(_spec().model_dump_json())
    created = run_extended(db, build_parser().parse_args(["experiment", "create", "--spec", str(spec_path)]))
    assigned = run_extended(db, build_parser().parse_args(["experiment", "assign", "--id", str(created["experiment_id"]), "--story", "ITB-1"]))
    assert assigned["variable"] == "hook_type"
    listed = run_extended(db, build_parser().parse_args(["experiment", "list"]))
    assert listed["experiments"][0]["status"] == "ACTIVE"
    card = run_extended(db, build_parser().parse_args(["scorecard"]))
    assert len(card["scorecard"]) == governance.WEEKS and card["active_version"] is None
    assert run_extended(db, build_parser().parse_args(["doctor"])) is None
