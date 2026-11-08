import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Job, utcnow


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


def claim(db: Session, worker_id: str, lease_seconds: int = 300) -> Job | None:
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
        job.updated_at = now
        db.add(AuditEvent(actor=worker_id, action="JOB_CLAIMED", entity_type="job", entity_id=job.id, details_json={"attempt": job.attempts}))
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


def complete(db: Session, job: Job, result_path: str) -> None:
    job.status = "SUCCEEDED"
    job.result_path = result_path
    job.lease_until = None
    db.commit()


def fail(db: Session, job: Job, error_code: str, retry_delay_seconds: int = 60) -> None:
    job.error_code = error_code[:150]
    job.lease_until = None
    if job.attempts < job.max_attempts:
        job.status = "QUEUED"
        job.due_at = utcnow() + timedelta(seconds=retry_delay_seconds)
    else:
        job.status = "FAILED"
    db.commit()


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
