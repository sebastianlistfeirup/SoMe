"""Owner-time measurement, a prefilled research packet and the publisher policy register.

The owner's own time is the production bottleneck (MobyGames research, footage,
rights, permissions). Time is logged per step so the most expensive step is
visible; the prefilled packet removes the blank-page work for that step without
inventing any fact; the publisher register makes footage permissions reusable.
"""

import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import OwnerTimeLog
from app.pipeline.editorial import EditorialRegistry
from app.pipeline.ideas import classify_idea_hook

OWNER_STEPS = ("idea_selection", "research", "mobygames", "footage_capture", "rights_permissions", "packet_writing", "review_approval", "manual_publishing", "other")
CONTENT_ROOT = Path(__file__).resolve().parents[2] / "content"

PLATFORM_TO_VARIANT = {"youtube_shorts": "youtube_shorts", "instagram_reels": "instagram_reels", "facebook_reels": "facebook_reels", "tiktok": "tiktok", "youtube_long": "youtube_long", "instagram_carousel": "instagram_carousel"}


# --- owner time ------------------------------------------------------------

def log_owner_time(db: Session, story_key: str, step: str, minutes: float, note: str = "") -> OwnerTimeLog:
    if step not in OWNER_STEPS:
        raise ValueError(f"owner_step_unknown:{step}")
    if not 0 < minutes <= 24 * 60:
        raise ValueError("owner_minutes_out_of_range")
    if not story_key.strip():
        raise ValueError("story_key_required")
    row = OwnerTimeLog(story_key=story_key.strip()[:120], step=step, minutes=float(minutes), note=note.strip()[:500])
    db.add(row)
    db.commit()
    return row


def owner_time_report(db: Session, days: int = 60) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    per_story_step: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in db.query(OwnerTimeLog).all():
        logged = row.logged_at.replace(tzinfo=timezone.utc) if row.logged_at.tzinfo is None else row.logged_at
        if logged >= since:
            per_story_step[row.story_key][row.step] += row.minutes
    by_step: dict[str, list[float]] = defaultdict(list)
    totals = []
    for steps in per_story_step.values():
        totals.append(sum(steps.values()))
        for step, minutes in steps.items():
            by_step[step].append(minutes)
    medians = {step: round(statistics.median(values), 1) for step, values in by_step.items()}
    bottleneck = max(medians, key=medians.get) if medians else None
    return {"window_days": days, "stories": len(per_story_step), "median_minutes_per_story": round(statistics.median(totals), 1) if totals else None, "median_minutes_by_step": medians, "bottleneck_step": bottleneck, "automation_hint": AUTOMATION_HINTS.get(bottleneck)}


AUTOMATION_HINTS = {
    "research": "Use `python -m app.cli prefill-packet --idea <ID>` so research starts from the idea, recipe and source requirements.",
    "packet_writing": "Use the prefilled packet; only replace the draft opening and add inspected sources and claims.",
    "mobygames": "MobyGames shows bot protection; keep a per-game research note and reuse it within its 168-hour window. No scraping.",
    "rights_permissions": "Record each publisher's policy once in content/PUBLISHER_POLICIES.json and reuse it until it expires.",
    "footage_capture": "Batch captures per game in Capture Bridge folders; one session can feed several stories.",
    "manual_publishing": "Approve all destinations at once; publishing jobs run per platform automatically.",
}


# --- prefilled packet --------------------------------------------------------

def prefill_packet(idea_id: str, now: datetime | None = None) -> dict:
    """A schema-valid packet in state needs_evidence. It contains no facts: only the idea,
    a draft opening the owner must rewrite or confirm, and every open requirement as a blocker."""
    now = now or datetime.now(timezone.utc)
    registry = EditorialRegistry()
    idea = registry.idea(idea_id)
    recipe = registry.recipe(idea["recipe_id"])
    platforms = idea["recommended_platforms"]
    short_platforms = [platform for platform in platforms if platform != "youtube_long"] or platforms
    target = idea["target_seconds"][0] if isinstance(idea["target_seconds"], list) else idea["target_seconds"]
    variants = [{
        "id": f"v-{platform.replace('_', '-')}",
        "platform": PLATFORM_TO_VARIANT.get(platform, platform),
        "kind": "narrated_video",
        "parent_variant_id": None,
        "game_ids": [],
        "title": idea["title"].split(":", 1)[-1].strip()[:100],
        "caption": "DRAFT — write after evidence and footage are confirmed.",
        "segment_ids": ["S01"],
        "target_seconds": target,
        "technical_capability_status": "not_checked",
        "disclosure_status": "needs_review",
        "disclosure_note": "Prefilled draft; nothing has been verified.",
    } for platform in short_platforms[:4]]
    blockers = [f"Source requirement: {requirement}" for requirement in idea["source_requirements"]]
    blockers += [f"Footage required: {item}" for item in idea["required_footage"]]
    blockers += ["MobyGames preparation (page, score or not-found note, trivia or not-found note, release platforms) for every featured game.", "Draft opening S01 is the idea's hook; rewrite or confirm it and add the remaining segments.", "Check the publisher policy register for every game's footage."]
    return {
        "schema_version": "1.1.0",
        "story_id": f"{idea_id}-{now.strftime('%Y%m%d')}",
        "lane": idea["lane"],
        "state": "needs_evidence",
        "target_language": "en",
        "promise": idea["angle"],
        "recipe_id": idea["recipe_id"],
        "created_at": now.isoformat(),
        "sources": [],
        "claims": [],
        "games": [],
        "media": [],
        "segments": [{"id": "S01", "start": 0, "end": 5, "voiceover": idea["hook"], "claim_ids": [], "reception_for": [], "shots": []}],
        "variants": variants,
        "blockers": blockers,
        "analytics_hypothesis": f"{idea.get('learning_question') or 'Record what this story should teach us.'} (draft hook type: {classify_idea_hook(idea['hook'])}; recipe: {recipe['title']})",
        "approval": {"owner_approved": False, "approved_revision": None, "revision": "prefill-1", "evidence_reviewed": False, "actual_media_reviewed": False, "voice_render_timed": False, "approved_at": None},
    }


def write_prefilled_packet(idea_id: str, plans_root: Path) -> Path:
    packet = prefill_packet(idea_id)
    folder = plans_root / packet["story_id"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "editorial-packet.json"
    if path.exists():
        raise ValueError("packet_already_exists")
    path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
    checklist = ["# Checklist for " + packet["story_id"], "", *[f"- [ ] {item}" for item in packet["blockers"]], "", "Log your time per step: `python -m app.cli timelog add --story " + packet["story_id"] + " --step research --minutes 30`"]
    (folder / "CHECKLIST.md").write_text("\n".join(checklist) + "\n", encoding="utf-8")
    return path


# --- publisher policy register ------------------------------------------------

def load_publisher_policies(path: Path | None = None) -> list[dict]:
    return json.loads((path or CONTENT_ROOT / "PUBLISHER_POLICIES.json").read_text(encoding="utf-8"))["publishers"]


def publisher_policy_blockers(rights_holders: list[str], now: datetime | None = None, policies: list[dict] | None = None) -> list[str]:
    """Block footage whose publisher is in the register but disallows use, is unverified or expired."""
    now = now or datetime.now(timezone.utc)
    policies = load_publisher_policies() if policies is None else policies
    blockers = []
    for holder in sorted(set(rights_holders)):
        lowered = holder.casefold()
        entry = next((item for item in policies if any(alias.casefold() in lowered for alias in [item["publisher"], *item.get("aliases", [])])), None)
        if entry is None:
            continue
        if entry.get("video_use_allowed") is False or entry.get("monetization_allowed") is False:
            blockers.append(f"publisher_policy_disallows:{entry['publisher']}")
            continue
        verified = entry.get("verified_at")
        if not verified:
            blockers.append(f"publisher_policy_unverified:{entry['publisher']}")
            continue
        verified_at = datetime.fromisoformat(verified.replace("Z", "+00:00"))
        if verified_at.tzinfo is None:
            verified_at = verified_at.replace(tzinfo=timezone.utc)
        if now - verified_at > timedelta(days=int(entry.get("reverify_after_days", 180))):
            blockers.append(f"publisher_policy_reverify_required:{entry['publisher']}")
    return blockers
