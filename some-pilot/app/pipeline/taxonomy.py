"""Controlled vocabularies used by production features and learning.

Free-text labels fragment learning groups ("question", "Question hook" and
"curiosity_question" would be three samples of one idea), so every stored hook
and CTA is normalised to one of these values.
"""

import re

HOOK_TYPES = (
    "question",
    "bold_claim",
    "surprising_fact",
    "ranking_reveal",
    "challenge",
    "story",
    "comparison",
    "practical_checklist",
)

HOOK_ALIASES = {
    "curiosity_question": "question",
    "curiosity": "question",
    "rhetorical_question": "question",
    "claim": "bold_claim",
    "hot_take": "bold_claim",
    "statement": "bold_claim",
    "fact": "surprising_fact",
    "did_you_know": "surprising_fact",
    "stat": "surprising_fact",
    "statistic": "surprising_fact",
    "ranking": "ranking_reveal",
    "countdown": "ranking_reveal",
    "top_10": "ranking_reveal",
    "top10": "ranking_reveal",
    "test": "challenge",
    "dare": "challenge",
    "narrative": "story",
    "anecdote": "story",
    "versus": "comparison",
    "vs": "comparison",
    "checklist": "practical_checklist",
    "how_to": "practical_checklist",
    "tips": "practical_checklist",
    "buying_guide": "practical_checklist",
}

LEGACY_HOOK = "other"

CTA_TYPES = ("follow", "save", "comment", "share", "watch_next", "none")


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return re.sub(r"_hook$", "", value)


def normalize_hook(value: str | None, strict: bool = True) -> str:
    """Map a label to the controlled hook vocabulary.

    strict=True raises for unknown values (new production data); strict=False maps
    unknown legacy values to "other" so old rows never create ad-hoc groups.
    """
    slug = _slug(value or "")
    if slug in HOOK_TYPES:
        return slug
    if slug in HOOK_ALIASES:
        return HOOK_ALIASES[slug]
    if strict:
        raise ValueError(f"hook_type_not_in_taxonomy:{value}")
    return LEGACY_HOOK


def detect_cta(text: str) -> str:
    lowered = text.casefold()
    for cta, words in (("follow", ("follow", "subscribe")), ("save", ("save this", "save it", "bookmark")), ("comment", ("comment", "tell me", "let me know")), ("share", ("share",)), ("watch_next", ("watch next", "part 2", "next video"))):
        if any(word in lowered for word in words):
            return cta
    return "none"
