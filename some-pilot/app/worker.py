import json
import socket
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.adapters.youtube import YouTubeAdapter
from app.config import get_settings
from app.db.models import Setting
from app.db.session import SessionLocal, init_database
from app.pipeline.approvals import ApprovalError, paused
from app.pipeline.backup import create_backup
from app.pipeline.dispatch import publish_destination
from app.pipeline.jobs import claim, complete, enqueue, fail, recover_expired_leases
from app.pipeline.learning import weekly_learning
from app.pipeline.maintenance import cleanup_temporary_files, prune_backups
from app.pipeline.metrics import collect_due
from app.pipeline.research import bible_research
from app.pipeline.revisions import create_post_revision
from app.pipeline.accounts import probe_accounts
from app.pipeline.alerts import daily_digest, immediate


def next_local(hour: int, weekday: int | None = None) -> datetime:
    zone = ZoneInfo(get_settings().app_timezone)
    now = datetime.now(zone)
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if weekday is not None:
        candidate += timedelta(days=(weekday - candidate.weekday()) % 7)
    if candidate <= now:
        candidate += timedelta(days=7 if weekday is not None else 1)
    return candidate.astimezone(timezone.utc)


def schedule(db) -> None:
    jobs = (("research", next_local(6)), ("metrics", datetime.now(timezone.utc)), ("learn_weekly", next_local(8, 0)), ("backup", next_local(3)), ("maintenance", next_local(4)), ("account_probe", next_local(5)), ("alerts_digest", next_local(7)), ("comments", next_local(6, 2)))
    for kind, due in jobs:
        enqueue(db, kind, {}, f"{kind}:{due.date().isoformat()}:{due.hour}", due_at=due)
    zone = ZoneInfo(get_settings().app_timezone)
    now_local = datetime.now(zone)
    first_next = (now_local.replace(day=1) + timedelta(days=32)).replace(day=1, hour=6, minute=0, second=0, microsecond=0)
    enqueue(db, "cost_report", {}, f"cost_report:{first_next.date().isoformat()}", due_at=first_next.astimezone(timezone.utc))
    restore_due = first_next.replace(hour=5)
    enqueue(db, "restore_drill", {}, f"restore_drill:{restore_due.date().isoformat()}", due_at=restore_due.astimezone(timezone.utc))


def heartbeat(db, worker_id: str) -> None:
    db.merge(Setting(key="worker_heartbeat", value_json={"worker_id": worker_id, "at_utc": datetime.now(timezone.utc).isoformat()}))
    db.commit()


def execute(db, job) -> Path:
    settings = get_settings()
    output = settings.data_dir / "jobs" / job.id
    output.mkdir(parents=True, exist_ok=True)
    if job.kind == "research":
        if not settings.youtube_api_key:
            result = {"status": "not_configured", "collected": 0}
        else:
            result = bible_research(db, output)
    elif job.kind == "metrics":
        result = collect_due(db, collect=True)
    elif job.kind == "learn_weekly":
        result = weekly_learning(db, output)
    elif job.kind == "backup":
        result = create_backup(db, settings.data_dir / "backups", verify=True)
        result["pruned"] = prune_backups(settings.data_dir / "backups")
        from app.pipeline.backup import upload_offsite

        result["offsite_upload"] = upload_offsite(Path(result["path"]))
    elif job.kind == "maintenance":
        result = {"deleted_temporary_files": cleanup_temporary_files()}
    elif job.kind == "revise_post":
        video = create_post_revision(db, job.payload["video_id"], job.payload["review_id"], job.id)
        result = {"status": "AWAITING_OWNER", "video_id": video.id, "source_video_id": job.payload["video_id"], "scope": "title_caption_hashtags"}
    elif job.kind == "publish":
        result = publish_destination(db, job.payload)
    elif job.kind == "produce":
        result = run_produce_job(db, job)
    elif job.kind == "alerts_digest":
        result = daily_digest(db)
    elif job.kind == "account_probe":
        result = probe_accounts(db)
    elif job.kind == "comments":
        from app.pipeline.audience import collect_comments, suggestions_from_comments

        if not settings.youtube_api_key:
            result = {"status": "not_configured"}
        else:
            result = collect_comments(db)
            result["suggestions"] = [item.id for item in suggestions_from_comments(db)]
    elif job.kind == "cost_report":
        from app.pipeline.ops import monthly_cost_report

        result = monthly_cost_report(db)
    elif job.kind == "restore_drill":
        from app.pipeline.backup import restore_drill

        result = restore_drill(settings.data_dir / "backups", settings.data_dir / "restore-drills")
    else:
        raise ValueError("unsupported_job_kind")
    path = output / "result.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return path


def log_event(event: str, job=None, **fields) -> None:
    """One JSON line per event on stdout (collected by Docker logs)."""
    record = {"at": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    if job is not None:
        record.update({"job_id": job.id, "kind": job.kind, "attempt": job.attempts, "status": job.status})
        if job.started_at:
            started = job.started_at if job.started_at.tzinfo else job.started_at.replace(tzinfo=timezone.utc)
            record["duration_seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 3)
    print(json.dumps(record, default=str), flush=True)


def error_code_for(exc: Exception) -> str:
    from app.pipeline.platforms import PublishError

    if isinstance(exc, (ApprovalError, PublishError)):
        return str(exc)
    message = (str(exc).splitlines() or [""])[0]
    # Our own pipeline errors are short snake_case codes; keep them, they are the useful part.
    if isinstance(exc, (ValueError, RuntimeError)) and message and len(message) <= 120 and " " not in message.split(":", 1)[0]:
        return f"{type(exc).__name__}:{message}"
    return type(exc).__name__


def handle_failure(db, job, exc: Exception) -> None:
    import traceback

    from app.pipeline.redact import redact

    settings = get_settings()
    output = settings.data_dir / "jobs" / job.id
    output.mkdir(parents=True, exist_ok=True)
    detail = output / f"error-attempt-{job.attempts}.json"
    message = redact(str(exc))[:500]
    detail.write_text(json.dumps({"job_id": job.id, "kind": job.kind, "attempt": job.attempts, "error_type": type(exc).__name__, "message": message, "traceback": redact("".join(traceback.format_exception(exc)))[-8000:], "at": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")
    db.rollback()
    fail(db, job, redact(error_code_for(exc)), message=message, detail_path=str(detail))
    log_event("job_failed", job=job, error_code=job.error_code)
    if job.status == "FAILED":
        try:
            immediate(db, "error", f"job_failed:{job.kind}:{job.id[:8]}", f"Job {job.kind} failed after {job.attempts} attempts: {job.error_code}")
        except Exception:
            pass


def run_produce_job(db, job) -> dict:
    from app.pipeline.jobs import renew_lease
    from app.pipeline.production import produce

    settings = get_settings()
    root = (settings.data_dir / "media-plans").resolve()
    plan = (root / job.payload["media_plan"]).resolve()
    if root not in plan.parents or not plan.is_file():
        raise ValueError("media_plan_outside_media_plans_or_missing")

    def progress(stage: str) -> None:
        renew_lease(db, job, stage, lease_seconds=max(600, settings.render_max_seconds * 2))
        heartbeat(db, socket.gethostname())

    video = produce(db, int(job.payload["topic_id"]), bool(job.payload.get("dry_run", True)), plan, progress=progress)
    return {"video_id": video.id, "status": video.status, "output_dir": video.output_dir, "dry_run": bool(job.payload.get("dry_run", True))}


def run() -> None:
    settings = get_settings()
    init_database()
    worker_id = socket.gethostname()
    while True:
        db = SessionLocal()
        try:
            heartbeat(db, worker_id)
            recover_expired_leases(db)
            schedule(db)
            if paused(db):
                time.sleep(settings.worker_poll_seconds)
                continue
            job = claim(db, worker_id)
            if job is None:
                time.sleep(settings.worker_poll_seconds)
                continue
            try:
                path = execute(db, job)
                complete(db, job, str(path))
                log_event("job_succeeded", job=job)
            except Exception as exc:
                handle_failure(db, job, exc)
        finally:
            db.close()


if __name__ == "__main__":
    run()
