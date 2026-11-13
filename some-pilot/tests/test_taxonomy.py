import pytest
from pydantic import ValidationError

from app.pipeline.ai import PostPackaging, ScriptDraft
from app.pipeline.taxonomy import HOOK_TYPES, detect_cta, normalize_hook


def test_hook_variants_collapse_to_one_controlled_value():
    assert normalize_hook("question") == normalize_hook("Question hook") == normalize_hook("curiosity_question") == "question"
    assert normalize_hook("Top 10") == "ranking_reveal"
    assert len(HOOK_TYPES) == 8


def test_unknown_hook_is_rejected_for_new_scripts_but_bucketed_for_legacy_rows():
    with pytest.raises(ValueError):
        normalize_hook("vibes")
    assert normalize_hook("vibes", strict=False) == "other"
    with pytest.raises(ValidationError):
        ScriptDraft(title="t", narration="x" * 30, hook_type="vibes", post_text="p")
    assert PostPackaging(title="Title", post_text="p", hook_type="Bold Claim").hook_type == "bold_claim"


def test_cta_detection_is_controlled():
    assert detect_cta("Follow for more handheld tests") == "follow"
    assert detect_cta("Save this checklist") == "save"
    assert detect_cta("Plain caption") == "none"
