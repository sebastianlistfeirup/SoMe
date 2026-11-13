"""Operational metrics (queue, durations, failures, cost per post) and the monthly cost report."""

import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Cost, Job, Publication, VideoVersion


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _cost_kind(kind: str) -> str:
    lowered = kind.casefold()
    if lowered.startswith("claude"):
        return "claude"
    if "eleven" in lowered:
        return "elevenlabs"
    if lowered.startswith("qwen") or "visual" in lowered:
        return "qwen"
    return "other"


def ops_metrics(db: Session, now: datetime | None = None, days: int = 7) -> dict:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    jobs = db.query(Job).all()
    queue = defaultdict(int)
    for job in jobs:
        queue[job.status] += 1
    durations: dict[str, list[float]] = defaultdict(list)
    outcomes: dict[str, dict[str, int]] = defaultdict(lambda: {"succeeded": 0, "failed": 0})
    for job in jobs:
        finished, started = _utc(job.finished_at), _utc(job.started_at)
        if finished and finished >= since:
            outcomes[job.kind]["succeeded" if job.status == "SUCCEEDED" else "failed"] += 1
            if started:
                durations[job.kind].append((finished - started).total_seconds())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_costs = [row for row in db.query(Cost).all() if _utc(row.created_at) >= month_start]
    spent = sum(row.actual_amount if row.actual_amount is not None else row.estimated_amount for row in month_costs)
    settings = get_settings()
    published = db.query(Publication).filter(Publication.status == "PUBLISHED").all()
    per_post = [float((db.get(VideoVersion, publication.video_version_id).features_json or {}).get("production_cost") or 0) for publication in published if db.get(VideoVersion, publication.video_version_id)]
    return {
        "queue": dict(queue),
        "job_duration_median_seconds": {kind: round(statistics.median(values), 1) for kind, values in durations.items()},
        "job_outcomes_7d": dict(outcomes),
        "month_spend_dkk": round(spent, 4),
        "monthly_budget_dkk": settings.monthly_ai_budget_dkk,
        "budget_used_share": round(spent / settings.monthly_ai_budget_dkk, 4) if settings.monthly_ai_budget_dkk else None,
        "median_production_cost_per_published_post_dkk": round(statistics.median(per_post), 4) if per_post else None,
    }


def monthly_cost_report(db: Session, month: str | None = None, output_dir: Path | None = None) -> dict:
    """Actual spend by provider versus the documented estimates for one calendar month (YYYY-MM)."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if month is None:
        previous = now.replace(day=1) - timedelta(days=1)
        month = previous.strftime("%Y-%m")
    start = datetime.strptime(month + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = (start + timedelta(days=32)).replace(day=1)
    totals = defaultdict(lambda: {"estimated": 0.0, "actual": 0.0, "uncertain": 0.0, "calls": 0})
    for row in db.query(Cost).all():
        created = _utc(row.created_at)
        if not (start <= created < end):
            continue
        bucket = totals[_cost_kind(row.kind)]
        bucket["calls"] += 1
        bucket["estimated"] += row.estimated_amount
        if row.actual_amount is not None:
            bucket["actual"] += row.actual_amount
        if row.status == "UNCERTAIN":
            bucket["uncertain"] += row.estimated_amount
    videos = [video for video in db.query(VideoVersion).all() if start <= _utc(video.created_at) < end and not (video.features_json or {}).get("is_demo")]
    published_ids = {publication.video_version_id for publication in db.query(Publication).filter(Publication.status == "PUBLISHED").all()}
    api_actual = sum(item["actual"] for item in totals.values())
    total = settings.server_monthly_cost_dkk + api_actual
    report = {
        "month": month,
        "server_dkk": settings.server_monthly_cost_dkk,
        "server_note": "Configured control-panel price; verify against the invoice (VAT not included).",
        "providers": {name: {key: round(value, 4) for key, value in values.items()} for name, values in totals.items()},
        "api_actual_dkk": round(api_actual, 4),
        "api_estimate_dkk": settings.expected_monthly_api_dkk,
        "api_vs_estimate": round(api_actual - settings.expected_monthly_api_dkk, 4),
        "total_dkk": round(total, 2),
        "productions": len(videos),
        "published_productions": len([video for video in videos if video.id in published_ids]),
        "cost_per_production_dkk": round(api_actual / len(videos), 4) if videos else None,
        "budget_dkk": settings.monthly_ai_budget_dkk,
        "note": "Estimates, not invoices. Exchange rate, VAT and subscription quota can change real charges.",
    }
    output_dir = output_dir or settings.data_dir / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"costs-{month}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [f"# Omkostninger {month}", "", f"- Server: {report['server_dkk']:.2f} DKK (kontrolpanelpris, verificér faktura)", f"- API faktisk: {report['api_actual_dkk']:.2f} DKK (estimat {report['api_estimate_dkk']:.2f} DKK, afvigelse {report['api_vs_estimate']:+.2f})"]
    lines += [f"  - {name}: {values['actual']:.4f} DKK over {values['calls']} kald" for name, values in report["providers"].items()]
    lines += [f"- I alt: {report['total_dkk']:.2f} DKK", f"- Produktioner: {report['productions']} (publiceret: {report['published_productions']})", f"- API-pris pr. produktion: {report['cost_per_production_dkk']}", "", report["note"]]
    (output_dir / f"costs-{month}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
