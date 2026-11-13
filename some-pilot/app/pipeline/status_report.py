"""Generate the factual part of STATUS from doctor and a test result.

Numbers that used to be hand-copied into five documents (test count, migration,
safety flags, integrations) come from one generator. Narrative history belongs in
TEST_PROTOCOL.md (changelog) and architecture in CLAUDE_HANDOFF.md.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Experiment, Setting


def collect_status(db: Session, tests_passed: int, environment: str, commit: str | None = None) -> dict:
    from app.cli import doctor
    from app.pipeline.alerts import collect_alerts

    report = doctor(db)
    settings = get_settings()
    integrations = report.get("integrations", {})
    governance = db.get(Setting, "learning_governance")
    accounts = db.get(Setting, "account_status")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": environment,
        "commit": commit or os.environ.get("IMAGE_TAG") or "unknown",
        "tests_passed": tests_passed,
        "migration": report.get("migration"),
        "safety": {"DRY_RUN": settings.dry_run, "PUBLISH_ENABLED": settings.publish_enabled, "PAID_JOBS_ENABLED": settings.paid_jobs_enabled, "WORKER_CONCURRENCY": settings.worker_concurrency},
        "publishing": {name: {key: value for key, value in (integrations.get(name) or {}).items() if key in {"publishing_configured", "oauth_verified", "direct_post_eligible", "direct_post_blocker"}} for name in ("youtube", "instagram", "facebook", "tiktok")},
        "voice": {key: (integrations.get("voice") or {}).get(key) for key in ("production_provider", "demo_provider", "elevenlabs_configured")},
        "learning": {"active_model_version": ((governance.value_json if governance else {}).get("active") or {}).get("version"), "active_experiments": db.query(Experiment).filter(Experiment.status == "ACTIVE").count()},
        "accounts_ok": {name: status.get("ok") for name, status in ((accounts.value_json if accounts else {}).get("platforms", {})).items()},
        "open_alerts": [alert["code"] for alert in collect_alerts(db)],
    }


def render_markdown(status: dict) -> str:
    def yes(value):
        return "ja" if value else "nej"

    lines = [
        "SoMe-maskinen — STATUS (genereret)",
        f"Genereret: {status['generated_at']} · miljø: {status['environment']} · commit: {status['commit']}",
        "Genereres med: python -m app.cli status-report --tests-passed <N> --environment <local|vps>",
        "Arkitektur og regler: CLAUDE_HANDOFF.md · historik: TEST_PROTOCOL.md (changelog)",
        "",
        "FAKTA",
        f"- Testpakke: {status['tests_passed']} bestået",
        f"- Migration: {status['migration'].get('current')} (forventet {status['migration'].get('expected')}, ok={yes(status['migration'].get('ok'))})",
        "- Sikkerhed: " + ", ".join(f"{key}={value}" for key, value in status["safety"].items()),
        "- Stemme: produktion=" + str(status["voice"].get("production_provider")) + ", kun demo=" + str(status["voice"].get("demo_provider")) + ", ElevenLabs konfigureret=" + yes(status["voice"].get("elevenlabs_configured")),
        "",
        "PUBLICERING",
    ]
    for name, values in status["publishing"].items():
        lines.append(f"- {name}: " + ", ".join(f"{key}={value}" for key, value in values.items()))
    lines += ["", "LÆRING", f"- Aktiv læringsmodel: {status['learning']['active_model_version'] or 'ingen endnu'}", f"- Aktive eksperimenter: {status['learning']['active_experiments']}", "", "DRIFT"]
    lines.append("- Kontotjek: " + (", ".join(f"{name}={'ok' if ok else 'fejl'}" for name, ok in status["accounts_ok"].items()) or "ikke kørt endnu"))
    lines.append("- Åbne advarsler: " + (", ".join(status["open_alerts"]) or "ingen"))
    lines += ["", "Ingen garanti for vækst, likes, subscribers eller fejlfri drift."]
    return "\n".join(lines) + "\n"


def write_status(db: Session, tests_passed: int, environment: str, output: Path | None = None, commit: str | None = None) -> dict:
    status = collect_status(db, tests_passed, environment, commit)
    output = output or get_settings().data_dir / "reports" / "STATUS.generated.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(status), encoding="utf-8")
    return {**status, "written_to": str(output)}
