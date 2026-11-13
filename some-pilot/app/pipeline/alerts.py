"""Operational alerts: immediate notices and a daily digest.

Channels are optional and off until configured: a generic JSON webhook
(Discord/Slack-compatible "content"/"text" fields) and/or SMTP e-mail. Messages
are redacted and never contain secrets. The same alert code is not resent
within ALERT_REPEAT_HOURS.
"""

import json
import shutil
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Cost, Job, Publication, Setting
from app.pipeline.redact import redact

SENT_KEY = "alerts_sent"


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def collect_alerts(db: Session, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    settings = get_settings()
    alerts = []
    day_ago = now - timedelta(hours=24)
    failed = [job for job in db.query(Job).filter(Job.status == "FAILED").all() if job.finished_at is None or _utc(job.finished_at) >= day_ago]
    for job in failed[:20]:
        alerts.append({"severity": "error", "code": f"job_failed:{job.kind}:{job.id[:8]}", "message": f"Job {job.kind} failed after {job.attempts} attempts: {job.error_code}"})
    for publication in db.query(Publication).filter(Publication.status == "RECONCILE_REQUIRED").all():
        alerts.append({"severity": "error", "code": f"reconcile:{publication.id}", "message": f"{publication.platform} publication {publication.id} needs manual reconciliation ({publication.error_code})."})
    disk = shutil.disk_usage(settings.data_dir)
    used = disk.used / disk.total
    if used >= 0.80:
        alerts.append({"severity": "error" if used >= 0.90 else "warning", "code": "disk_usage", "message": f"Disk usage is {used:.0%}; rendering stops at 90 %."})
    backups = [job for job in db.query(Job).filter(Job.kind == "backup").all() if job.status in {"SUCCEEDED", "FAILED"}]
    latest_backup = max(backups, key=lambda job: _utc(job.updated_at), default=None)
    if latest_backup is None or latest_backup.status == "FAILED" or _utc(latest_backup.updated_at) < now - timedelta(hours=36):
        alerts.append({"severity": "error", "code": "backup_stale_or_failed", "message": "No successful verified backup in the last 36 hours."})
    heartbeat = db.get(Setting, "worker_heartbeat")
    if heartbeat is None or datetime.fromisoformat(heartbeat.value_json["at_utc"]) < now - timedelta(minutes=10):
        alerts.append({"severity": "error", "code": "worker_heartbeat_stale", "message": "The worker has not reported a heartbeat for 10 minutes."})
    accounts = db.get(Setting, "account_status")
    for platform, status in ((accounts.value_json if accounts else {}).get("platforms", {})).items():
        if status.get("configured") and not status.get("ok"):
            alerts.append({"severity": "error", "code": f"account:{platform}", "message": f"{platform} connection check failed: {status.get('error_code')}"})
        elif status.get("expires_in_days") is not None and status["expires_in_days"] <= 2:
            alerts.append({"severity": "warning", "code": f"token_expiry:{platform}", "message": f"{platform} token expires in {status['expires_in_days']} day(s)."})
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = sum(row.actual_amount if row.actual_amount is not None else row.estimated_amount for row in db.query(Cost).all() if _utc(row.created_at) >= month_start)
    if spent >= 0.8 * settings.monthly_ai_budget_dkk:
        alerts.append({"severity": "warning", "code": "ai_budget", "message": f"AI/voice spend this month is {spent:.2f} DKK of {settings.monthly_ai_budget_dkk:.0f} DKK."})
    governance = db.get(Setting, "learning_governance")
    for event in (governance.value_json.get("events", []) if governance else [])[-5:]:
        if event.get("action") == "LEARNING_MODEL_ROLLED_BACK" and datetime.fromisoformat(event["at"]) >= day_ago:
            alerts.append({"severity": "warning", "code": f"learning_rollback:{event.get('version')}", "message": "The learning model was rolled back after two weekly declines."})
    for alert in alerts:
        alert["message"] = redact(alert["message"])
    return alerts


def channels_configured() -> dict:
    settings = get_settings()
    return {"webhook": bool(settings.alert_webhook_url), "email": bool(settings.alert_smtp_host and settings.alert_email_from and settings.alert_email_to)}


def _send(subject: str, body: str) -> list[str]:
    settings = get_settings()
    sent = []
    if settings.alert_webhook_url:
        text = f"**{subject}**\n{body}"[:1900]
        response = httpx.post(settings.alert_webhook_url, json={"content": text, "text": text}, timeout=15)
        response.raise_for_status()
        sent.append("webhook")
    if settings.alert_smtp_host and settings.alert_email_from and settings.alert_email_to:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.alert_email_from
        message["To"] = settings.alert_email_to
        message.set_content(body)
        with smtplib.SMTP(settings.alert_smtp_host, settings.alert_smtp_port, timeout=20) as client:
            client.starttls()
            if settings.alert_smtp_user:
                client.login(settings.alert_smtp_user, settings.alert_smtp_password)
            client.send_message(message)
        sent.append("email")
    return sent


def notify(db: Session, alerts: list[dict], subject: str, now: datetime | None = None, force: bool = False) -> dict:
    """Send alerts not sent within the repeat window. Returns what happened, never raises on channel errors."""
    now = now or datetime.now(timezone.utc)
    settings = get_settings()
    state = db.get(Setting, SENT_KEY)
    sent_at = dict(state.value_json) if state else {}
    window = timedelta(hours=settings.alert_repeat_hours)
    fresh = [alert for alert in alerts if force or alert["code"] not in sent_at or datetime.fromisoformat(sent_at[alert["code"]]) < now - window]
    if not fresh:
        return {"sent": [], "alerts": 0, "suppressed": len(alerts)}
    if not any(channels_configured().values()):
        return {"sent": [], "alerts": len(fresh), "status": "no_channel_configured"}
    body = "\n".join(f"[{alert['severity'].upper()}] {alert['message']}" for alert in fresh)
    try:
        channels = _send(subject, redact(body))
    except Exception as exc:
        return {"sent": [], "alerts": len(fresh), "status": "channel_error", "error": type(exc).__name__}
    for alert in fresh:
        sent_at[alert["code"]] = now.isoformat()
    db.merge(Setting(key=SENT_KEY, value_json=sent_at))
    db.commit()
    return {"sent": channels, "alerts": len(fresh)}


def daily_digest(db: Session, now: datetime | None = None) -> dict:
    alerts = collect_alerts(db, now)
    if not alerts:
        return {"alerts": 0, "sent": []}
    return {**notify(db, alerts, f"SoMe-maskinen: {len(alerts)} driftsadvarsel(er)", now, force=True), "codes": [alert["code"] for alert in alerts]}


def immediate(db: Session, severity: str, code: str, message: str) -> dict:
    return notify(db, [{"severity": severity, "code": code, "message": redact(message)}], f"SoMe-maskinen: {code}")


def status_json(db: Session) -> str:
    return json.dumps({"channels": channels_configured(), "alerts": collect_alerts(db)}, ensure_ascii=False)
