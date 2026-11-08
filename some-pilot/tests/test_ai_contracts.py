import pytest
from pydantic import ValidationError

from app.pipeline.ai import build_clip_plan
from app.pipeline.production import transcription_quality


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
