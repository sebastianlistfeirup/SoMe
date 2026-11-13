import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Asset, MetricSnapshot, Observation, Publication, Setting, VideoVersion
from app.pipeline.stats import median_ci
from app.pipeline.taxonomy import normalize_hook


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


# Canonical metric names follow YouTube Analytics. Manual CSV imports from other
# platforms may use the aliases below; comparisons always stay within one platform group.
METRIC_ALIASES = {
    "views": "views",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "subscribersGained": "subscribersGained",
    "subscribers_gained": "subscribersGained",
    "followers_gained": "subscribersGained",
    "follows": "subscribersGained",
    "subscribersLost": "subscribersLost",
    "subscribers_lost": "subscribersLost",
    "followers_lost": "subscribersLost",
    "averageViewPercentage": "averageViewPercentage",
    "average_view_percentage": "averageViewPercentage",
    "averageViewDuration": "averageViewDuration",
    "average_view_duration": "averageViewDuration",
    "average_watch_time_seconds": "averageViewDuration",
    "estimatedMinutesWatched": "estimatedMinutesWatched",
    "estimated_minutes_watched": "estimatedMinutesWatched",
    "hookRetention3s": "hookRetention3s",
    "hook_retention_3s": "hookRetention3s",
    "introRetention": "introRetention",
}

# Explicit, versioned judgement weights. They express channel goals, not causal effects.
SIGNAL_WEIGHTS_VERSION = "learning-signals-v2"
SIGNAL_WEIGHTS = {
    "views_relative": 0.25,
    "retention_pct": 0.20,
    "net_subscribers_per_1k_views": 0.20,
    "hook_retention_3s": 0.15,
    "engagement_per_1k_views": 0.12,
    "watch_seconds_per_view": 0.08,
}
LEARNING_WINDOW_DAYS = 60
GROWTH_BASELINE_DAYS = 14
GROWTH_BASELINE_MIN = 3
MIN_SAMPLES = 2
MULTIPLIER_FLOOR = 0.75
MULTIPLIER_CEILING = 1.25


def _length_bucket(seconds: float) -> str:
    return "short" if seconds <= 35 else "medium" if seconds <= 60 else "long"


def _publication_metrics(db: Session, is_demo: bool, age_days: int, published_since: datetime | None = None, published_until: datetime | None = None) -> dict[int, dict[str, float]]:
    """One value per publication and metric: the snapshot closest to the target age (latest wins ties)."""
    chosen: dict[int, dict[str, tuple[float, datetime, float]]] = defaultdict(dict)
    snapshots = db.query(MetricSnapshot).filter(MetricSnapshot.is_demo == is_demo, MetricSnapshot.metric_name.in_(list(METRIC_ALIASES)), MetricSnapshot.metric_value.isnot(None)).all()
    published_cache: dict[int, datetime | None] = {}
    for snap in snapshots:
        if snap.publication_id not in published_cache:
            publication = db.get(Publication, snap.publication_id)
            published_cache[snap.publication_id] = _utc(publication.published_at) if publication and publication.published_at else None
        published_at = published_cache[snap.publication_id]
        if published_at is None:
            continue
        if (published_since and published_at < published_since) or (published_until and published_at > published_until):
            continue
        collected = _utc(snap.collected_at)
        distance = abs((collected - published_at).total_seconds() / 86400 - age_days)
        if distance > 0.75:
            continue
        name = METRIC_ALIASES[snap.metric_name]
        current = chosen[snap.publication_id].get(name)
        if current is None or distance < current[0] or (distance == current[0] and collected > current[1]):
            chosen[snap.publication_id][name] = (distance, collected, float(snap.metric_value))
    return {pub_id: {name: item[2] for name, item in metrics.items()} for pub_id, metrics in chosen.items()}


def _signals(metrics: dict[str, float]) -> dict[str, float]:
    signals: dict[str, float] = {}
    views = metrics.get("views")
    if views is not None:
        signals["views"] = views
    if metrics.get("averageViewPercentage") is not None:
        signals["retention_pct"] = metrics["averageViewPercentage"]
    if metrics.get("hookRetention3s") is not None:
        signals["hook_retention_3s"] = metrics["hookRetention3s"]
    if metrics.get("averageViewDuration") is not None:
        signals["watch_seconds_per_view"] = metrics["averageViewDuration"]
    elif metrics.get("estimatedMinutesWatched") is not None and views:
        signals["watch_seconds_per_view"] = metrics["estimatedMinutesWatched"] * 60 / views
    if views and views > 0:
        interactions = [metrics[name] for name in ("likes", "comments", "shares") if metrics.get(name) is not None]
        if interactions:
            signals["engagement_per_1k_views"] = sum(interactions) * 1000 / views
        if metrics.get("subscribersGained") is not None:
            net = metrics["subscribersGained"] - (metrics.get("subscribersLost") or 0)
            signals["net_subscribers_per_1k_views"] = net * 1000 / views
    return signals


def _growth_baselines(rows: list[tuple[Publication, dict[str, float]]]) -> dict[int, float]:
    """Channel-level views baseline per publication: median views of the same platform
    published within +/- GROWTH_BASELINE_DAYS (falls back to the platform window median).

    Dividing by it removes most of the "newer videos get more views because the
    channel grew" effect before hooks are compared.
    """
    baselines: dict[int, float] = {}
    by_platform: dict[str, list[tuple[datetime, float, int]]] = defaultdict(list)
    for publication, metrics in rows:
        if metrics.get("views") is not None:
            by_platform[publication.platform].append((_utc(publication.published_at), metrics["views"], publication.id))
    for items in by_platform.values():
        platform_median = statistics.median(value for _when, value, _id in items)
        for when, _value, publication_id in items:
            near = [value for other, value, _other_id in items if abs((other - when).total_seconds()) <= GROWTH_BASELINE_DAYS * 86400]
            baseline = statistics.median(near) if len(near) >= GROWTH_BASELINE_MIN else platform_median
            if baseline > 0:
                baselines[publication_id] = baseline
    return baselines


def _group_rows(db: Session, is_demo: bool, age_days: int = 7, now: datetime | None = None, window_days: int | None = LEARNING_WINDOW_DAYS) -> dict[str, dict[str, list[float]]]:
    now = _utc(now or datetime.now(timezone.utc))
    since = now - timedelta(days=window_days) if window_days else None
    rows = []
    for publication_id, metrics in sorted(_publication_metrics(db, is_demo, age_days, since, now).items()):
        publication = db.get(Publication, publication_id)
        if publication is not None:
            rows.append((publication, metrics))
    baselines = _growth_baselines(rows)
    groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for publication, metrics in rows:
        video = db.get(VideoVersion, publication.video_version_id)
        if not video:
            continue
        key = f"{publication.platform}|{video.format}|{normalize_hook(video.hook_type, strict=False)}|{_length_bucket(video.duration_seconds or 0)}"
        signals = _signals(metrics)
        if "views" in signals and publication.id in baselines:
            signals["views_relative"] = signals["views"] / baselines[publication.id]
        for name, value in signals.items():
            groups[key][name].append(value)
    return groups


def _describe(values: list[float]) -> dict:
    ordered = sorted(values)
    q1 = statistics.median(ordered[: len(ordered) // 2]) if len(ordered) > 1 else None
    q3 = statistics.median(ordered[(len(ordered) + 1) // 2 :]) if len(ordered) > 1 else None
    return {"sample_size": len(values), "median": statistics.median(values), "q1": q1, "q3": q3, "min": min(values), "max": max(values), "median_ci90": median_ci(values)}


def _damped_signal(group_values: list[float], overall_median: float | None) -> dict | None:
    if len(group_values) < MIN_SAMPLES or not overall_median or overall_median <= 0:
        return None
    raw = statistics.median(group_values) / overall_median
    shrink = len(group_values) / (len(group_values) + 5)
    bounded = max(MULTIPLIER_FLOOR, min(MULTIPLIER_CEILING, 1 + (raw - 1) * shrink))
    return {"raw_ratio": round(raw, 4), "damped": round(bounded, 4), "sample_size": len(group_values)}


def _combine(signals: dict[str, dict]) -> tuple[float, dict[str, float]]:
    total = sum(SIGNAL_WEIGHTS[name] for name in signals)
    weights = {name: SIGNAL_WEIGHTS[name] / total for name in signals}
    log_mean = sum(weights[name] * math.log(signals[name]["damped"]) for name in signals)
    combined = max(MULTIPLIER_FLOOR, min(MULTIPLIER_CEILING, math.exp(log_mean)))
    return round(combined, 4), {name: round(weight, 4) for name, weight in weights.items()}


def _cohort(group_key: str) -> str:
    platform, video_format, _hook, bucket = group_key.split("|")
    return f"{platform}|{video_format}|{bucket}"


def scene_drops(db: Session, is_demo: bool, now: datetime, window_days: int = LEARNING_WINDOW_DAYS, limit: int = 10) -> list[dict]:
    """Steepest per-second retention drops by scene, joined to the scene's asset context."""
    since = now - timedelta(days=window_days)
    rows = []
    curves = db.query(MetricSnapshot).filter(MetricSnapshot.is_demo == is_demo, MetricSnapshot.metric_name == "retentionCurve").all()
    latest: dict[int, MetricSnapshot] = {}
    for curve in curves:
        if curve.publication_id not in latest or _utc(curve.collected_at) > _utc(latest[curve.publication_id].collected_at):
            latest[curve.publication_id] = curve
    for publication_id, curve in latest.items():
        publication = db.get(Publication, publication_id)
        if not publication or not publication.published_at or _utc(publication.published_at) < since:
            continue
        for scene in (curve.features_json or {}).get("scenes", []):
            asset = db.get(Asset, scene["asset_id"]) if scene.get("asset_id") else None
            context = (asset.metadata_json or {}) if asset else {}
            rows.append({"publication_id": publication_id, "platform": publication.platform, **scene, "kind": context.get("kind"), "source_type": context.get("source_type"), "context": context.get("context")})
    return sorted(rows, key=lambda row: row["drop_per_second"], reverse=True)[:limit]


def weekly_learning(db: Session, output_dir: Path | None = None, is_demo: bool = False, now: datetime | None = None, window_days: int = LEARNING_WINDOW_DAYS) -> dict:
    settings = get_settings()
    now = _utc(now or datetime.now(timezone.utc))
    output_dir = output_dir or settings.data_dir / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    groups = _group_rows(db, is_demo, now=now, window_days=window_days)
    overall: dict[str, float] = {}
    for name in SIGNAL_WEIGHTS:
        pooled = [value for signals in groups.values() for value in signals.get(name, [])]
        if pooled:
            overall[name] = statistics.median(pooled)
    summaries = []
    for key, signals in sorted(groups.items()):
        described = {name: _describe(values) for name, values in signals.items() if values}
        if not described:
            continue
        row = {"group": key, "sample_size": max(item["sample_size"] for item in described.values()), "signals": described}
        views = described.get("views")
        if views:
            row.update({"median_views": views["median"], "q1": views["q1"], "q3": views["q3"], "min": views["min"], "max": views["max"]})
        summaries.append(row)
    setting_key = "learning_model_demo" if is_demo else "learning_model"
    previous = db.get(Setting, setting_key)
    version = int(previous.value_json.get("version", 0)) + 1 if previous else 1
    multipliers = previous.value_json.get("hook_multipliers", {}) if previous else {}
    # Hooks are only compared with other hooks in the same cohort (platform, format, length bucket),
    # so platform-level differences in reach never masquerade as hook effects.
    cohorts: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for key in groups:
        cohorts[_cohort(key)]["groups"].append(key)
    cohort_medians: dict[str, dict[str, float]] = {}
    no_comparison = []
    for cohort, members in sorted(cohorts.items()):
        if len({key.split("|")[2] for key in members["groups"]}) < 2:
            no_comparison.extend(sorted(members["groups"]))
            continue
        cohort_medians[cohort] = {}
        for name in SIGNAL_WEIGHTS:
            pooled = [value for key in members["groups"] for value in groups[key].get(name, [])]
            if pooled:
                cohort_medians[cohort][name] = statistics.median(pooled)
    per_hook: dict[str, list[dict]] = defaultdict(list)
    for key, signals in sorted(groups.items()):
        baseline = cohort_medians.get(_cohort(key))
        if baseline is None:
            continue
        damped = {name: result for name in SIGNAL_WEIGHTS if (result := _damped_signal(signals.get(name, []), baseline.get(name)))}
        if not damped:
            continue
        combined, weights_used = _combine(damped)
        per_hook[key.split("|")[2]].append({"group": key, "multiplier": combined, "sample_size": max(item["sample_size"] for item in damped.values()), "signals": damped, "weights_used": weights_used})
    updates = []
    for hook, group_results in sorted(per_hook.items()):
        total = sum(item["sample_size"] for item in group_results)
        pooled = math.exp(sum(item["sample_size"] * math.log(item["multiplier"]) for item in group_results) / total)
        multipliers[hook] = round(max(MULTIPLIER_FLOOR, min(MULTIPLIER_CEILING, pooled)), 4)
        updates.append({"hook": hook, "multiplier": multipliers[hook], "sample_size": total, "groups": group_results, "reason": "Sample-weighted geometric mean over cohorts of shrunk seven-day median ratios versus other hooks in the same platform, format and length bucket; correlation only."})
    model = Setting(key=setting_key, value_json={"version": version, "hook_multipliers": multipliers, "signal_weights": {"version": SIGNAL_WEIGHTS_VERSION, "weights": SIGNAL_WEIGHTS}, "experiment_allocation": {"known_formats": 0.8, "new_experiments": 0.2}, "last_updated_utc": datetime.now(timezone.utc).isoformat(), "data_mode": "demo" if is_demo else "real", "updates": updates})
    db.merge(model)
    db.commit()
    governance = None
    experiments = []
    allocation = None
    next_ideas = []
    quality_calibration = None
    rejection_counts = None
    if not is_demo:
        from app.pipeline.experiments import allocation_report, evaluate_active
        from app.pipeline.governance import weekly_step

        experiments = evaluate_active(db, now)
        allocation = allocation_report(db, now=now)
        governance = weekly_step(db, model.value_json, now)
        from app.pipeline.ideas import rank_ideas
        from app.pipeline.quality import calibration_report, rejection_category_counts

        next_ideas = rank_ideas(db, 10)
        quality_calibration = calibration_report(db)
        rejection_counts = rejection_category_counts(db)
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
        "comparison": f"One snapshot per publication at approximately seven days, published within the last {window_days} days, grouped by platform, format, hook and length bucket. Views are divided by the channel's same-platform median around the publish date (growth correction). Signals: relative views, retention, hook retention after the intro, watch time per view, engagement and net subscribers per 1,000 views.",
        "window": {"days": window_days, "until": now.isoformat(), "growth_baseline_days": GROWTH_BASELINE_DAYS},
        "uncertainty_intervals": "median_ci90 is a seeded 90 % bootstrap interval of each group median; null below three samples.",
        "scene_drops": scene_drops(db, is_demo, now, window_days),
        "experiments": experiments,
        "exploration_allocation": allocation,
        "governance": governance,
        "next_ideas": next_ideas,
        "quality_calibration": quality_calibration,
        "owner_rejection_categories_28d": rejection_counts,
        "signal_weights": {"version": SIGNAL_WEIGHTS_VERSION, "weights": SIGNAL_WEIGHTS},
        "overall_medians": overall,
        "cohort_medians": cohort_medians,
        "groups_without_comparable_hook": no_comparison,
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
    for row in summaries:
        parts = [f"{name} n={item['sample_size']} median={item['median']:.2f} range={item['min']:.2f}–{item['max']:.2f}" for name, item in row["signals"].items()]
        lines.append(f"- {row['group']}: " + "; ".join(parts))
    lines += ["", "## Model updates"]
    for item in updates:
        lines.append(f"- {item['hook']}: {item['multiplier']:.4f} (n={item['sample_size']})")
        lines.extend(f"  - {group['group']}: {group['multiplier']:.4f} from " + ", ".join(f"{name}={sig['damped']:.4f} (n={sig['sample_size']})" for name, sig in group["signals"].items()) for group in item["groups"])
    if no_comparison:
        lines.append("- No comparable hook in cohort (skipped): " + ", ".join(no_comparison))
    if governance:
        lines += ["", "## Scorecard (primary: net subscribers per 1,000 views)"]
        lines.extend(f"- {row['week_start']}: primary={row['primary']} (n={row['primary_n']}), retention={row['retention_pct']}, hook_retention_3s={row['hook_retention_3s']}, first-pass approval={row['first_pass_approval']['rate']}" for row in governance["scorecard"])
        lines.append(f"- Active model: v{governance['active_version']}; candidate in shadow: v{governance['candidate_version']}; guardrail breaches: {', '.join(governance['guardrail_breaches']) or 'none'}; rolled back: {governance['rolled_back']}")
    if experiments:
        lines += ["", "## Experiments"]
        lines.extend(f"- {item['name']} ({item['variable']}): {item['decision']}; samples {item['samples']}" for item in experiments)
    if next_ideas:
        lines += ["", "## Suggested next ideas (80 % exploit / 20 % explore)"]
        lines.extend(f"- [{item['allocation']}] {item['idea_id']} {item['title']} — score {item['score']}" for item in next_ideas)
    if report["scene_drops"]:
        lines += ["", "## Steepest scene drops"]
        lines.extend(f"- publication {row['publication_id']} {row['scene_id']} ({row.get('source_type')}): {row['drop_per_second']:.4f}/s — {row.get('context')}" for row in report["scene_drops"])
    lines += ["", "## Interpretation", "- Correlation only; no causal claim.", "- Repeat promising formats only after comparable results.", "", "## Next experiment", report["next_experiment"]]
    md_path = output_dir / f"learning-{mode}-{date}-v{version}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["files"] = {"json": str(json_path), "markdown": str(md_path)}
    return report
