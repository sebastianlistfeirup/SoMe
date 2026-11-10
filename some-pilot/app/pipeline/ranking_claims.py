import re


RANK_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}


def ranking_claim_control(plan) -> dict:
    issues = []
    checked_names = []
    checked_ranks = []
    normalized_names = [scene.game.strip().casefold() for scene in plan.scenes]
    if len(set(normalized_names)) != 10:
        issues.append("game_names_must_be_unique")
    for scene in sorted(plan.scenes, key=lambda item: item.rank):
        checked_names.append(scene.game)
        checked_ranks.append({"rank": scene.rank, "game": scene.game})
        expected = RANK_WORDS[scene.rank]
        narration = scene.narration.casefold()
        if not re.search(rf"\b(?:number|at number)\s+{expected}\b", narration):
            issues.append(f"narration_rank_mismatch:{scene.rank}:{scene.game}")

    post = plan.post_text.casefold()
    if "editorial ranking" not in post:
        issues.append("subjective_ranking_disclosure_missing")
    if "not an fps benchmark" not in post:
        issues.append("performance_test_disclosure_missing")

    full_text = "\n".join([plan.title, plan.hook, plan.post_text, *[scene.narration for scene in plan.scenes]]).casefold()
    performance_text = full_text.replace("not an fps benchmark", "")
    prohibited = {
        "fps": r"\bfps\b|frames per second",
        "battery": r"battery life|hours? of battery",
        "benchmark": r"\bbenchmark(?:ed|ing|s)?\b",
        "first_party_test": r"\bwe (?:tested|measured|benchmarked)\b",
    }
    for label, pattern in prohibited.items():
        if re.search(pattern, performance_text):
            issues.append(f"unsupported_performance_claim:{label}")

    claim_rows = [claim.model_dump(mode="json") for claim in plan.claims]
    for claim in plan.claims:
        if not claim.verified:
            issues.append(f"claim_not_verified:{claim.id}")
        if not claim.evidence_note.strip():
            issues.append(f"claim_evidence_note_missing:{claim.id}")
        if not claim.verified_at:
            issues.append(f"claim_verification_date_missing:{claim.id}")
        if claim.game and claim.game.casefold() not in normalized_names:
            issues.append(f"claim_game_not_in_ranking:{claim.id}")

    hades_scene = next((scene for scene in plan.scenes if scene.game.casefold() == "hades ii"), None)
    if hades_scene and "steam deck verified" in hades_scene.narration.casefold():
        evidence = [claim for claim in plan.claims if claim.game and claim.game.casefold() == "hades ii" and "steam deck verified" in claim.text.casefold()]
        if not evidence:
            issues.append("hades_ii_deck_verified_evidence_missing")

    return {
        "decision": "ALLOW" if not issues else "BLOCK",
        "issues": issues,
        "mode": "structured_human_reviewed_ranking",
        "checked_game_names": checked_names,
        "checked_rank_order": checked_ranks,
        "subjective_ranking_disclosed": "editorial ranking" in post,
        "performance_test_disclosed": "not an fps benchmark" in post,
        "claims": claim_rows,
    }
