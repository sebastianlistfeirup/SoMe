from datetime import datetime, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Cost


class BudgetExceeded(ValueError):
    pass


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def reserve(db: Session, job_id: str, kind: str, estimate_dkk: float) -> Cost:
    settings = get_settings()
    if not settings.paid_jobs_enabled:
        raise BudgetExceeded("paid_jobs_disabled")
    if estimate_dkk <= 0 or estimate_dkk > settings.max_job_ai_cost_dkk:
        raise BudgetExceeded("job_cost_limit")
    if db.in_transaction():
        if db.dirty or db.new or db.deleted:
            raise RuntimeError("reserve_rejects_uncommitted_changes")
        db.rollback()
    db.execute(text("BEGIN IMMEDIATE"))
    try:
        start = month_start()
        rows = db.query(Cost).filter(Cost.created_at >= start, Cost.currency == "DKK").all()
        committed = sum(row.actual_amount if row.actual_amount is not None else row.estimated_amount for row in rows if row.status != "CANCELLED")
        if committed + estimate_dkk > settings.monthly_ai_budget_dkk:
            raise BudgetExceeded("monthly_budget_exceeded")
        cost = Cost(job_id=job_id, kind=kind, estimated_amount=estimate_dkk)
        db.add(cost)
        db.commit()
        db.refresh(cost)
        return cost
    except Exception:
        db.rollback()
        raise


def settle(db: Session, cost: Cost, actual_dkk: float, token_in: int | None = None, token_out: int | None = None, uncertain: bool = False) -> None:
    cost.actual_amount = actual_dkk
    cost.token_in = token_in
    cost.token_out = token_out
    cost.status = "UNCERTAIN" if uncertain else "SETTLED"
    db.commit()


def monthly_total(db: Session) -> float:
    start = month_start()
    rows = db.query(Cost).filter(Cost.created_at >= start, Cost.currency == "DKK", Cost.status != "CANCELLED").all()
    return sum(row.actual_amount if row.actual_amount is not None else row.estimated_amount for row in rows)
