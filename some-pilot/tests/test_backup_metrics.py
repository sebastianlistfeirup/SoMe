from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.db.models import Publication
from app.pipeline.backup import create_backup, restore_to_directory, verify_backup
from app.pipeline.metrics import import_csv


def test_backup_verify_and_restore(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "backup_key", "")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db.info['database_path']}")
    destination = db.info["tmp_path"] / "backups"
    result = create_backup(db, destination, verify=True)
    assert result["verified"] and not result["encrypted"]
    assert verify_backup(Path(result["path"]))
    restored = restore_to_directory(Path(result["path"]), db.info["tmp_path"] / "restored")
    assert restored["integrity"] == "ok"
    assert not restored["publish_enabled"] and not restored["paid_jobs_enabled"]


def test_encrypted_backup_verify_and_restore(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "backup_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db.info['database_path']}")
    destination = db.info["tmp_path"] / "encrypted-backups"
    result = create_backup(db, destination, verify=True)
    assert result["verified"] and result["encrypted"]
    assert Path(result["path"]).suffix == ".enc"
    assert verify_backup(Path(result["path"]))
    restored = restore_to_directory(Path(result["path"]), db.info["tmp_path"] / "restored-encrypted")
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


def test_backup_and_restore_reject_path_traversal(db):
    import zipfile
    path = db.info["tmp_path"] / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../outside.txt", "must not escape")
    with pytest.raises(ValueError, match="backup_unsafe_path"):
        verify_backup(path)
    with pytest.raises(ValueError, match="backup_unsafe_path"):
        restore_to_directory(path, db.info["tmp_path"] / "restore-unsafe")
    assert not (db.info["tmp_path"] / "outside.txt").exists()


def test_metrics_csv_import_is_idempotent(db, awaiting_video):
    from app.db.models import MetricSnapshot
    publication = Publication(video_version_id=awaiting_video.id, platform="youtube", account="demo", idempotency_key="metrics-idempotent", status="PUBLISHED")
    db.add(publication)
    db.commit()
    path = db.info["tmp_path"] / "metrics-idempotent.csv"
    path.write_text("publication_id,metric_name,metric_value,collected_at,metric_definition_version\n1,views,10,2026-01-01T00:00:00Z,v1\n")
    assert import_csv(db, path, is_demo=True) == 1
    assert import_csv(db, path, is_demo=True) == 0
    assert db.query(MetricSnapshot).count() == 1
