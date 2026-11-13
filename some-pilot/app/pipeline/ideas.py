"""Rank the Content Bible idea bank with what the channel has learned.

Scores are damped, non-causal priorities. 80 % of the suggestions exploit what
has worked (recipe and hook evidence); 20 % explore recipes/hooks with the least
data so the model keeps learning. Research queries for the worker are derived
from the ranked ideas instead of hard-coded search terms, and research results
are stored as idea suggestions with a written rationale.
"""

import math
import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import IdeaSuggestion, Observation, Publication, VideoVersion
from app.pipeline.editorial import EditorialRegistry
from app.pipeline.taxonomy import normalize_hook

EXPLOIT_SHARE = 0.8
FRESHNESS_FACTOR = {"event": 1.10, "deal": 1.05, "evergreen": 1.0}
PRIMARY = "net_subscribers_per_1k_views"
OUTLIER_RATIO = 3.0


def classify_idea_hook(text: str) -> str:
    lowered = text.casefold().strip()
    if re.match(r"^(top\s*\d+|\d+\s)", lowered) or "ranked" in lowered:
        return "ranking_reveal"
    if any(word in lowered for word in (" vs ", " versus ", "compared", "which is better")):
        return "comparison"
    if any(word in lowered for word in ("how to", "checklist", "tips", "before you buy")):
        return "practical_checklist"
    if lowered.startswith(("can you", "try ", "could you")):
        return "challenge"
    if lowered.endswith("?"):
        return "question"
    if any(word in lowered for word in ("did you know", "%", "only ")) or re.search(r"\d", lowered):
        return "surprising_fact"
    if lowered.startswith(("when ", "this is the story", "follow ")):
        return "story"
    return "bold_claim"


def _damped(values: list[float], overall: float | None) -> float:
    if not values or not overall or overall <= 0:
        return 1.0
    raw = statistics.median(values) / overall
    shrink = len(values) / (len(values) + 5)
    return max(0.75, min(1.25, 1 + (raw - 1) * shrink))


def _outcomes(db: Session) -> tuple[dict[str, list[float]], dict[str, list[float]], set[str], float | None]:
    from app.pipeline.learning import _publication_metrics, _signals

    by_recipe: dict[str, list[float]] = defaultdict(list)
    by_series: dict[str, list[float]] = defaultdict(list)
    pooled = []
    for publication_id, metrics in _publication_metrics(db, False, 7).items():
        value = _signals(metrics).get(PRIMARY)
        publication = db.get(Publication, publication_id)
        video = db.get(VideoVersion, publication.video_version_id) if publication else None
        if value is None or video is None:
            continue
        features = video.features_json or {}
        pooled.append(value)
        if features.get("recipe_id"):
            by_recipe[features["recipe_id"]].append(value)
        if features.get("series_id"):
            by_series[features["series_id"]].append(value)
    produced = {(video.features_json or {}).get("idea_id") for video in db.query(VideoVersion).all()} - {None}
    return by_recipe, by_series, produced, statistics.median(pooled) if pooled else None


def rank_ideas(db: Session, limit: int = 10, lane: str | None = None, series_by_recipe: dict[str, str] | None = None) -> list[dict]:
    from app.pipeline.governance import active_learning_model

    registry = EditorialRegistry()
    if series_by_recipe is None:
        from app.pipeline.audience import series_by_recipe as registry_series

        series_by_recipe = registry_series()
    active = active_learning_model(db)
    hook_multipliers = (active or {}).get("model", {}).get("hook_multipliers", {})
    by_recipe, by_series, produced, overall = _outcomes(db)
    candidates = []
    for idea in registry.ideas:
        if lane and idea["lane"] != lane:
            continue
        if idea["id"] in produced:
            continue
        hook = classify_idea_hook(idea["hook"])
        recipe_factor = _damped(by_recipe.get(idea["recipe_id"], []), overall)
        series = (series_by_recipe or {}).get(idea["recipe_id"])
        series_factor = _damped(by_series.get(series, []), overall) if series else 1.0
        hook_factor = float(hook_multipliers.get(normalize_hook(hook, strict=False), 1.0))
        freshness = FRESHNESS_FACTOR.get(idea["freshness"], 1.0)
        evidence_n = len(by_recipe.get(idea["recipe_id"], []))
        score = round(100 * recipe_factor * hook_factor * series_factor * freshness, 2)
        candidates.append({
            "idea_id": idea["id"],
            "lane": idea["lane"],
            "title": idea["title"],
            "recipe_id": idea["recipe_id"],
            "hook_type": hook,
            "platforms": idea["recommended_platforms"],
            "score": score,
            "evidence_samples": evidence_n,
            "factors": {"recipe": round(recipe_factor, 4), "hook": round(hook_factor, 4), "series": round(series_factor, 4), "freshness": freshness},
            "learning_question": idea.get("learning_question"),
            "series_id": series,
        })
    exploit_slots = math.ceil(limit * EXPLOIT_SHARE)
    exploit = sorted(candidates, key=lambda item: (-item["score"], item["idea_id"]))[:exploit_slots]
    chosen = {item["idea_id"] for item in exploit}
    explore_pool = [item for item in candidates if item["idea_id"] not in chosen]
    explore = sorted(explore_pool, key=lambda item: (item["evidence_samples"], -item["score"], item["idea_id"]))[: limit - len(exploit)]
    for item in exploit:
        item["allocation"] = "exploit"
        item["rationale"] = f"Score {item['score']} from recipe evidence (n={item['evidence_samples']}) and the active hook model; correlation only."
    for item in explore:
        item["allocation"] = "explore"
        item["rationale"] = f"Exploration slot: recipe {item['recipe_id']} has only {item['evidence_samples']} measured posts. Answers: {item['learning_question']}"
    return exploit + explore


def research_query(idea: dict) -> str:
    """A short search query from an idea title, without the recipe prefix."""
    title = idea["title"].split(":", 1)[-1]
    words = re.findall(r"[\w'+-]+", title)
    stop = {"the", "a", "an", "you", "your", "of", "to", "and", "is", "in", "for", "on", "this", "that", "what", "why", "how", "with", "can", "it"}
    kept = [word for word in words if word.casefold() not in stop]
    return " ".join(kept[:6])


def research_plan(db: Session, limit: int = 6) -> list[dict]:
    return [{"idea_id": item["idea_id"], "lane": item["lane"], "title": item["title"], "query": research_query(item), "allocation": item["allocation"]} for item in rank_ideas(db, limit)]


def suggestions_from_research(db: Session, plan: list[dict], days: int = 30, is_demo: bool = False) -> list[IdeaSuggestion]:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    created = []
    for item in plan:
        all_rows = db.query(Observation).filter(Observation.is_demo.is_(is_demo), Observation.topic.startswith(item["query"] + ":"), Observation.metric_value.isnot(None)).all()
        all_rows = [row for row in all_rows if (row.collected_at_utc.replace(tzinfo=timezone.utc) if row.collected_at_utc.tzinfo is None else row.collected_at_utc) >= since]
        rows = [row for row in all_rows if row.metric_name == "views"]
        ratios = [row for row in all_rows if row.metric_name == "views_per_subscriber"]
        outliers = sorted((row for row in ratios if row.metric_value >= OUTLIER_RATIO), key=lambda row: row.metric_value, reverse=True)
        values = [float(row.metric_value) for row in rows]
        top = sorted(rows, key=lambda row: row.metric_value or 0, reverse=True)[:3]
        evidence = {"outliers": [{"url": row.source_url, "title": row.topic.split(":", 1)[-1][:200], "views_per_subscriber": row.metric_value} for row in outliers[:5]], "outlier_ratio_threshold": OUTLIER_RATIO, "observations": len(values), "median_views": statistics.median(values) if values else None, "examples": [{"url": row.source_url, "title": row.topic.split(":", 1)[-1][:200], "views": row.metric_value} for row in top], "window_days": days, "limitations": "Search sample of other channels; cumulative views, not views per hour. Interest signal only, never evidence or footage."}
        if values:
            rationale = f"{len(values)} recent YouTube videos match '{item['query']}' (median {statistics.median(values):,.0f} views in the last {days} days). Ranked as {item['allocation']}."
        else:
            rationale = f"No recent YouTube matches for '{item['query']}'. Ranked as {item['allocation']}; low competition or low interest — verify before choosing."
        if outliers:
            rationale += f" {len(outliers)} outlier(s): a video reached at least {OUTLIER_RATIO:g}× its own channel's subscribers — a stronger topic signal than raw views."
        suggestion = IdeaSuggestion(idea_id=item["idea_id"], lane=item["lane"], title=item["title"], query=item["query"], rationale=rationale, evidence_json=evidence, score=float(len(outliers)) * 1000 + (evidence["median_views"] or 0) / 1000 if values or outliers else None, is_demo=is_demo)
        db.add(suggestion)
        created.append(suggestion)
    db.commit()
    return created
