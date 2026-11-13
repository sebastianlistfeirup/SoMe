import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.pipeline.experiments import ExperimentSpec, create_experiment, experiment_markers, verify_rendered_variant
from app.pipeline.owner_workflow import OWNER_STEPS, load_publisher_policies, log_owner_time, owner_time_report, prefill_packet, publisher_policy_blockers, write_prefilled_packet

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc)


def test_prefilled_packet_is_schema_valid_and_contains_no_facts():
    schema = json.loads((ROOT / "content" / "schemas" / "packet.schema.json").read_text(encoding="utf-8"))
    packet = prefill_packet("GI001", NOW)
    errors = sorted(Draft202012Validator(schema).iter_errors(packet), key=lambda error: error.path)
    assert not errors, [error.message for error in errors]
    assert packet["state"] == "needs_evidence"
    assert packet["sources"] == [] and packet["claims"] == [] and packet["games"] == []
    assert any("MobyGames" in blocker for blocker in packet["blockers"])
    assert packet["approval"]["owner_approved"] is False


def test_prefilled_packet_cannot_pass_the_production_gate():
    from app.pipeline.editorial import evaluate_editorial_packet

    packet = prefill_packet("GI001", NOW)
    result = evaluate_editorial_packet(packet, packet["segments"][0]["voiceover"], {name: 5 for name in ("viewer_promise", "opening", "evidence", "visual_match", "payoff", "platform_fit", "voice")})
    assert result["decision"] == "BLOCK"
    assert "editorial_packet_not_production_ready:needs_evidence" in result["blockers"]


def test_write_prefilled_packet_never_overwrites(tmp_path):
    path = write_prefilled_packet("GI002", tmp_path)
    assert path.is_file() and (path.parent / "CHECKLIST.md").is_file()
    with pytest.raises(ValueError, match="already_exists"):
        write_prefilled_packet("GI002", tmp_path)


def test_owner_time_report_finds_bottleneck(db):
    for story, step, minutes in (("s1", "mobygames", 40), ("s1", "footage_capture", 20), ("s2", "mobygames", 50), ("s2", "review_approval", 10)):
        log_owner_time(db, story, step, minutes)
    report = owner_time_report(db)
    assert report["stories"] == 2 and report["bottleneck_step"] == "mobygames"
    assert report["median_minutes_by_step"]["mobygames"] == 45
    assert "No scraping" in report["automation_hint"]
    with pytest.raises(ValueError):
        log_owner_time(db, "s3", "napping", 5)
    assert "rights_permissions" in OWNER_STEPS


def test_publisher_register_blocks_disallowed_unverified_and_stale_policies():
    policies = [
        {"publisher": "Allowed Games", "aliases": [], "video_use_allowed": True, "monetization_allowed": True, "verified_at": (NOW - timedelta(days=10)).isoformat(), "reverify_after_days": 180},
        {"publisher": "Stale Games", "aliases": [], "video_use_allowed": True, "monetization_allowed": True, "verified_at": (NOW - timedelta(days=400)).isoformat(), "reverify_after_days": 180},
        {"publisher": "Strict Games", "aliases": ["Strict"], "video_use_allowed": True, "monetization_allowed": False, "verified_at": NOW.isoformat()},
        {"publisher": "Unknown Status Games", "aliases": [], "video_use_allowed": None, "monetization_allowed": None, "verified_at": None},
    ]
    blockers = publisher_policy_blockers(["Allowed Games Ltd", "Stale Games", "Strict Interactive", "Unknown Status Games", "Not In Register"], NOW, policies)
    assert blockers == ["publisher_policy_reverify_required:Stale Games", "publisher_policy_disallows:Strict Games", "publisher_policy_unverified:Unknown Status Games"]


def test_real_register_is_well_formed_and_owner_verification_is_pending():
    policies = load_publisher_policies()
    assert {"Devolver Digital", "Nintendo"} <= {item["publisher"] for item in policies}
    assert all(item["policy_url"].startswith("https://") for item in policies)
    assert publisher_policy_blockers(["Devolver Digital"], NOW) == ["publisher_policy_unverified:Devolver Digital"]


def test_pilot_specs_are_valid_preregistrations_on_different_variables(db):
    specs = [ExperimentSpec.model_validate_json((ROOT / "content" / "pilot" / name).read_text(encoding="utf-8")) for name in ("pilot-hook.json", "pilot-length.json")]
    assert all(spec.is_pilot for spec in specs)
    assert {spec.variable for spec in specs} == {"hook_type", "duration_bucket"}
    created = [create_experiment(db, spec) for spec in specs]
    assert len(created) == 2


def test_multiple_experiment_markers_are_all_verified_after_render():
    features = {"duration_seconds": 50, "experiments": [{"experiment_id": 1, "variable": "hook_type", "value": "question"}, {"experiment_id": 2, "variable": "duration_bucket", "value": "medium"}]}
    assert len(experiment_markers(features)) == 2
    verify_rendered_variant(features)
    with pytest.raises(ValueError, match="duration_bucket"):
        verify_rendered_variant({**features, "duration_seconds": 20})


def test_every_decision_is_enforced_by_existing_tests():
    decisions = sorted((ROOT / "docs" / "decisions").glob("0*.md"))
    assert len(decisions) >= 10
    for path in decisions:
        text = path.read_text(encoding="utf-8")
        references = re.findall(r"`(tests/[\w/]+\.py)::(\w+)`", text)
        assert references, f"{path.name} names no enforcing test"
        for file_name, test_name in references:
            source = (ROOT / file_name).read_text(encoding="utf-8")
            assert re.search(rf"^def {test_name}\(", source, flags=re.MULTILINE), f"{path.name}: {file_name}::{test_name} is missing"


def test_status_report_is_generated_from_doctor(db, tmp_path):
    from app.pipeline.status_report import write_status

    result = write_status(db, 271, "local", tmp_path / "STATUS.generated.txt", commit="abc123")
    text = (tmp_path / "STATUS.generated.txt").read_text(encoding="utf-8")
    assert result["tests_passed"] == 271 and "271 bestået" in text and "commit: abc123" in text
    assert "DRY_RUN=" in text and "PUBLISH_ENABLED=" in text
