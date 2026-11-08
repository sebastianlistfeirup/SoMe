from pathlib import Path

import pytest

from app.config import get_settings
from app.db.models import Publication
from app.pipeline.backup import create_backup, restore_to_directory, verify_backup
from app.pipeline.metrics import import_csv


def test_backup_verify_and_restore(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db.info['database_path']}")
    destination = db.info["tmp_path"] / "backups"
    result = create_backup(db, destination, verify=True)
    assert result["verified"] and not result["encrypted"]
    assert verify_backup(Path(result["path"]))
    restored = restore_to_directory(Path(result["path"]), db.info["tmp_path"] / "restored")
    assert restored["integrity"] == "ok"
    assert not restored["publish_enabled"] and not restored["paid_jobs_enabled"]


def test_metrics_reject_demo_production_mixing(db, awaiting_video):
    publication = Publication(video_version_id=awaiting_video.id, platform="youtube", account="demo", idempotency_key="metrics-demo", status="PUBLISHED")
    db.add(publication)
    db.commit()
    path = db.info["tmp_path"] / "metrics.csv"
    path.write_text("publication_id,metric_name,metric_value,collected_at,metric_definition_version\n1,views,10,2026-01-01T00:00:00Z,v1\n")
    with pytest.raises(ValueError, match="demo_production_mixing"):
        import_csv(db, path, is_demo=False)
    assert import_csv(db, path, is_demo=True) == 1
