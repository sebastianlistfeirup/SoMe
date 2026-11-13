"""Weekly scorecard, shadow mode and automatic rollback for the learning model.

weekly_learning computes a new model every week ("learning_model"). That model
is only a candidate: prompts use the *active* model. A candidate is promoted
after one full week in shadow mode when guardrails are healthy and its shadow
predictions did not contradict the week's outcomes. If the primary metric falls
two weeks in a row after an activation, the previous active model is restored.
Nothing here changes code, policy, footage or publishing.
"""

import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Publication, Review, Setting, VideoVersion
from app.pipeline.taxonomy import normalize_hook

GOVERNANCE_KEY = "learning_governance"
PRIMARY_METRIC = "net_subscribers_per_1k_views"
GUARDRAIL_METRICS = ("retention_pct", "hook_retention_3s")
SHADOW_DAYS = 6
GUARDRAIL_FLOOR = 0.85
WEEKS = 6


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _week_start(moment: datetime) -> datetime:
    moment = _utc(moment)
    return (moment - timedelta(days=moment.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def first_pass_approval_rate(db: Session, since: datetime, until: datetime) -> dict:
    """Share of produced videos whose first owner decision was an approval."""
    first: dict[int, Review] = {}
    for review in db.query(Review).order_by(Review.created_at, Review.id).all():
        if review.decision not in {"APPROVED", "REJECTED"}:
            continue
        first.setdefault(review.video_version_id, review)
    decided = [review for review in first.values() if since <= _utc(review.created_at) < until]
    approved = [review for review in decided if review.decision == "APPROVED"]
    return {"n": len(decided), "rate": round(len(approved) / len(decided), 4) if decided else None}


def scorecard(db: Session, now: datetime | None = None, weeks: int = WEEKS) -> list[dict]:
    """Weekly medians of day-7 signals for publications published in each week."""
    from app.pipeline.learning import _publication_metrics, _signals

    now = _utc(now or datetime.now(timezone.utc))
    current = _week_start(now)
    starts = [current - timedelta(weeks=offset) for offset in range(weeks, 0, -1)]
    per_publication = _publication_metrics(db, False, 7)
    buckets: dict[datetime, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for publication_id, metrics in per_publication.items():
        publication = db.get(Publication, publication_id)
        if not publication or not publication.published_at:
            continue
        week = _week_start(publication.published_at)
        for name, value in _signals(metrics).items():
            buckets[week][name].append(value)
    rows = []
    for start in starts:
        signals = buckets.get(start, {})
        row = {"week_start": start.date().isoformat(), "primary_metric": PRIMARY_METRIC, "primary": statistics.median(signals[PRIMARY_METRIC]) if signals.get(PRIMARY_METRIC) else None, "primary_n": len(signals.get(PRIMARY_METRIC, []))}
        for name in GUARDRAIL_METRICS:
            row[name] = statistics.median(signals[name]) if signals.get(name) else None
        row["first_pass_approval"] = first_pass_approval_rate(db, start, start + timedelta(weeks=1))
        rows.append(row)
    return rows


def _guardrail_breaches(rows: list[dict]) -> list[str]:
    if len(rows) < 2:
        return []
    latest, history = rows[-1], rows[-5:-1]
    breaches = []
    for name in GUARDRAIL_METRICS:
        previous = [row[name] for row in history if row.get(name) is not None]
        if latest.get(name) is not None and previous and latest[name] < GUARDRAIL_FLOOR * statistics.median(previous):
            breaches.append(name)
    previous_rates = [row["first_pass_approval"]["rate"] for row in history if row["first_pass_approval"]["rate"] is not None]
    latest_rate = latest["first_pass_approval"]["rate"]
    if latest_rate is not None and previous_rates and latest_rate < GUARDRAIL_FLOOR * statistics.median(previous_rates):
        breaches.append("first_pass_approval")
    return breaches


def _two_consecutive_declines(rows: list[dict], since: datetime) -> bool:
    after = [row for row in rows if row["primary"] is not None and datetime.fromisoformat(row["week_start"]).replace(tzinfo=timezone.utc) >= _week_start(since) - timedelta(weeks=1)]
    if len(after) < 3:
        return False
    a, b, c = (row["primary"] for row in after[-3:])
    return b < a and c < b


def shadow_agreement(db: Session, multipliers: dict[str, float], since: datetime, until: datetime) -> dict:
    """Did the candidate's hook ranking point the same way as this window's outcomes?"""
    from app.pipeline.learning import _publication_metrics, _signals

    by_hook: dict[str, list[float]] = defaultdict(list)
    for publication_id, metrics in _publication_metrics(db, False, 7).items():
        publication = db.get(Publication, publication_id)
        if not publication or not publication.published_at or not (since <= _utc(publication.published_at) < until):
            continue
        video = db.get(VideoVersion, publication.video_version_id)
        value = _signals(metrics).get(PRIMARY_METRIC)
        if video is not None and value is not None:
            by_hook[normalize_hook(video.hook_type, strict=False)].append(value)
    scored = {hook: statistics.median(values) for hook, values in by_hook.items() if hook in multipliers}
    if len(scored) < 2:
        return {"hooks_compared": len(scored), "agreement": None}
    overall = statistics.median(scored.values())
    agree = sum(1 for hook, value in scored.items() if (multipliers[hook] >= 1) == (value >= overall))
    return {"hooks_compared": len(scored), "agreement": round(agree / len(scored), 4)}


def _state(db: Session) -> dict:
    setting = db.get(Setting, GOVERNANCE_KEY)
    return dict(setting.value_json) if setting else {"active": None, "candidate": None, "history": [], "events": []}


def active_learning_model(db: Session) -> dict | None:
    return _state(db).get("active")


def weekly_step(db: Session, latest_model: dict, now: datetime | None = None) -> dict:
    now = _utc(now or datetime.now(timezone.utc))
    state = _state(db)
    history = list(state.get("history", []))
    events = list(state.get("events", []))
    rows = scorecard(db, now)
    breaches = _guardrail_breaches(rows)
    active = state.get("active")
    candidate = state.get("candidate")

    def log(action: str, **details) -> None:
        events.append({"at": now.isoformat(), "action": action, **details})
        db.add(AuditEvent(actor="learning", action=action, entity_type="learning_model", entity_id=str(details.get("version")), details_json=details))

    rolled_back = False
    if active and _two_consecutive_declines(rows, datetime.fromisoformat(active["activated_at"])):
        previous = history.pop() if history else None
        log("LEARNING_MODEL_ROLLED_BACK", version=active["version"], restored=previous["version"] if previous else None, reason="primary_metric_declined_two_consecutive_weeks")
        active = previous
        rolled_back = True
    shadow = None
    if candidate and not rolled_back and (not active or candidate["version"] != active["version"]):
        computed = datetime.fromisoformat(candidate["computed_at"])
        shadow = shadow_agreement(db, candidate["model"].get("hook_multipliers", {}), computed, now)
        aged = now - computed >= timedelta(days=SHADOW_DAYS)
        contradicted = shadow["agreement"] is not None and shadow["hooks_compared"] >= 4 and shadow["agreement"] < 0.5
        if aged and not breaches and not contradicted:
            if active:
                history.append(active)
            active = {"version": candidate["version"], "model": candidate["model"], "activated_at": now.isoformat(), "shadow": shadow}
            log("LEARNING_MODEL_ACTIVATED", version=candidate["version"], shadow=shadow)
        elif aged:
            log("LEARNING_MODEL_PROMOTION_BLOCKED", version=candidate["version"], guardrail_breaches=breaches, shadow=shadow)
    new_candidate = {"version": latest_model["version"], "model": latest_model, "computed_at": now.isoformat()}
    state = {"active": active, "candidate": new_candidate, "history": history[-10:], "events": events[-50:], "scorecard": rows, "guardrail_breaches": breaches, "updated_at": now.isoformat()}
    db.merge(Setting(key=GOVERNANCE_KEY, value_json=state))
    db.commit()
    return {"active_version": active["version"] if active else None, "candidate_version": new_candidate["version"], "rolled_back": rolled_back, "guardrail_breaches": breaches, "shadow": shadow, "scorecard": rows}
