from datetime import datetime, timedelta, timezone

from app.db.models import MetricSnapshot, Publication, Setting
from app.pipeline.learning import weekly_learning
from app.pipeline.research import priority_score


def test_priority_formula():
    assert priority_score(100, 100, 100, 100, 100) == 100
    assert priority_score(95, 92, 55, 65, 60) == 79.75


def test_learning_uses_samples_and_versions(db, awaiting_video):
    now = datetime.now(timezone.utc)
    publication = Publication(video_version_id=awaiting_video.id, platform="youtube", account="demo", idempotency_key="demo-pub", status="PUBLISHED", published_at=now - timedelta(days=7))
    db.add(publication)
    db.flush()
    for value in (100, 140):
        db.add(MetricSnapshot(publication_id=publication.id, collected_at=now, metric_definition_version="demo-v1", metric_name="views", metric_value=value, is_demo=True))
    db.commit()
    report = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    assert report["data_mode"] == "demo"
    assert report["observed"][0]["sample_size"] == 2
    assert report["observed"][0]["median_views"] == 120
    assert report["model_version"] == 1
    assert db.get(Setting, "learning_model") is None
    assert "cannot establish causality" in report["possible_explanations"][0]
    second = weekly_learning(db, db.info["tmp_path"], is_demo=True)
    assert second["model_version"] == 2
