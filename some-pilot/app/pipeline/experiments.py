"""Pre-registered, one-variable experiments.

An experiment is registered before any production: hypothesis, the single
variable that changes, the variants, the primary metric, guardrails, a stop rule
and a rollback. The spec is hashed and cannot change while active. Assignment is
balanced randomisation per story, production verifies the assigned variant, and
evaluation only recommends; adopting a winner is an owner decision.
"""

import hashlib
import json
import statistics
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Experiment, Publication, VideoVersion
from app.pipeline.stats import median_difference_ci
from app.pipeline.taxonomy import CTA_TYPES, HOOK_TYPES

ExperimentVariable = Literal["hook_type", "cta_type", "series_id", "thumbnail_type", "duration_bucket", "opening_style", "title_style", "publish_hour_bucket"]
PrimaryMetric = Literal["net_subscribers_per_1k_views", "retention_pct", "hook_retention_3s", "engagement_per_1k_views", "watch_seconds_per_view", "views"]

# Variables production can verify from the rendered output; the rest are declared
# by the planner and recorded as such in the evaluation.
VERIFIABLE_VARIABLES = {"hook_type", "cta_type", "series_id", "thumbnail_type", "duration_bucket"}
GUARDRAIL_TOLERANCE = 0.10
EXPLORATION_SHARE = 0.20


class Variant(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=100)


class ExperimentSpec(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    hypothesis: str = Field(min_length=20, max_length=2000)
    variable: ExperimentVariable
    variants: list[Variant] = Field(min_length=2, max_length=4)
    primary_metric: PrimaryMetric = "net_subscribers_per_1k_views"
    guardrails: list[PrimaryMetric] = Field(default_factory=lambda: ["retention_pct"])
    platform: Literal["youtube", "instagram", "tiktok", "facebook", "any"] = "any"
    min_samples_per_variant: int = Field(default=6, ge=3, le=100)
    max_days: int = Field(default=42, ge=7, le=120)
    minimum_detectable_effect: float = Field(default=0.10, gt=0, le=2)
    rollback: str = Field(min_length=10, max_length=1000)
    is_pilot: bool = False

    @model_validator(mode="after")
    def one_variable_distinct_values(self):
        if len({variant.id for variant in self.variants}) != len(self.variants):
            raise ValueError("experiment_variant_ids_must_be_unique")
        if len({variant.value for variant in self.variants}) != len(self.variants):
            raise ValueError("experiment_variant_values_must_differ")
        allowed = {"hook_type": HOOK_TYPES, "cta_type": CTA_TYPES, "duration_bucket": ("short", "medium", "long")}.get(self.variable)
        if allowed and any(variant.value not in allowed for variant in self.variants):
            raise ValueError(f"experiment_value_not_in_taxonomy:{self.variable}")
        if self.primary_metric in self.guardrails:
            raise ValueError("primary_metric_cannot_be_guardrail")
        return self


def spec_hash(spec: ExperimentSpec) -> str:
    canonical = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_experiment(db: Session, spec: ExperimentSpec, actor: str = "owner") -> Experiment:
    active = db.query(Experiment).filter(Experiment.status == "ACTIVE").all()
    if any(item.spec_json.get("variable") == spec.variable for item in active):
        raise ValueError(f"active_experiment_already_tests:{spec.variable}")
    now = datetime.now(timezone.utc)
    experiment = Experiment(name=spec.name, status="ACTIVE", variants_json=[variant.model_dump() for variant in spec.variants], allocation_json={"method": "balanced_randomisation_per_story", "assignments": {}}, results_json={}, spec_json=spec.model_dump(mode="json"), spec_sha256=spec_hash(spec), started_at=now)
    db.add(experiment)
    db.flush()
    db.add(AuditEvent(actor=actor, action="EXPERIMENT_REGISTERED", entity_type="experiment", entity_id=str(experiment.id), details_json={"spec_sha256": experiment.spec_sha256, "variable": spec.variable}))
    db.commit()
    return experiment


def _spec(experiment: Experiment) -> ExperimentSpec:
    spec = ExperimentSpec.model_validate(experiment.spec_json)
    if spec_hash(spec) != experiment.spec_sha256:
        raise ValueError("experiment_spec_changed_after_registration")
    return spec


def assign_variant(db: Session, experiment_id: int, story_key: str, actor: str = "planner") -> dict:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None or experiment.status != "ACTIVE":
        raise ValueError("experiment_not_active")
    spec = _spec(experiment)
    allocation = dict(experiment.allocation_json or {})
    assignments = dict(allocation.get("assignments", {}))
    if story_key in assignments:
        variant_id = assignments[story_key]
    else:
        counts = {variant.id: 0 for variant in spec.variants}
        for assigned in assignments.values():
            counts[assigned] = counts.get(assigned, 0) + 1
        fewest = min(counts.values())
        candidates = sorted(variant_id for variant_id, count in counts.items() if count == fewest)
        digest = int(hashlib.sha256(f"{experiment.id}:{story_key}".encode()).hexdigest(), 16)
        variant_id = candidates[digest % len(candidates)]
        assignments[story_key] = variant_id
        experiment.allocation_json = {**allocation, "assignments": assignments}
        db.add(AuditEvent(actor=actor, action="EXPERIMENT_ASSIGNED", entity_type="experiment", entity_id=str(experiment.id), details_json={"story": story_key, "variant": variant_id}))
        db.commit()
    value = next(variant.value for variant in spec.variants if variant.id == variant_id)
    return {"experiment_id": experiment.id, "variant_id": variant_id, "variable": spec.variable, "value": value, "is_pilot": spec.is_pilot}


def duration_bucket(seconds: float | None) -> str:
    seconds = seconds or 0
    return "short" if seconds <= 35 else "medium" if seconds <= 60 else "long"


def verify_assignment(db: Session, experiment_id: int, variant_id: str, story_key: str, features: dict) -> dict:
    """Block production when the plan does not match the registered assignment."""
    experiment = db.get(Experiment, experiment_id)
    if experiment is None or experiment.status != "ACTIVE":
        raise ValueError("experiment_not_active")
    spec = _spec(experiment)
    assigned = (experiment.allocation_json or {}).get("assignments", {}).get(story_key)
    if assigned is None:
        raise ValueError("experiment_story_not_assigned")
    if assigned != variant_id:
        raise ValueError(f"experiment_variant_mismatch:assigned={assigned}")
    value = next(variant.value for variant in spec.variants if variant.id == variant_id)
    if spec.variable in VERIFIABLE_VARIABLES and spec.variable != "duration_bucket":
        actual = features.get(spec.variable)
        if actual != value:
            raise ValueError(f"experiment_variable_not_applied:{spec.variable}={actual}")
    if spec.platform != "any" and features.get("platform") != spec.platform:
        raise ValueError("experiment_platform_mismatch")
    return {"experiment_id": experiment.id, "variant_id": variant_id, "variable": spec.variable, "value": value, "verified": spec.variable in VERIFIABLE_VARIABLES, "spec_sha256": experiment.spec_sha256, "is_pilot": spec.is_pilot}


def verify_rendered_variant(features: dict) -> None:
    """Checks that can only run after rendering (duration bucket)."""
    experiment = features.get("experiment") or {}
    if experiment.get("variable") == "duration_bucket" and duration_bucket(features.get("duration_seconds")) != experiment.get("value"):
        raise ValueError("experiment_variable_not_applied:duration_bucket")


def _variant_values(db: Session, experiment: Experiment, metric: str, now: datetime) -> dict[str, list[float]]:
    from app.pipeline.learning import _publication_metrics, _signals

    per_publication = _publication_metrics(db, False, 7)
    values: dict[str, list[float]] = {variant["id"]: [] for variant in experiment.variants_json}
    for publication_id, metrics in per_publication.items():
        publication = db.get(Publication, publication_id)
        video = db.get(VideoVersion, publication.video_version_id) if publication else None
        marker = (video.features_json or {}).get("experiment") if video else None
        if not marker or marker.get("experiment_id") != experiment.id:
            continue
        signal = _signals(metrics).get(metric)
        if signal is not None and marker.get("variant_id") in values:
            values[marker["variant_id"]].append(signal)
    return values


def evaluate_experiment(db: Session, experiment_id: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise ValueError("experiment_not_found")
    spec = _spec(experiment)
    primary = _variant_values(db, experiment, spec.primary_metric, now)
    control_id = spec.variants[0].id
    control = primary[control_id]
    comparisons = []
    for variant in spec.variants[1:]:
        treatment = primary[variant.id]
        interval = median_difference_ci(treatment, control)
        relative = None
        if treatment and control and statistics.median(control):
            relative = statistics.median(treatment) / statistics.median(control) - 1
        comparisons.append({"variant_id": variant.id, "n": len(treatment), "control_n": len(control), "median": statistics.median(treatment) if treatment else None, "control_median": statistics.median(control) if control else None, "relative_difference": round(relative, 4) if relative is not None else None, "difference_ci90": interval})
    started = experiment.started_at.replace(tzinfo=timezone.utc) if experiment.started_at and experiment.started_at.tzinfo is None else experiment.started_at
    enough = all(len(values) >= spec.min_samples_per_variant for values in primary.values())
    timed_out = started is not None and now - started > timedelta(days=spec.max_days)
    decision = "running"
    winner = None
    if enough:
        decisive = [item for item in comparisons if item["difference_ci90"] and (item["difference_ci90"][0] > 0 or item["difference_ci90"][1] < 0) and item["relative_difference"] is not None and abs(item["relative_difference"]) >= spec.minimum_detectable_effect]
        better = [item for item in decisive if item["difference_ci90"][0] > 0]
        if better:
            winner = max(better, key=lambda item: item["relative_difference"])["variant_id"]
            decision = f"winner:{winner}"
        elif decisive:
            decision = f"winner:{control_id}"
            winner = control_id
        else:
            decision = "no_detectable_difference"
    elif timed_out:
        decision = "inconclusive_timeout"
    guardrails = {}
    if winner and winner != control_id:
        for metric in spec.guardrails:
            values = _variant_values(db, experiment, metric, now)
            if values[winner] and values[control_id]:
                ratio = statistics.median(values[winner]) / statistics.median(values[control_id]) if statistics.median(values[control_id]) else 1
                guardrails[metric] = {"ratio_to_control": round(ratio, 4), "breached": ratio < 1 - GUARDRAIL_TOLERANCE}
        if any(item["breached"] for item in guardrails.values()):
            decision = f"winner_blocked_by_guardrail:{winner}"
    result = {"experiment_id": experiment.id, "name": spec.name, "variable": spec.variable, "primary_metric": spec.primary_metric, "control": control_id, "samples": {key: len(values) for key, values in primary.items()}, "comparisons": comparisons, "guardrails": guardrails, "decision": decision, "evaluated_at": now.isoformat(), "variable_verified_at_production": spec.variable in VERIFIABLE_VARIABLES, "rollback": spec.rollback, "adoption": "owner_decision_required", "causal_note": "Randomised within this channel; still a small sample. Adopt only with the owner's review."}
    experiment.results_json = result
    if decision != "running" and experiment.status == "ACTIVE":
        experiment.status = "COMPLETED"
        experiment.ended_at = now
        experiment.decision = decision
        db.add(AuditEvent(actor="learning", action="EXPERIMENT_COMPLETED", entity_type="experiment", entity_id=str(experiment.id), details_json={"decision": decision}))
    db.commit()
    return result


def evaluate_active(db: Session, now: datetime | None = None) -> list[dict]:
    return [evaluate_experiment(db, item.id, now) for item in db.query(Experiment).filter(Experiment.status == "ACTIVE").order_by(Experiment.id).all()]


def stop_experiment(db: Session, experiment_id: int, reason: str, actor: str = "owner") -> Experiment:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None or experiment.status != "ACTIVE":
        raise ValueError("experiment_not_active")
    if len(reason.strip()) < 5:
        raise ValueError("stop_reason_required")
    experiment.status = "STOPPED"
    experiment.ended_at = datetime.now(timezone.utc)
    experiment.decision = "stopped:" + reason.strip()[:100]
    db.add(AuditEvent(actor=actor, action="EXPERIMENT_STOPPED", entity_type="experiment", entity_id=str(experiment.id), details_json={"reason": reason[:500]}))
    db.commit()
    return experiment


def allocation_report(db: Session, days: int = 30, now: datetime | None = None) -> dict:
    """Actual exploration share (experiments, excluding the pilot) versus the 20 % target."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    videos = [video for video in db.query(VideoVersion).all() if not (video.features_json or {}).get("is_demo") and video.created_at and (video.created_at.replace(tzinfo=timezone.utc) if video.created_at.tzinfo is None else video.created_at) >= since]
    experimental = [video for video in videos if (video.features_json or {}).get("experiment") and not video.features_json["experiment"].get("is_pilot")]
    share = len(experimental) / len(videos) if videos else 0.0
    return {"window_days": days, "productions": len(videos), "experimental": len(experimental), "share": round(share, 4), "target_share": EXPLORATION_SHARE, "over_budget": len(videos) >= 10 and share > EXPLORATION_SHARE + 0.05}
