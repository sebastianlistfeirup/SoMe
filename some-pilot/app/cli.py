import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from sqlalchemy import text

from app.adapters.fixtures import FixtureAdapter
from app.adapters.youtube import YouTubeAdapter
from app.config import get_settings
from app.db.models import AuthUser, Topic
from app.db.session import SessionLocal, init_database
from app.pipeline.ai import claude_reply_text
from app.pipeline.approvals import approve, set_pause
from app.pipeline.backup import create_backup, restore_to_directory
from app.pipeline.costs import monthly_total, reserve, settle
from app.pipeline.jobs import recover_expired_leases
from app.pipeline.learning import weekly_learning
from app.pipeline.media import require_tools
from app.pipeline.metrics import collect_due, import_csv
from app.pipeline.platforms import FacebookPublisher, InstagramPublisher, TikTokPublisher, YouTubePublisher, manual_export
from app.pipeline.production import produce
from app.pipeline.research import export_observations, import_report, run_adapters


def result_file(db, command_name: str, payload: dict, output: str | None = None) -> Path:
    settings = get_settings()
    target = Path(output) if output else settings.data_dir / "results" / f"{command_name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return target


def _alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))


def migrate() -> None:
    command.upgrade(_alembic_config(), "head")


def expected_migration() -> str:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(_alembic_config()).get_current_head()


def doctor(db, paid_check: bool = False) -> dict:
    settings = get_settings()
    tools = {}
    for tool in ("ffmpeg", "ffprobe", "espeak-ng"):
        tools[tool] = bool(shutil.which(tool))
    disk = shutil.disk_usage(settings.data_dir)
    try:
        migration_version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        migration_version = None
    checks = {
        "database": "ok",
        "migration": {"current": migration_version, "expected": expected_migration(), "ok": migration_version == expected_migration()},
        "tools": tools,
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free, "used_percent": round(disk.used / disk.total * 100, 2), "alarm": disk.used / disk.total > 0.8, "stop_render": disk.used / disk.total > 0.9},
        "model_cache": {"path": str(settings.model_cache_dir), "whisper_small_cached": (settings.model_cache_dir / "whisper").exists()},
        "budget": {"monthly_limit_dkk": settings.monthly_ai_budget_dkk, "monthly_reserved_or_actual_dkk": monthly_total(db), "paid_jobs_enabled": settings.paid_jobs_enabled},
        "safety": {"dry_run": settings.dry_run, "publish_enabled": settings.publish_enabled, "paid_jobs_enabled": settings.paid_jobs_enabled},
        "integrations": {"youtube": YouTubePublisher().capabilities(db), "instagram": InstagramPublisher().capabilities(db), "facebook": FacebookPublisher().capabilities(db), "tiktok": TikTokPublisher().capabilities(db), "youtube_research": YouTubeAdapter().capabilities(), "qwen_vision": {"model": settings.qwen_model_vision, "api_key_configured": bool(settings.dashscope_api_key), "workspace_configured": bool(settings.qwen_workspace_id), "pricing_configured": settings.qwen_input_dkk_per_million > 0 and settings.qwen_output_dkk_per_million > 0}, "claude": {"script_model": settings.claude_model_text, "research_model": settings.claude_model_research, "api_key_configured": bool(settings.anthropic_api_key), "script_pricing_configured": settings.claude_input_dkk_per_million > 0 and settings.claude_output_dkk_per_million > 0, "research_pricing_configured": settings.claude_research_input_dkk_per_million > 0 and settings.claude_research_output_dkk_per_million > 0}, "voice": {"provider": settings.voice_provider, "production_provider": "elevenlabs", "demo_provider": settings.demo_voice_provider, "demo_only_rejected_for_publication": settings.demo_voice_provider in {"kokoro", "espeak-ng"}, "local_available": settings.demo_voice_provider == "kokoro", "elevenlabs_configured": bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id and settings.elevenlabs_cost_per_1000_chars_dkk > 0 and settings.elevenlabs_pricing_verified_at and settings.elevenlabs_voice_rights_confirmed), "avatar_required": False}},
        "paid_api_test": "not_run",
    }
    checks["overall"] = "render_blocked_disk" if checks["disk"]["stop_render"] else "ok_demo" if all(tools.values()) else "setup_required"
    if paid_check:
        if not settings.paid_jobs_enabled:
            raise RuntimeError("paid_check_requires_paid_jobs_enabled")
        if settings.claude_input_dkk_per_million <= 0 or settings.claude_output_dkk_per_million <= 0:
            raise RuntimeError("verified_model_pricing_required")
        reservation = reserve(db, f"doctor-{uuid.uuid4()}", "claude_doctor", settings.max_job_ai_cost_dkk)
        from anthropic import Anthropic
        client = Anthropic(api_key=settings.anthropic_api_key, max_retries=0)
        try:
            reply = client.messages.create(model=settings.claude_model_text, max_tokens=32, messages=[{"role": "user", "content": "Svar kun: OK"}])
        except Exception:
            settle(db, reservation, settings.max_job_ai_cost_dkk, uncertain=True)
            raise
        actual = (reply.usage.input_tokens * settings.claude_input_dkk_per_million + reply.usage.output_tokens * settings.claude_output_dkk_per_million) / 1_000_000
        settle(db, reservation, actual, reply.usage.input_tokens, reply.usage.output_tokens)
        checks["paid_api_test"] = {"reply": claude_reply_text(reply), "input_tokens": reply.usage.input_tokens, "output_tokens": reply.usage.output_tokens}
    return checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    sub.add_parser("init-db")
    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument("--paid-check", action="store_true")
    research = sub.add_parser("research")
    research.add_argument("--days", type=int, default=30)
    research.add_argument("--output", default="./data/reports")
    research.add_argument("--demo", action="store_true")
    research.add_argument("--import-report")
    produce_parser = sub.add_parser("produce")
    produce_parser.add_argument("--topic-id", type=int, required=True)
    produce_parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    produce_parser.add_argument("--media-plan", type=Path, required=True)
    ranking_parser = sub.add_parser("ranking")
    ranking_parser.add_argument("--plan", required=True)
    ranking_parser.add_argument("--output", required=True)
    ranking_parser.add_argument("--platform", choices=["tiktok", "reels", "youtube"], default="reels")
    ranking_parser.add_argument("--mobile-style", choices=["zoom", "safe"], default="zoom")
    ranking_parser.add_argument("--voice-provider", choices=["kokoro", "elevenlabs"], default="elevenlabs")
    metrics = sub.add_parser("metrics")
    metrics.add_argument("--due", action="store_true")
    metrics.add_argument("--import-csv")
    metrics.add_argument("--demo", action="store_true")
    learn = sub.add_parser("learn")
    learn.add_argument("--weekly", action="store_true")
    learn.add_argument("--demo", action="store_true")
    backup = sub.add_parser("backup")
    backup.add_argument("--verify", action="store_true")
    pause = sub.add_parser("pause")
    pause.add_argument("--all", action="store_true")
    sub.add_parser("resume")
    demo = sub.add_parser("demo")
    demo.add_argument("--produce", action="store_true")
    demo.add_argument("--media-plan", type=Path)
    approve_parser = sub.add_parser("approve")
    approve_parser.add_argument("--video-id", type=int, required=True)
    approve_parser.add_argument("--reviewer", required=True)
    approve_parser.add_argument("--platform", default="youtube")
    approve_parser.add_argument("--account", required=True)
    approve_parser.add_argument("--watched-full-video", action="store_true")
    export = sub.add_parser("export")
    export.add_argument("--video-id", type=int, required=True)
    export.add_argument("--platform", default="youtube")
    publish = sub.add_parser("publish")
    publish.add_argument("--video-id", type=int, required=True)
    publish.add_argument("--platform", choices=["youtube", "instagram", "facebook", "tiktok"], required=True)
    publish.add_argument("--account", required=True)
    publish.add_argument("--privacy", default="private")
    restore = sub.add_parser("restore")
    restore.add_argument("--input", required=True)
    restore.add_argument("--target", required=True)
    sub.add_parser("recover-jobs")
    user = sub.add_parser("init-user")
    user.add_argument("--username", default="owner")
    experiment = sub.add_parser("experiment", help="Pre-registered one-variable experiments")
    experiment.add_argument("action", choices=["create", "list", "assign", "evaluate", "stop"])
    experiment.add_argument("--spec", type=Path, help="JSON spec for create")
    experiment.add_argument("--id", type=int)
    experiment.add_argument("--story", help="Story key (packet story_id) for assign")
    experiment.add_argument("--reason", default="")
    sub.add_parser("scorecard", help="Weekly scorecard and learning-model governance state")
    ideas = sub.add_parser("ideas", help="Rank the Content Bible idea bank (80 %% exploit / 20 %% explore)")
    ideas.add_argument("--next", type=int, default=10)
    ideas.add_argument("--lane", choices=["gaming", "ai", "crossover"])
    sub.add_parser("calibration", help="Compare predicted and independent quality scores with outcomes")
    return parser


def run_extended(db, args) -> dict | None:
    """Commands added after the original CLI contract; returns None when not handled."""
    if args.command == "experiment":
        from app.db.models import Experiment
        from app.pipeline.experiments import ExperimentSpec, assign_variant, create_experiment, evaluate_experiment, stop_experiment

        if args.action == "create":
            if not args.spec:
                raise ValueError("experiment_spec_required")
            spec = ExperimentSpec.model_validate_json(args.spec.read_text(encoding="utf-8"))
            experiment = create_experiment(db, spec)
            return {"experiment_id": experiment.id, "spec_sha256": experiment.spec_sha256, "status": experiment.status}
        if args.action == "list":
            return {"experiments": [{"id": item.id, "name": item.name, "status": item.status, "variable": (item.spec_json or {}).get("variable"), "decision": item.decision, "samples": (item.results_json or {}).get("samples")} for item in db.query(Experiment).order_by(Experiment.id).all()]}
        if args.id is None:
            raise ValueError("experiment_id_required")
        if args.action == "assign":
            if not args.story:
                raise ValueError("experiment_story_required")
            return assign_variant(db, args.id, args.story)
        if args.action == "evaluate":
            return evaluate_experiment(db, args.id)
        experiment = stop_experiment(db, args.id, args.reason)
        return {"experiment_id": experiment.id, "status": experiment.status, "decision": experiment.decision}
    if args.command == "ideas":
        from app.pipeline.ideas import rank_ideas

        return {"ideas": rank_ideas(db, args.next, args.lane)}
    if args.command == "calibration":
        from app.pipeline.quality import calibration_report, rejection_category_counts

        return {"calibration": calibration_report(db), "rejection_categories_28d": rejection_category_counts(db)}
    if args.command == "scorecard":
        from app.db.models import Setting
        from app.pipeline.governance import GOVERNANCE_KEY, scorecard

        state = db.get(Setting, GOVERNANCE_KEY)
        value = state.value_json if state else {}
        return {"scorecard": scorecard(db), "active_version": (value.get("active") or {}).get("version"), "candidate_version": (value.get("candidate") or {}).get("version"), "recent_events": value.get("events", [])[-10:]}
    return None


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    init_database()
    db = SessionLocal()
    try:
        payload = {}
        extended = run_extended(db, args)
        if extended is not None:
            payload = extended
        elif args.command == "migrate":
            migrate()
            payload = {"status": "migrated"}
        elif args.command == "init-db":
            payload = {"status": "initialized"}
        elif args.command == "doctor":
            payload = doctor(db, args.paid_check)
        elif args.command == "research":
            if args.import_report:
                payload = import_report(db, Path(args.import_report))
            elif args.demo:
                fixture = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "research.json"
                adapter = FixtureAdapter(fixture)
                payload = run_adapters(db, [adapter], ["demo"], ["en"], args.days, Path(args.output))
            else:
                adapters = [YouTubeAdapter()] if settings.youtube_api_key else []
                if not adapters:
                    payload = {"status": "no_real_adapters_configured", "observations": 0, "next": "Configure YouTube API or use --demo; demo is never real research."}
                else:
                    from app.pipeline.research import bible_research

                    payload = bible_research(db, Path(args.output), adapters, days=args.days)
        elif args.command == "produce":
            video = produce(db, args.topic_id, args.dry_run, args.media_plan)
            payload = {"video_id": video.id, "status": video.status, "output_dir": video.output_dir, "demo": args.dry_run}
        elif args.command == "ranking":
            from app.pipeline.production_ranking import produce_ranking
            payload = produce_ranking(db, Path(args.plan), Path(args.output), args.platform, args.mobile_style, args.voice_provider)
        elif args.command == "metrics":
            payload = import_csv_result(db, args)
        elif args.command == "learn":
            payload = weekly_learning(db, is_demo=args.demo)
        elif args.command == "backup":
            payload = create_backup(db, verify=args.verify)
        elif args.command == "pause":
            set_pause(db, True, "cli-owner")
            payload = {"paused": True}
        elif args.command == "resume":
            set_pause(db, False, "cli-owner")
            payload = {"paused": False}
        elif args.command == "demo":
            if args.produce and not args.media_plan:
                raise ValueError("real_media_plan_required")
            topic = Topic(niche="demo_handhelds", language="en", title="DEMO: A practical checklist for choosing a gaming handheld", score_json={"demo": True})
            db.add(topic)
            db.commit()
            db.refresh(topic)
            payload = {"topic_id": topic.id, "demo": True}
            if args.produce:
                video = produce(db, topic.id, True, args.media_plan)
                payload.update({"video_id": video.id, "status": video.status, "output_dir": video.output_dir})
        elif args.command == "approve":
            from app.db.models import VideoVersion
            video = db.get(VideoVersion, args.video_id)
            if not video:
                raise ValueError("video_not_found")
            review = approve(db, video, args.reviewer, args.platform, args.account, args.watched_full_video)
            payload = {"review_id": review.id, "status": video.status, "approval_sha256": review.digest_json["approval_sha256"]}
        elif args.command == "export":
            from app.db.models import VideoVersion
            video = db.get(VideoVersion, args.video_id)
            if not video:
                raise ValueError("video_not_found")
            payload = {"export": str(manual_export(video, args.platform, settings.data_dir)), "published": False}
        elif args.command == "publish":
            from app.db.models import VideoVersion
            video = db.get(VideoVersion, args.video_id)
            if not video:
                raise ValueError("video_not_found")
            if args.platform == "youtube":
                publication = YouTubePublisher().publish(db, video, args.account, args.privacy)
            elif args.platform == "instagram":
                publication = InstagramPublisher().publish(db, video, args.account)
            elif args.platform == "facebook":
                publication = FacebookPublisher().publish(db, video, args.account)
            else:
                publication = TikTokPublisher().publish(db, video, args.account)
            payload = {"publication_id": publication.id, "status": publication.status, "remote_id": publication.remote_id}
        elif args.command == "restore":
            payload = restore_to_directory(Path(args.input), Path(args.target))
        elif args.command == "recover-jobs":
            payload = {"recovered": recover_expired_leases(db)}
        elif args.command == "init-user":
            password = os.environ.get("APP_ADMIN_PASSWORD", "")
            if len(password) < 14:
                raise ValueError("APP_ADMIN_PASSWORD_must_have_at_least_14_characters")
            if db.query(AuthUser).filter(AuthUser.username == args.username).first():
                raise ValueError("user_exists")
            db.add(AuthUser(username=args.username, password_hash=PasswordHasher().hash(password)))
            db.commit()
            payload = {"username": args.username, "created": True}
        output = result_file(db, args.command, payload)
        print(json.dumps({"ok": True, "result": payload, "result_file": str(output)}, ensure_ascii=False, default=str))
        return 0
    except Exception as exc:
        db.rollback()
        payload = {"ok": False, "command": args.command, "error_code": type(exc).__name__, "message": str(exc)[:500]}
        output = result_file(db, args.command, payload)
        print(json.dumps({**payload, "result_file": str(output)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        db.close()


def import_csv_result(db, args) -> dict:
    if args.import_csv:
        return {"imported": import_csv(db, Path(args.import_csv), is_demo=args.demo)}
    if args.due:
        return collect_due(db)
    raise ValueError("use_due_or_import_csv")


if __name__ == "__main__":
    raise SystemExit(main())
