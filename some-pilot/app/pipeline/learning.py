import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MetricSnapshot, Observation, Publication, Setting, VideoVersion


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _group_rows(db: Session, is_demo: bool, age_days: int = 7) -> dict[str, list[float]]:
    groups: dict[str, list[float]] = defaultdict(list)
    snapshots = db.query(MetricSnapshot).filter(MetricSnapshot.is_demo == is_demo, MetricSnapshot.metric_name == "views", MetricSnapshot.metric_value.isnot(None)).all()
    for snap in snapshots:
        publication = db.get(Publication, snap.publication_id)
        if not publication or not publication.published_at:
            continue
        video = db.get(VideoVersion, publication.video_version_id)
        if not video:
            continue
        actual_age = (_utc(snap.collected_at) - _utc(publication.published_at)).total_seconds() / 86400
        if abs(actual_age - age_days) > 0.75:
            continue
        length = video.duration_seconds or 0
        bucket = "short" if length <= 35 else "medium" if length <= 60 else "long"
        key = f"{publication.platform}|{video.format}|{video.hook_type}|{bucket}"
        groups[key].append(float(snap.metric_value))
    return groups


def weekly_learning(db: Session, output_dir: Path | None = None, is_demo: bool = False) -> dict:
    settings = get_settings()
    output_dir = output_dir or settings.data_dir / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    groups = _group_rows(db, is_demo)
    all_values = [value for values in groups.values() for value in values]
    overall = statistics.median(all_values) if all_values else None
    summaries = []
    for key, values in sorted(groups.items()):
        ordered = sorted(values)
        q1 = statistics.median(ordered[: len(ordered) // 2]) if len(ordered) > 1 else None
        q3 = statistics.median(ordered[(len(ordered) + 1) // 2 :]) if len(ordered) > 1 else None
        summaries.append({"group": key, "sample_size": len(values), "median_views": statistics.median(values), "q1": q1, "q3": q3, "min": min(values), "max": max(values)})
    setting_key = "learning_model_demo" if is_demo else "learning_model"
    previous = db.get(Setting, setting_key)
    version = int(previous.value_json.get("version", 0)) + 1 if previous else 1
    multipliers = previous.value_json.get("hook_multipliers", {}) if previous else {}
    updates = []
    if overall:
        for row in summaries:
            if row["sample_size"] < 2:
                continue
            hook = row["group"].split("|")[2]
            raw = row["median_views"] / overall if overall > 0 else 1
            shrink = row["sample_size"] / (row["sample_size"] + 5)
            target = 1 + (raw - 1) * shrink
            bounded = max(0.75, min(1.25, target))
            multipliers[hook] = round(bounded, 4)
            updates.append({"hook": hook, "multiplier": multipliers[hook], "sample_size": row["sample_size"], "reason": "Shrunk seven-day within-group median ratio; correlation only."})
    model = Setting(key=setting_key, value_json={"version": version, "hook_multipliers": multipliers, "experiment_allocation": {"known_formats": 0.8, "new_experiments": 0.2}, "last_updated_utc": datetime.now(timezone.utc).isoformat(), "data_mode": "demo" if is_demo else "real", "updates": updates})
    db.merge(model)
    db.commit()
    prompt_dir = settings.data_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    mode = "demo" if is_demo else "real"
    prompt_document = {"version": f"learning-{mode}-v{version}", "base_prompt_version": "claude-json-v2-controlled", "created_at_utc": datetime.now(timezone.utc).isoformat(), "data_mode": mode, "hook_multipliers": multipliers, "updates": updates, "editorial_guidance": "Prefer evidence-supported hooks with higher damped multipliers; preserve factual, rights and safety constraints.", "rollback": "Select any earlier prompt JSON explicitly; no automatic code or policy change."}
    (prompt_dir / f"script-learning-{mode}-v{version}.json").write_text(json.dumps(prompt_document, indent=2, ensure_ascii=False), encoding="utf-8")
    external = db.query(Observation).filter(Observation.is_demo == is_demo, Observation.metric_name.in_(["views", "views_approximate"]), Observation.metric_value.isnot(None)).all()
    external_groups: dict[str, list[float]] = defaultdict(list)
    for row in external:
        external_groups[row.topic.split(":", 1)[0]].append(float(row.metric_value))
    external_summary = [{"topic": key, "sample_size": len(values), "median_views": statistics.median(values), "limitations": "Mixed platforms/channels and collection methods; inspiration signal, not causal benchmark."} for key, values in external_groups.items()]
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_mode": "demo" if is_demo else "real",
        "comparison": "Views at approximately seven days, grouped by platform, format, hook and length bucket",
        "observed": summaries,
        "external_content_signals": external_summary,
        "possible_explanations": ["Hook, topic, packaging and channel fit may contribute; this sample cannot establish causality."],
        "uncertainty": "Small organic samples, unknown traffic sources and algorithm changes limit conclusions.",
        "repeat": "Retain formats with repeatable within-group results; do not scale on one viral post.",
        "next_experiment": "Test one opening variation while holding topic, platform, format and approximate length constant.",
        "model_version": version,
        "model_updates": updates,
    }
    date = datetime.now(timezone.utc).date().isoformat()
    json_path = output_dir / f"learning-{mode}-{date}-v{version}.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Weekly learning — {date} — model v{version}", "", f"Data mode: {'DEMO' if is_demo else 'REAL'}", "", "## Observed"]
    lines.extend(f"- {row['group']}: n={row['sample_size']}, median={row['median_views']:.1f}, range={row['min']:.1f}–{row['max']:.1f}" for row in summaries)
    lines += ["", "## Interpretation", "- Correlation only; no causal claim.", "- Repeat promising formats only after comparable results.", "", "## Next experiment", report["next_experiment"]]
    md_path = output_dir / f"learning-{mode}-{date}-v{version}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["files"] = {"json": str(json_path), "markdown": str(md_path)}
    return report
