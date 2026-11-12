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
from app.pipeline.research import run_adapters
from app.pipeline.revisions import create_post_revision


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
    jobs = (("research", next_local(6)), ("metrics", datetime.now(timezone.utc)), ("learn_weekly", next_local(8, 0)), ("backup", next_local(3)), ("maintenance", next_local(4)))
    for kind, due in jobs:
        enqueue(db, kind, {}, f"{kind}:{due.date().isoformat()}:{due.hour}", due_at=due)


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
            result = run_adapters(db, [YouTubeAdapter()], ["handheld gaming PC", "RTX Spark"], ["en"], 30, output)
    elif job.kind == "metrics":
        result = collect_due(db, collect=True)
    elif job.kind == "learn_weekly":
        result = weekly_learning(db, output)
    elif job.kind == "backup":
        result = create_backup(db, settings.data_dir / "backups", verify=True)
        result["pruned"] = prune_backups(settings.data_dir / "backups")
        result["offsite_upload"] = "not_configured"
    elif job.kind == "maintenance":
        result = {"deleted_temporary_files": cleanup_temporary_files()}
    elif job.kind == "revise_post":
        video = create_post_revision(db, job.payload["video_id"], job.payload["review_id"], job.id)
        result = {"status": "AWAITING_OWNER", "video_id": video.id, "source_video_id": job.payload["video_id"], "scope": "title_caption_hashtags"}
    elif job.kind == "publish":
        result = publish_destination(db, job.payload)
    else:
        raise ValueError("unsupported_job_kind")
    path = output / "result.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return path


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
            except Exception as exc:
                from app.pipeline.platforms import PublishError

                error_code = str(exc) if isinstance(exc, (ApprovalError, PublishError)) else type(exc).__name__
                fail(db, job, error_code)
        finally:
            db.close()


if __name__ == "__main__":
    run()
