import json
from types import SimpleNamespace

import anthropic
import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.db.models import Cost, Topic
from app.pipeline.ai import ControlResult, _call_json, build_clip_plan, claude_draft, demo_draft, review_draft
from app.pipeline.production import transcription_quality


def configure_claude(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "paid_jobs_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-only-not-a-real-key")
    monkeypatch.setattr(settings, "claude_model_text", "claude-sonnet-5-5")
    monkeypatch.setattr(settings, "claude_model_research", "claude-haiku-5-5")
    monkeypatch.setattr(settings, "claude_input_dkk_per_million", 12.9)
    monkeypatch.setattr(settings, "claude_output_dkk_per_million", 64.5)
    monkeypatch.setattr(settings, "claude_research_input_dkk_per_million", 0.645)
    monkeypatch.setattr(settings, "claude_research_output_dkk_per_million", 3.225)
    return settings


def forbid_network(monkeypatch):
    def fail_if_called(**_kwargs):
        raise AssertionError("Anthropic must not be instantiated")

    monkeypatch.setattr(anthropic, "Anthropic", fail_if_called)


def test_clip_plan_validation_and_claim_allowlist():
    plan = build_clip_plan([{"start": 0, "end": 2, "text": "Safe segment", "claim_ids": ["known", "invented"]}], 1, 2, ["known"])
    assert plan.scenes[0].claim_ids == ["known"]
    with pytest.raises(ValidationError):
        build_clip_plan([{"start": 0, "end": 0, "text": "Invalid"}], 1, 1, [])


def test_transcription_quality_flags_changed_numbers():
    transcription = {"segments_detail": [{"text": "The price is 100 dollars"}], "language_probability": 0.99}
    result = transcription_quality("The price is 200 dollars", transcription)
    assert result["decision"] == "REVIEW"
    assert result["missing_numbers"] == ["200"]


def test_claude_routes_script_to_sonnet_and_review_to_haiku_with_separate_prices(db, monkeypatch):
    configure_claude(monkeypatch)
    topic = Topic(niche="test", language="en", title="Handheld gaming test")
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        payload = demo_draft(topic).model_dump() if kwargs["model"] == "claude-sonnet-5-5" else ControlResult(decision="ALLOW").model_dump()
        return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(payload))], usage=SimpleNamespace(input_tokens=1000, output_tokens=100))

    monkeypatch.setattr(anthropic, "Anthropic", lambda **_kwargs: SimpleNamespace(messages=SimpleNamespace(create=create)))
    db.add(topic)
    db.commit()
    sources = [{"source_url": "https://example.com/source", "text": "Verified source excerpt"}]

    draft = claude_draft(db, topic, sources, "script-route-test")
    result = review_draft(db, draft, sources, "review-route-test")

    assert result.decision == "ALLOW"
    assert [call["model"] for call in calls] == ["claude-sonnet-5-5", "claude-haiku-5-5"]
    costs = db.query(Cost).order_by(Cost.id).all()
    assert [cost.kind for cost in costs] == ["claude_script", "claude_claim_review"]
    assert costs[0].actual_amount == pytest.approx(0.01935)
    assert costs[1].actual_amount == pytest.approx(0.0009675)


@pytest.mark.parametrize("field", ["paid_jobs_enabled", "anthropic_api_key"])
def test_claude_blocks_before_network_when_disabled_or_key_is_missing(db, monkeypatch, field):
    configure_claude(monkeypatch)
    monkeypatch.setattr(get_settings(), field, False if field == "paid_jobs_enabled" else "")
    forbid_network(monkeypatch)

    with pytest.raises(RuntimeError, match="claude_not_configured_or_disabled"):
        _call_json(db, ControlResult, "Return JSON", f"blocked-{field}", "claude_test", 100)
    assert db.query(Cost).count() == 0


@pytest.mark.parametrize("field", ["claude_input_dkk_per_million", "claude_output_dkk_per_million"])
def test_claude_script_blocks_before_network_without_verified_prices(db, monkeypatch, field):
    configure_claude(monkeypatch)
    monkeypatch.setattr(get_settings(), field, 0)
    forbid_network(monkeypatch)

    with pytest.raises(RuntimeError, match="verified_model_pricing_required"):
        _call_json(db, ControlResult, "Return JSON", f"blocked-{field}", "claude_test", 100)
    assert db.query(Cost).count() == 0


@pytest.mark.parametrize("field", ["claude_research_input_dkk_per_million", "claude_research_output_dkk_per_million"])
def test_claude_research_blocks_before_network_without_verified_prices(db, monkeypatch, field):
    configure_claude(monkeypatch)
    monkeypatch.setattr(get_settings(), field, 0)
    forbid_network(monkeypatch)

    with pytest.raises(RuntimeError, match="verified_model_pricing_required"):
        _call_json(db, ControlResult, "Return JSON", f"blocked-{field}", "claude_test", 100, route="research")
    assert db.query(Cost).count() == 0


def test_claude_reads_text_after_thinking_block(db, monkeypatch):
    configure_claude(monkeypatch)
    reply = SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking="private reasoning"), SimpleNamespace(type="text", text=ControlResult(decision="ALLOW").model_dump_json())],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )
    monkeypatch.setattr(anthropic, "Anthropic", lambda **_kwargs: SimpleNamespace(messages=SimpleNamespace(create=lambda **_kwargs: reply)))

    result = _call_json(db, ControlResult, "Return JSON", "thinking-block-test", "claude_test", 100, route="research")

    assert result.decision == "ALLOW"
    cost = db.query(Cost).one()
    assert cost.status == "SETTLED"
    assert cost.actual_amount == pytest.approx(0.000129)
