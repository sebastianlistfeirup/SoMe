"""The full backup streams: chunked AES-GCM, old Fernet backups still readable, bounded memory."""

import base64
import hashlib
import io
import os
import tracemalloc
import zipfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.pipeline import backup
from app.pipeline.backup import create_backup, decrypt_backup_to, restore_drill, restore_to_directory, verify_backup


def _use_test_db(db, monkeypatch, key: str = "") -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "backup_key", key)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db.info['database_path']}")


def _approved_video(db, video, size: int) -> str:
    """Make the fixture video APPROVED and give it a video.mp4 of ``size`` bytes; return its sha256."""
    digest = hashlib.sha256()
    with (Path(video.output_dir) / "video.mp4").open("wb") as handle:
        remaining = size
        while remaining:
            block = os.urandom(min(remaining, 1 << 20))
            digest.update(block)
            handle.write(block)
            remaining -= len(block)
    video.status = "APPROVED"
    db.commit()
    return digest.hexdigest()


def _encrypt_chunked(plain: bytes, key: str, chunk_size: int) -> bytes:
    raw = io.BytesIO()
    writer = backup._EncryptingWriter(raw, key, chunk_size=chunk_size)
    writer.write(plain)
    writer.finish()
    return raw.getvalue()


def _decrypt_bytes(tmp_path: Path, blob: bytes, key: str) -> bytes:
    source = tmp_path / "blob.zip.encc"
    source.write_bytes(blob)
    out = tmp_path / "blob.out"
    decrypt_backup_to(source, out, key)
    return out.read_bytes()


def _records(blob: bytes) -> tuple[bytes, list[bytes]]:
    header_size = 8 + 4 + 32
    records, offset = [], header_size
    while offset < len(blob):
        length = int.from_bytes(blob[offset + 1:offset + 5], "big")
        records.append(blob[offset:offset + 5 + length])
        offset += 5 + length
    return blob[:header_size], records


@pytest.mark.parametrize("size", [0, 1, 1023, 1024, 1025, 5000])
def test_chunked_round_trip_at_chunk_boundaries(tmp_path, size):
    key = Fernet.generate_key().decode()
    plain = os.urandom(size)
    blob = _encrypt_chunked(plain, key, chunk_size=1024)
    assert blob.startswith(backup.CHUNKED_MAGIC)
    assert _decrypt_bytes(tmp_path, blob, key) == plain


def test_chunked_rejects_tampering_truncation_reordering_and_wrong_key(tmp_path):
    key = Fernet.generate_key().decode()
    blob = _encrypt_chunked(os.urandom(3500), key, chunk_size=1024)
    header, records = _records(blob)
    assert len(records) == 4 and records[-1][0] == 1

    flipped = bytearray(blob)
    flipped[len(header) + 40] ^= 1
    cases = {
        "backup_decrypt_failed": [bytes(flipped), header + records[1] + records[0] + b"".join(records[2:])],
        "backup_truncated": [header + b"".join(records[:-1]), blob[:-7]],
        "backup_trailing_data": [blob + b"x"],
    }
    for error, blobs in cases.items():
        for bad in blobs:
            with pytest.raises(ValueError, match=error):
                _decrypt_bytes(tmp_path, bad, key)
    # Dropping the final record and marking the previous one final must not authenticate either.
    forged = bytearray(records[-2])
    forged[0] = 1
    with pytest.raises(ValueError, match="backup_decrypt_failed"):
        _decrypt_bytes(tmp_path, header + b"".join(records[:-2]) + bytes(forged), key)
    with pytest.raises(ValueError, match="backup_decrypt_failed"):
        _decrypt_bytes(tmp_path, blob, Fernet.generate_key().decode())


@pytest.mark.parametrize("size", [0, 1, 15, 16, 17, 31, 32, 33, 1000, 65_537])
@pytest.mark.parametrize("block", [4, 8, 44, 4096])
def test_streaming_fernet_decrypt_matches_fernet(tmp_path, size, block):
    key = Fernet.generate_key().decode()
    plain = os.urandom(size)
    token = Fernet(key.encode()).encrypt(plain)
    out = io.BytesIO()
    backup._decrypt_legacy_fernet(io.BytesIO(token), out, key, block=block)
    assert out.getvalue() == plain == Fernet(key.encode()).decrypt(token)


def test_streaming_fernet_decrypt_rejects_tampering_and_wrong_key():
    key = Fernet.generate_key().decode()
    token = Fernet(key.encode()).encrypt(os.urandom(1000))
    decoded = bytearray(base64.urlsafe_b64decode(token))
    decoded[100] ^= 1
    tampered = base64.urlsafe_b64encode(bytes(decoded))
    for bad, bad_key in ((tampered, key), (token[:-8], key), (token, Fernet.generate_key().decode()), (b"not a token", key)):
        with pytest.raises(ValueError, match="backup_decrypt_failed"):
            backup._decrypt_legacy_fernet(io.BytesIO(bad), io.BytesIO(), bad_key, block=64)


def _legacy_backup(db, monkeypatch, backups: Path, key: str) -> Path:
    """Build a backup exactly as the pre-2026-11-18 code wrote it: one Fernet token, .zip.enc."""
    _use_test_db(db, monkeypatch)
    plain = Path(create_backup(db, backups, verify=False)["path"])
    legacy = plain.with_name(plain.name + ".enc")
    legacy.write_bytes(Fernet(key.encode()).encrypt(plain.read_bytes()))
    plain.unlink()
    monkeypatch.setattr(get_settings(), "backup_key", key)
    return legacy


def test_old_fernet_backups_still_verify_restore_and_drill(db, awaiting_video, monkeypatch):
    expected = _approved_video(db, awaiting_video, 300_000)
    key = Fernet.generate_key().decode()
    backups = db.info["tmp_path"] / "legacy-backups"
    legacy = _legacy_backup(db, monkeypatch, backups, key)
    assert legacy.suffix == ".enc"
    assert verify_backup(legacy)
    target = db.info["tmp_path"] / "restored-legacy"
    assert restore_to_directory(legacy, target)["integrity"] == "ok"
    assert hashlib.sha256((target / f"versions/{awaiting_video.id}/video.mp4").read_bytes()).hexdigest() == expected
    report = restore_drill(backups, db.info["tmp_path"] / "drills")
    assert report["backup"] == legacy.name and report["integrity"] == "ok"
    assert report["row_counts"]["video_versions"] == 1
    assert not any(path.name.startswith(".tmp-backup-") for path in backups.iterdir())


def test_restore_drill_reads_the_new_chunked_format(db, awaiting_video, monkeypatch):
    _approved_video(db, awaiting_video, 50_000)
    _use_test_db(db, monkeypatch, Fernet.generate_key().decode())
    backups = db.info["tmp_path"] / "backups"
    created = create_backup(db, backups, verify=True)
    assert created["verified"] and created["path"].endswith(".zip.encc")
    report = restore_drill(backups, db.info["tmp_path"] / "drills")
    assert report["backup"] == Path(created["path"]).name and report["integrity"] == "ok"
    assert sorted(path.name for path in backups.iterdir()) == [Path(created["path"]).name]


def test_verify_detects_a_changed_video_inside_the_archive(db, awaiting_video, monkeypatch):
    _approved_video(db, awaiting_video, 10_000)
    _use_test_db(db, monkeypatch)
    path = Path(create_backup(db, db.info["tmp_path"] / "backups", verify=True)["path"])
    rebuilt = path.with_name("some-backup-20260101T000000Z.zip")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(rebuilt, "w") as target:
        for info in source.infolist():
            data = source.read(info)
            target.writestr(info.filename, b"swapped" if info.filename.endswith("video.mp4") else data)
    with pytest.raises(ValueError, match="backup_file_hash_mismatch"):
        verify_backup(rebuilt)


def test_large_backup_round_trip_stays_within_a_small_memory_ceiling(db, awaiting_video, monkeypatch):
    """A 48 MB video goes through create + verify + restore (new format) and a 24 MB old-format
    decrypt while traced Python allocations stay far below the file sizes. The old code held the
    whole zip plus the whole ciphertext in memory (well over 100 MB here)."""
    video_size = 48 * 1024 * 1024
    expected = _approved_video(db, awaiting_video, video_size)
    key = Fernet.generate_key().decode()
    _use_test_db(db, monkeypatch, key)
    monkeypatch.setattr(backup, "CHUNK_SIZE", 1024 * 1024)
    monkeypatch.setattr(backup, "LEGACY_BASE64_BLOCK", 256 * 1024)
    ceiling = 12 * 1024 * 1024
    tmp = db.info["tmp_path"]

    tracemalloc.start()
    try:
        created = create_backup(db, tmp / "backups", verify=True)
        restored = restore_to_directory(Path(created["path"]), tmp / "restored-large")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert created["verified"] and created["bytes"] > video_size and restored["integrity"] == "ok"
    assert peak < ceiling, f"peak {peak / 2**20:.1f} MiB"
    restored_video = tmp / "restored-large" / f"versions/{awaiting_video.id}/video.mp4"
    assert hashlib.sha256(restored_video.read_bytes()).hexdigest() == expected

    legacy_plain = tmp / "legacy-plain.bin"
    legacy_plain.write_bytes(os.urandom(24 * 1024 * 1024))
    legacy = tmp / "legacy.zip.enc"
    legacy.write_bytes(Fernet(key.encode()).encrypt(legacy_plain.read_bytes()))
    out = tmp / "legacy-out.bin"
    tracemalloc.start()
    try:
        decrypt_backup_to(legacy, out, key)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < ceiling, f"legacy peak {peak / 2**20:.1f} MiB"
    assert out.read_bytes() == legacy_plain.read_bytes()


def test_a_killed_run_leaves_no_backup_file_behind(db, monkeypatch):
    _use_test_db(db, monkeypatch, Fernet.generate_key().decode())
    backups = db.info["tmp_path"] / "backups"

    def explode(*_args):
        raise RuntimeError("simulated crash mid-archive")

    monkeypatch.setattr(backup, "_write_archive", explode)
    with pytest.raises(RuntimeError):
        create_backup(db, backups, verify=True)
    assert list(backups.iterdir()) == []


def test_stale_scratch_dirs_of_killed_runs_are_removed(db, monkeypatch):
    _use_test_db(db, monkeypatch)
    backups = db.info["tmp_path"] / "backups"
    stale, fresh, foreign = backups / ".tmp-backup-stale", backups / ".tmp-backup-fresh", backups / "tmp-not-ours"
    for path in (stale, fresh, foreign):
        path.mkdir(parents=True)
        (path / "some.db").write_bytes(b"x")
    for path in (stale, foreign):
        os.utime(path, (1_000_000_000, 1_000_000_000))
    create_backup(db, backups, verify=True)
    assert not stale.exists() and fresh.exists() and foreign.exists()
