import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Job, utcnow

BACKOFF_BASE_SECONDS = 60
BACKOFF_MAX_SECONDS = 3600
DEFAULT_LEASE_SECONDS = 300
# Jobs whose failure may leave an uncertain remote state are never retried blindly.
NO_MANUAL_RETRY_ERRORS = ("reconcile", "RECONCILE")


def enqueue(db: Session, kind: str, payload: dict, idempotency_key: str, due_at: datetime | None = None, max_attempts: int = 3) -> tuple[Job, bool]:
    existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
    if existing:
        return existing, False
    job = Job(id=str(uuid.uuid4()), kind=kind, payload=payload, idempotency_key=idempotency_key, due_at=due_at or utcnow(), max_attempts=max_attempts)
    db.add(job)
    try:
        db.commit()
    except Exception:
        db.rollback()
        existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
        if existing:
            return existing, False
        raise
    return job, True


def claim(db: Session, worker_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> Job | None:
    if db.in_transaction():
        if db.dirty or db.new or db.deleted:
            raise RuntimeError("claim_rejects_uncommitted_changes")
        db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))
    try:
        now = utcnow()
        candidates = db.query(Job).filter(Job.status == "QUEUED").order_by(Job.due_at, Job.created_at).all()
        job = next((item for item in candidates if _as_utc(item.due_at) <= now and item.attempts < item.max_attempts), None)
        if job is None:
            db.commit()
            return None
        job.status = "RUNNING"
        job.attempts += 1
        job.lease_until = now + timedelta(seconds=lease_seconds)
        job.started_at = now
        job.progress_json = {"stage": "claimed", "at": now.isoformat()}
        job.updated_at = now
        db.add(AuditEvent(actor=worker_id, action="JOB_CLAIMED", entity_type="job", entity_id=job.id, details_json={"attempt": job.attempts}))
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


def renew_lease(db: Session, job: Job, stage: str | None = None, detail: dict | None = None, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> None:
    """Called by long jobs (render, upload) so the lease never expires while they still run."""
    now = utcnow()
    job.lease_until = now + timedelta(seconds=lease_seconds)
    if stage:
        history = list((job.progress_json or {}).get("history", []))[-20:]
        history.append({"stage": stage, "at": now.isoformat()})
        job.progress_json = {"stage": stage, "at": now.isoformat(), "detail": detail or {}, "history": history}
    db.commit()


def complete(db: Session, job: Job, result_path: str) -> None:
    job.status = "SUCCEEDED"
    job.result_path = result_path
    job.lease_until = None
    job.finished_at = utcnow()
    job.progress_json = {**(job.progress_json or {}), "stage": "done"}
    db.commit()


def backoff_seconds(attempts: int) -> int:
    return min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * 2 ** max(0, attempts - 1))


def fail(db: Session, job: Job, error_code: str, retry_delay_seconds: int | None = None, message: str | None = None, detail_path: str | None = None) -> None:
    job.error_code = error_code[:150]
    job.error_message = (message or "")[:500] or None
    job.lease_until = None
    if detail_path:
        job.result_path = detail_path
    if job.attempts < job.max_attempts:
        job.status = "QUEUED"
        job.due_at = utcnow() + timedelta(seconds=retry_delay_seconds if retry_delay_seconds is not None else backoff_seconds(job.attempts))
    else:
        job.status = "FAILED"
        job.finished_at = utcnow()
    db.commit()


def can_retry(job: Job) -> bool:
    return job.status == "FAILED" and not any(marker in (job.error_code or "") for marker in NO_MANUAL_RETRY_ERRORS)


def retry_failed(db: Session, job_id: str, actor: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise ValueError("job_not_found")
    if not can_retry(job):
        raise ValueError("job_not_retryable")
    previous = job.error_code
    job.status = "QUEUED"
    job.attempts = 0
    job.due_at = utcnow()
    job.error_code = None
    job.error_message = None
    job.finished_at = None
    db.add(AuditEvent(actor=actor, action="JOB_RETRIED", entity_type="job", entity_id=job.id, details_json={"previous_error": previous}))
    db.commit()
    return job


def recover_expired_leases(db: Session) -> int:
    now = utcnow()
    jobs = db.query(Job).filter(Job.status == "RUNNING").all()
    recovered = 0
    for job in jobs:
        if job.lease_until and _as_utc(job.lease_until) < now:
            job.status = "QUEUED" if job.attempts < job.max_attempts else "FAILED"
            job.error_code = "lease_expired"
            job.lease_until = None
            recovered += 1
    db.commit()
    return recovered


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
