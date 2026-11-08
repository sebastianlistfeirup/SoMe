import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import VideoVersion


def create_backup(db: Session, destination: Path | None = None, verify: bool = True) -> dict:
    settings = get_settings()
    destination = destination or settings.data_dir / "backups"
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with tempfile.TemporaryDirectory(dir=destination) as temp:
        root = Path(temp)
        db_path = root / "some.db"
        source_path = Path(settings.database_url.removeprefix("sqlite:///"))
        source = sqlite3.connect(source_path)
        target = sqlite3.connect(db_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        archive_path = root / "backup.zip"
        hashes = {}
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(db_path, "some.db")
            for video in db.query(VideoVersion).filter(VideoVersion.status.in_(["APPROVED", "SCHEDULED", "PUBLISHED"])).all():
                for name in ("manifest.json", "rights.json", "video.mp4", "thumbnail.jpg", "post.json"):
                    path = Path(video.output_dir) / name
                    if path.exists():
                        relative = f"versions/{video.id}/{name}"
                        archive.write(path, relative)
                        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            archive.writestr("backup-manifest.json", json.dumps({"created_at_utc": datetime.now(timezone.utc).isoformat(), "files_sha256": hashes}, indent=2))
        encrypted = bool(settings.backup_key)
        if encrypted:
            final = destination / f"some-backup-{stamp}.zip.enc"
            final.write_bytes(Fernet(settings.backup_key.encode()).encrypt(archive_path.read_bytes()))
        else:
            final = destination / f"some-backup-{stamp}.zip"
            final.write_bytes(archive_path.read_bytes())
    result = {"path": str(final), "encrypted": encrypted, "verified": False, "external_offsite": False}
    if verify:
        result["verified"] = verify_backup(final)
    return result


def verify_backup(path: Path) -> bool:
    settings = get_settings()
    with tempfile.TemporaryDirectory() as temp:
        archive_path = Path(temp) / "backup.zip"
        if path.suffix == ".enc":
            if not settings.backup_key:
                raise ValueError("backup_key_required")
            archive_path.write_bytes(Fernet(settings.backup_key.encode()).decrypt(path.read_bytes()))
        else:
            archive_path.write_bytes(path.read_bytes())
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise ValueError("backup_zip_corrupt")
            archive.extractall(temp)
        connection = sqlite3.connect(Path(temp) / "some.db")
        try:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("backup_database_integrity_failed")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "video_versions" not in tables:
                raise ValueError("backup_schema_missing")
        finally:
            connection.close()
        manifest = json.loads((Path(temp) / "backup-manifest.json").read_text())
        for relative, expected in manifest["files_sha256"].items():
            if hashlib.sha256((Path(temp) / relative).read_bytes()).hexdigest() != expected:
                raise ValueError("backup_file_hash_mismatch")
    return True


def restore_to_directory(path: Path, target: Path) -> dict:
    if target.exists() and any(target.iterdir()):
        raise ValueError("restore_target_must_be_empty")
    settings = get_settings()
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        archive_path = Path(temp) / "backup.zip"
        if path.suffix == ".enc":
            archive_path.write_bytes(Fernet(settings.backup_key.encode()).decrypt(path.read_bytes()))
        else:
            archive_path.write_bytes(path.read_bytes())
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(target)
    connection = sqlite3.connect(target / "some.db")
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    return {"restored_to": str(target), "integrity": integrity, "publish_enabled": False, "paid_jobs_enabled": False, "note": "No environment/secrets restored; external publishing remains disabled by configuration."}
