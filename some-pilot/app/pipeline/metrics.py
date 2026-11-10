import csv
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import MetricSnapshot, Publication, VideoVersion

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
    return {"due": due, "status": "collected_where_configured_else_manual_import_required", "collected": collected, "errors": errors}
