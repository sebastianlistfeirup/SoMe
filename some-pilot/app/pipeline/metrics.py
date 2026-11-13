import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MetricSnapshot, Publication, VideoVersion
from app.pipeline.stats import interpolate

REQUIRED = {"publication_id", "metric_name", "metric_value", "collected_at", "metric_definition_version"}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def import_csv(db: Session, path: Path, is_demo: bool = False) -> int:
    count = 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing_columns:" + ",".join(sorted(missing)))
        for row in reader:
            publication = db.get(Publication, int(row["publication_id"]))
            if publication is None:
                raise ValueError("unknown_publication")
            video = db.get(VideoVersion, publication.video_version_id)
            if video is None or bool(video.features_json.get("is_demo")) != is_demo:
                raise ValueError("demo_production_mixing_blocked")
            collected_at = datetime.fromisoformat(row["collected_at"].replace("Z", "+00:00"))
            existing = db.query(MetricSnapshot).filter(MetricSnapshot.publication_id == publication.id, MetricSnapshot.metric_name == row["metric_name"], MetricSnapshot.collected_at == collected_at, MetricSnapshot.metric_definition_version == row["metric_definition_version"], MetricSnapshot.is_demo.is_(is_demo)).first()
            if existing:
                continue
            value = float(row["metric_value"]) if row["metric_value"].strip() else None
            snapshot = MetricSnapshot(publication_id=publication.id, collected_at=collected_at, metric_definition_version=row["metric_definition_version"], metric_name=row["metric_name"], metric_value=value, unit=row.get("unit") or None, features_json={}, is_demo=is_demo)
            db.add(snapshot)
            count += 1
    db.commit()
    return count


def _youtube_access_token() -> str:
    settings = get_settings()
    response = httpx.post("https://oauth2.googleapis.com/token", data={"client_id": settings.youtube_client_id, "client_secret": settings.youtube_client_secret, "refresh_token": settings.youtube_refresh_token, "grant_type": "refresh_token"}, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def collect_youtube_analytics(db: Session, publication: Publication) -> int:
    if not publication.remote_id or not publication.published_at:
        raise ValueError("youtube_remote_id_and_publish_date_required")
    settings = get_settings()
    if not all((settings.youtube_client_id, settings.youtube_client_secret, settings.youtube_refresh_token)):
        raise RuntimeError("youtube_analytics_oauth_missing")
    metrics = ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage", "subscribersGained", "subscribersLost", "likes", "comments", "shares"]
    response = httpx.get("https://youtubeanalytics.googleapis.com/v2/reports", headers={"Authorization": f"Bearer {_youtube_access_token()}"}, params={"ids": "channel==MINE", "filters": f"video=={publication.remote_id}", "startDate": _as_utc(publication.published_at).date().isoformat(), "endDate": datetime.now(timezone.utc).date().isoformat(), "metrics": ",".join(metrics)}, timeout=30)
    if response.status_code in {401, 403}:
        raise RuntimeError("youtube_analytics_authorization_required")
    response.raise_for_status()
    body = response.json()
    rows = body.get("rows", [])
    values = rows[0] if rows else []
    now = datetime.now(timezone.utc)
    count = 0
    for index, metric in enumerate(metrics):
        value = float(values[index]) if index < len(values) else None
        db.add(MetricSnapshot(publication_id=publication.id, collected_at=now, metric_definition_version="youtube-analytics-v2:2026-11-08", metric_name=metric, metric_value=value, unit=None, features_json={"source": "YouTube Analytics API", "remote_id": publication.remote_id}, is_demo=False))
        count += 1
    db.commit()
    return count


RETENTION_DEFINITION = "youtube-analytics-retention-v1"


def retention_summary(points: list[tuple[float, float]], duration_seconds: float, intro_seconds: float = 0.0, scenes: list[dict] | None = None) -> dict:
    """Turn a 100-point retention curve into first-seconds and per-scene signals.

    points are (elapsedVideoTimeRatio, audienceWatchRatio). Times are converted with
    the rendered duration. hook_retention_3s is measured from the end of the brand
    intro, so it describes the editorial opening rather than the fixed ident.
    """
    if duration_seconds <= 0 or not points:
        raise ValueError("retention_requires_duration_and_points")

    def at(seconds: float) -> float | None:
        return interpolate(points, min(1.0, max(0.0, seconds / duration_seconds)))

    start = at(0) or 0
    intro_end = at(intro_seconds) if intro_seconds else start
    summary = {
        "retentionAt1s": at(1),
        "retentionAt3s": at(3),
        "retentionAt5s": at(5),
        "introRetention": round(intro_end / start, 6) if intro_seconds and start else None,
        "hookRetention3s": round(at(intro_seconds + 3) / intro_end, 6) if intro_end else None,
    }
    scene_rows = []
    for scene in scenes or []:
        begin = intro_seconds + scene["start_ms"] / 1000
        end = intro_seconds + scene["end_ms"] / 1000
        begin_value, end_value = at(begin), at(end)
        if begin_value is None or end_value is None or end <= begin:
            continue
        drop = begin_value - end_value
        scene_rows.append({"scene_id": scene["scene_id"], "asset_id": scene.get("asset_id"), "start_seconds": round(begin, 3), "end_seconds": round(end, 3), "watch_ratio_start": round(begin_value, 6), "watch_ratio_end": round(end_value, 6), "drop": round(drop, 6), "drop_per_second": round(drop / (end - begin), 6)})
    summary["scenes"] = scene_rows
    return summary


def collect_youtube_retention(db: Session, publication: Publication) -> int:
    if not publication.remote_id or not publication.published_at:
        raise ValueError("youtube_remote_id_and_publish_date_required")
    settings = get_settings()
    if not all((settings.youtube_client_id, settings.youtube_client_secret, settings.youtube_refresh_token)):
        raise RuntimeError("youtube_analytics_oauth_missing")
    video = db.get(VideoVersion, publication.video_version_id)
    if video is None or not video.duration_seconds:
        raise ValueError("video_duration_required_for_retention")
    response = httpx.get("https://youtubeanalytics.googleapis.com/v2/reports", headers={"Authorization": f"Bearer {_youtube_access_token()}"}, params={"ids": "channel==MINE", "filters": f"video=={publication.remote_id}", "dimensions": "elapsedVideoTimeRatio", "metrics": "audienceWatchRatio,relativeRetentionPerformance", "startDate": _as_utc(publication.published_at).date().isoformat(), "endDate": datetime.now(timezone.utc).date().isoformat()}, timeout=30)
    if response.status_code in {401, 403}:
        raise RuntimeError("youtube_analytics_authorization_required")
    response.raise_for_status()
    rows = response.json().get("rows", [])
    if not rows:
        return 0
    points = [(float(row[0]), float(row[1])) for row in rows]
    relative = [float(row[2]) for row in rows if len(row) > 2 and row[2] is not None]
    scenes = []
    clip_plan = Path(video.output_dir) / "clip_plan.json"
    if clip_plan.is_file():
        scenes = json.loads(clip_plan.read_text(encoding="utf-8")).get("scenes", [])
    intro = float(video.features_json.get("intro_seconds") or 0)
    summary = retention_summary(points, float(video.duration_seconds), intro, scenes)
    now = datetime.now(timezone.utc)
    features = {"source": "YouTube Analytics API retention", "remote_id": publication.remote_id, "intro_seconds": intro, "duration_seconds": video.duration_seconds}
    count = 0
    for name in ("retentionAt1s", "retentionAt3s", "retentionAt5s", "introRetention", "hookRetention3s"):
        db.add(MetricSnapshot(publication_id=publication.id, collected_at=now, metric_definition_version=RETENTION_DEFINITION, metric_name=name, metric_value=summary[name], unit="ratio", features_json=features, is_demo=False))
        count += 1
    db.add(MetricSnapshot(publication_id=publication.id, collected_at=now, metric_definition_version=RETENTION_DEFINITION, metric_name="relativeRetentionMedian", metric_value=statistics.median(relative) if relative else None, unit="ratio", features_json=features, is_demo=False))
    db.add(MetricSnapshot(publication_id=publication.id, collected_at=now, metric_definition_version=RETENTION_DEFINITION, metric_name="retentionCurve", metric_value=float(len(points)), unit="points", features_json={**features, "points": points, "scenes": summary["scenes"]}, is_demo=False))
    db.commit()
    return count + 2


def collect_due(db: Session, collect: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    due = []
    errors = []
    collected = 0
    attempted = set()
    for publication in db.query(Publication).filter(Publication.status == "PUBLISHED").all():
        published = publication.published_at
        if published is None:
            continue
        published = _as_utc(published)
        age_days = (now - published).total_seconds() / 86400
        targets = [age for age in (1, 3, 7, 28) if age_days >= age]
        existing = db.query(MetricSnapshot).filter(MetricSnapshot.publication_id == publication.id).all()
        for target in targets:
            if not any(round((_as_utc(snap.collected_at) - published).total_seconds() / 86400) == target for snap in existing):
                due.append({"publication_id": publication.id, "target_days": target, "platform": publication.platform})
        if collect and due and due[-1]["publication_id"] == publication.id and publication.id not in attempted:
            attempted.add(publication.id)
            if publication.platform == "youtube" and get_settings().youtube_refresh_token:
                try:
                    collected += collect_youtube_analytics(db, publication)
                except Exception as exc:
                    errors.append({"publication_id": publication.id, "error": type(exc).__name__})
                try:
                    collected += collect_youtube_retention(db, publication)
                except Exception as exc:
                    errors.append({"publication_id": publication.id, "kind": "retention", "error": type(exc).__name__})
    return {"due": due, "status": "collected_where_configured_else_manual_import_required", "collected": collected, "errors": errors}
