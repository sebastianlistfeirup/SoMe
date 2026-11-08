import re
import time
from datetime import datetime
from pathlib import Path

from app.config import get_settings


def prune_backups(directory: Path, daily: int = 7, weekly: int = 4) -> list[str]:
    candidates = [path for path in directory.glob("some-backup-*.zip*") if re.match(r"some-backup-\d{8}T\d{6}Z", path.name)]
    ordered = sorted(candidates, key=lambda path: path.name, reverse=True)
    keep = set(ordered[:daily])
    by_week = {}
    for path in ordered:
        stamp = datetime.strptime(path.name.removeprefix("some-backup-")[:16], "%Y%m%dT%H%M%SZ")
        by_week.setdefault(stamp.isocalendar()[:2], []).append(path)
    for paths in by_week.values():
        keep.update(paths[:1])
    if len(by_week) > weekly:
        for week in sorted(by_week, reverse=True)[weekly:]:
            keep.difference_update(by_week[week])
    deleted = []
    for path in ordered:
        if path not in keep:
            path.unlink()
            deleted.append(str(path))
    return deleted


def cleanup_temporary_files(older_than_seconds: int = 86400) -> list[str]:
    settings = get_settings()
    deleted = []
    cutoff = time.time() - older_than_seconds
    for name in ("tmp", "quarantine"):
        root = settings.data_dir / name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                deleted.append(str(path))
    return deleted
