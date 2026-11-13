import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import AuthUser, Cost, Job, Publication, Setting, Topic
from app.pipeline import alerts
from app.pipeline.jobs import backoff_seconds, can_retry, claim, enqueue, fail, renew_lease, retry_failed
from app.pipeline.redact import redact

NOW = datetime.now(timezone.utc)


def test_redaction_removes_configured_secrets_and_token_patterns(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-very-secret-value")
    text = redact("key sk-ant-very-secret-value failed; Authorization: Bearer abcdefghijklmnop; url?access_token=xyz123456&x=1")
    assert "very-secret" not in text and "abcdefghijklmnop" not in text and "xyz123456" not in text
    assert text.count("[REDACTED]") >= 3


def test_exponential_backoff_and_final_failure_message(db):
    assert [backoff_seconds(n) for n in (1, 2, 3, 10)] == [60, 120, 240, 3600]
    job, _ = enqueue(db, "metrics", {}, "backoff-test", max_attempts=2)
    claimed = claim(db, "w")
    before = datetime.now(timezone.utc)
    fail(db, claimed, "ValueError:boom", message="boom")
    due = claimed.due_at if claimed.due_at.tzinfo else claimed.due_at.replace(tzinfo=timezone.utc)
    assert claimed.status == "QUEUED" and due >= before + timedelta(seconds=55)
    claimed.due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    again = claim(db, "w")
    fail(db, again, "ValueError:boom", message="boom")
    assert again.status == "FAILED" and again.error_message == "boom" and again.finished_at is not None


def test_retry_resets_failed_job_but_never_reconcile_cases(db):
    job, _ = enqueue(db, "metrics", {}, "retry-test", max_attempts=1)
    claimed = claim(db, "w")
    fail(db, claimed, "ValueError:x")
    assert can_retry(claimed)
    retried = retry_failed(db, claimed.id, "owner")
    assert retried.status == "QUEUED" and retried.attempts == 0
    publish, _ = enqueue(db, "publish", {}, "retry-publish", max_attempts=1)
    claimed = claim(db, "w")
    fail(db, claimed, "upload_timeout_reconcile_required")
    assert not can_retry(claimed)
    with pytest.raises(ValueError, match="not_retryable"):
        retry_failed(db, claimed.id, "owner")


def test_renew_lease_records_progress(db):
    enqueue(db, "produce", {}, "lease-test")
    job = claim(db, "w")
    old = job.lease_until
    renew_lease(db, job, "rendering", {"scene": 2}, lease_seconds=900)
    assert job.progress_json["stage"] == "rendering" and job.progress_json["history"][-1]["stage"] == "rendering"
    assert job.lease_until > old


def test_worker_failure_writes_redacted_detail_and_useful_code(db, tmp_path, monkeypatch):
    from app import worker

    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "eleven-secret-123456")
    monkeypatch.setattr(worker, "immediate", lambda *_args, **_kwargs: {"sent": []})
    enqueue(db, "metrics", {}, "failure-test", max_attempts=1)
    job = claim(db, "w")
    worker.handle_failure(db, job, ValueError("editorial_blocked:claim_C01:expired"))
    assert job.error_code == "ValueError:editorial_blocked:claim_C01:expired"
    worker_detail = json.loads(Path(job.result_path).read_text())
    assert worker_detail["error_type"] == "ValueError"
    assert "editorial_blocked" in worker_detail["traceback"]
    enqueue(db, "metrics", {}, "failure-secret", max_attempts=1)
    job = claim(db, "w")
    worker.handle_failure(db, job, RuntimeError("provider said eleven-secret-123456 is invalid"))
    assert job.error_code == "RuntimeError"
    assert "eleven-secret-123456" not in Path(job.result_path).read_text() and "eleven-secret-123456" not in (job.error_message or "")


def test_produce_job_rejects_plans_outside_media_plans(db, tmp_path, monkeypatch):
    from app import worker

    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    (tmp_path / "media-plans").mkdir()
    (tmp_path / "outside.json").write_text("{}")
    enqueue(db, "produce", {"topic_id": 1, "media_plan": "../outside.json"}, "produce-outside")
    job = claim(db, "w")
    with pytest.raises(ValueError, match="media_plan_outside"):
        worker.run_produce_job(db, job)


def test_produce_job_reports_progress_and_renews_lease(db, tmp_path, monkeypatch):
    from app import worker

    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    plans = tmp_path / "media-plans" / "pilot"
    plans.mkdir(parents=True)
    (plans / "plan.json").write_text("{}")
    stages = []

    def fake_produce(_db, topic_id, dry_run, plan, progress=None):
        progress("rendering")
        stages.append((topic_id, dry_run, plan.name))
        return SimpleNamespace(id=9, status="AWAITING_OWNER", output_dir="x")

    monkeypatch.setattr("app.pipeline.production.produce", fake_produce)
    enqueue(db, "produce", {"topic_id": 3, "media_plan": "pilot/plan.json", "dry_run": True}, "produce-ok")
    job = claim(db, "w")
    result = worker.run_produce_job(db, job)
    assert result["video_id"] == 9 and stages == [(3, True, "plan.json")]
    assert job.progress_json["stage"] == "rendering"


def test_alerts_collect_failures_backup_heartbeat_budget_and_reconcile(db, awaiting_video, monkeypatch):
    monkeypatch.setattr(get_settings(), "monthly_ai_budget_dkk", 10)
    enqueue(db, "publish", {}, "alert-job", max_attempts=1)
    job = claim(db, "w")
    fail(db, job, "PublishError:x")
    db.add(Publication(video_version_id=awaiting_video.id, platform="youtube", account="a", idempotency_key="rec", status="RECONCILE_REQUIRED", error_code="upload_timeout"))
    db.add(Cost(job_id="c", kind="claude_script", estimated_amount=9, actual_amount=9, status="SETTLED"))
    db.commit()
    codes = {alert["code"].split(":")[0] for alert in alerts.collect_alerts(db)}
    assert {"job_failed", "reconcile", "backup_stale_or_failed", "worker_heartbeat_stale", "ai_budget"} <= codes


def test_notify_needs_channel_suppresses_repeats_and_redacts(db, monkeypatch):
    settings = get_settings()
    assert alerts.notify(db, [{"severity": "error", "code": "x", "message": "m"}], "s")["status"] == "no_channel_configured"
    monkeypatch.setattr(settings, "alert_webhook_url", "https://hooks.example.test/abc")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-leaky-123456")
    posts = []
    monkeypatch.setattr(alerts.httpx, "post", lambda url, json, timeout: posts.append(json) or SimpleNamespace(raise_for_status=lambda: None))
    first = alerts.notify(db, [{"severity": "error", "code": "x", "message": "key sk-ant-leaky-123456"}], "subject")
    assert first["sent"] == ["webhook"] and "leaky" not in posts[0]["content"]
    second = alerts.notify(db, [{"severity": "error", "code": "x", "message": "again"}], "subject")
    assert second["sent"] == [] and second["suppressed"] == 1


def test_account_probe_records_status_without_secrets(db, monkeypatch):
    from app.pipeline import accounts

    settings = get_settings()
    for field, value in (("youtube_client_id", "cid"), ("youtube_client_secret", "csecret-123456"), ("youtube_refresh_token", "refresh-token-123456")):
        monkeypatch.setattr(settings, field, value)
    monkeypatch.setattr(settings, "meta_access_token", "")
    monkeypatch.setattr(settings, "meta_page_access_token", "")
    monkeypatch.setattr(settings, "tiktok_access_token", "")
    monkeypatch.setattr(accounts.httpx, "post", lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: {"access_token": "at-123456", "scope": "https://www.googleapis.com/auth/youtube.upload"}))
    monkeypatch.setattr(accounts.httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: {"items": [{"id": "UC123", "snippet": {"title": "Pixel and Parameters"}}]}))
    result = accounts.probe_accounts(db, NOW)
    youtube = result["platforms"]["youtube"]
    assert youtube["ok"] and youtube["account_id"] == "UC123" and youtube["expires_in_days"] == 7
    assert result["platforms"]["meta"] == {"configured": False, "ok": False, "checked_at": NOW.isoformat(), "last_ok_at": None}
    stored = json.dumps(db.get(Setting, "account_status").value_json)
    assert "refresh-token-123456" not in stored and "at-123456" not in stored and "csecret" not in stored
    later = accounts.probe_accounts(db, NOW + timedelta(days=5))
    assert later["platforms"]["youtube"]["expires_in_days"] == 2


def test_ops_metrics_and_monthly_cost_report(db, awaiting_video, tmp_path):
    from app.pipeline.ops import monthly_cost_report, ops_metrics

    month = NOW.strftime("%Y-%m")
    db.add_all([Cost(job_id="a", kind="claude_script", estimated_amount=0.3, actual_amount=0.2, status="SETTLED"), Cost(job_id="b", kind="ELEVENLABS", estimated_amount=0.5, actual_amount=0.5, status="ACTUAL")])
    db.commit()
    metrics = ops_metrics(db)
    assert metrics["month_spend_dkk"] == pytest.approx(0.7)
    report = monthly_cost_report(db, month, tmp_path)
    assert report["providers"]["claude"]["actual"] == pytest.approx(0.2) and report["providers"]["elevenlabs"]["actual"] == pytest.approx(0.5)
    assert report["total_dkk"] == pytest.approx(get_settings().server_monthly_cost_dkk + 0.7, abs=0.01)
    assert (tmp_path / f"costs-{month}.md").is_file()


def test_restore_drill_proves_backup_and_removes_copy(db, monkeypatch):
    from app.pipeline.backup import create_backup, restore_drill

    settings = get_settings()
    monkeypatch.setattr(settings, "backup_key", "")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db.info['database_path']}")
    backups = db.info["tmp_path"] / "backups"
    create_backup(db, backups, verify=True)
    drills = db.info["tmp_path"] / "drills"
    report = restore_drill(backups, drills)
    assert report["integrity"] == "ok" and "video_versions" in report["row_counts"]
    remaining = list(drills.iterdir())
    assert len(remaining) == 1 and remaining[0].name.startswith("drill-") and remaining[0].suffix == ".json"


def test_offsite_upload_is_off_by_default_and_refuses_unencrypted(tmp_path, monkeypatch):
    from app.pipeline.backup import upload_offsite

    plain = tmp_path / "some-backup-20260101T000000Z.zip"
    plain.write_bytes(b"x")
    assert upload_offsite(plain) == {"status": "not_configured"}
    settings = get_settings()
    for field, value in (("offsite_webdav_url", "https://box.example.test/backups"), ("offsite_username", "u"), ("offsite_password", "p")):
        monkeypatch.setattr(settings, field, value)
    with pytest.raises(ValueError, match="encrypted"):
        upload_offsite(plain)
    encrypted = tmp_path / "some-backup-20260101T000000Z.zip.enc"
    encrypted.write_bytes(Fernet(Fernet.generate_key()).encrypt(b"data"))
    calls = []
    import httpx

    monkeypatch.setattr(httpx, "put", lambda url, content, auth, timeout: calls.append(url) or SimpleNamespace(raise_for_status=lambda: None))
    monkeypatch.setattr(httpx, "head", lambda url, auth, timeout: SimpleNamespace(raise_for_status=lambda: None, headers={"content-length": str(encrypted.stat().st_size)}))
    assert upload_offsite(encrypted)["status"] == "uploaded" and calls[0].endswith(encrypted.name)


def test_operations_page_retry_and_produce_routes(db, tmp_path, monkeypatch):
    from app.db.session import get_db
    from app.main import app

    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    (tmp_path / "media-plans" / "pilot").mkdir(parents=True)
    (tmp_path / "media-plans" / "pilot" / "plan.json").write_text("{}")
    db.add(AuthUser(username="owner", password_hash=PasswordHasher().hash("a-secure-test-password")))
    db.add(Topic(niche="gaming", language="en", title="Topic"))
    db.commit()
    enqueue(db, "metrics", {}, "web-retry", max_attempts=1)
    job = claim(db, "w")
    fail(db, job, "ValueError:x")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://testserver")
    client.post("/login", data={"username": "owner", "password": "a-secure-test-password"})
    page = client.get("/operations")
    assert page.status_code == 200 and "Prøv igen" in page.text and "pilot/plan.json" in page.text
    csrf = page.text.split('name="csrf_token" value="')[1].split('"')[0]
    assert client.post(f"/jobs/{job.id}/retry", data={"csrf_token": csrf}, follow_redirects=False).status_code == 303
    assert db.get(Job, job.id).status == "QUEUED"
    assert client.post("/jobs/produce", data={"csrf_token": csrf, "topic_id": 1, "media_plan": "../x.json"}, follow_redirects=False).status_code == 422
    assert client.post("/jobs/produce", data={"csrf_token": csrf, "topic_id": 1, "media_plan": "pilot/plan.json"}, follow_redirects=False).status_code == 303
    produce_job = db.query(Job).filter(Job.kind == "produce").one()
    assert produce_job.payload["dry_run"] is True
    assert client.post("/timelog", data={"csrf_token": csrf, "story_key": "GI001-x", "step": "mobygames", "minutes": 25}, follow_redirects=False).status_code == 303
    assert client.post("/timelog", data={"csrf_token": csrf, "story_key": "GI001-x", "step": "napping", "minutes": 25}, follow_redirects=False).status_code == 422
    assert "mobygames" in client.get("/operations").text
    app.dependency_overrides.clear()
