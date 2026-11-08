import threading

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.pipeline.costs import BudgetExceeded, monthly_total, reserve
from app.pipeline.jobs import claim, enqueue


def test_job_idempotency_and_single_claim(db):
    job, created = enqueue(db, "research", {}, "same-job")
    same, created_again = enqueue(db, "research", {}, "same-job")
    assert created and not created_again and job.id == same.id
    claimed = claim(db, "worker-1")
    assert claimed.id == job.id
    assert claim(db, "worker-2") is None


def test_parallel_job_claim_is_unique(db):
    enqueue(db, "research", {}, "parallel-job")
    claimed = []

    def worker():
        session = Session(db.get_bind())
        try:
            job = claim(session, "worker")
            if job:
                claimed.append(job.id)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(claimed) == 1


def test_budget_limits_and_reservation_accounting(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "paid_jobs_enabled", True)
    monkeypatch.setattr(settings, "monthly_ai_budget_dkk", 10)
    monkeypatch.setattr(settings, "max_job_ai_cost_dkk", 5)
    with pytest.raises(BudgetExceeded, match="job_cost_limit"):
        reserve(db, "job-a", "claude", 6)
    reserve(db, "job-b", "claude", 4)
    reserve(db, "job-c", "claude", 4)
    assert monthly_total(db) == 8
    with pytest.raises(BudgetExceeded, match="monthly_budget"):
        reserve(db, "job-d", "claude", 4)


def test_paid_jobs_disabled_by_default(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "paid_jobs_enabled", False)
    with pytest.raises(BudgetExceeded, match="paid_jobs_disabled"):
        reserve(db, "job", "claude", 1)


def test_parallel_budget_cannot_exceed_limit(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "paid_jobs_enabled", True)
    monkeypatch.setattr(settings, "monthly_ai_budget_dkk", 5)
    monkeypatch.setattr(settings, "max_job_ai_cost_dkk", 5)
    successes = []
    failures = []

    def worker(number):
        session = Session(db.get_bind())
        try:
            reserve(session, f"parallel-{number}", "claude", 4)
            successes.append(number)
        except BudgetExceeded:
            failures.append(number)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(number,)) for number in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(successes) == 1 and len(failures) == 1
