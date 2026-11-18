"""Full backups: SQLite online backup plus the approved/scheduled/published outputs.

Everything streams. Backups are several GB (every published video.mp4), so no step may
hold a whole archive, a whole video or a whole ciphertext in memory (the worker has a
5 GB mem_limit and the old read_bytes() version was OOM-killed).

Encrypted formats, both keyed by BACKUP_KEY (a Fernet key):

* ``.zip.encc`` (written since 2026-11-18): chunked AES-256-GCM.
  Header ``MAGIC | chunk_size (u32 BE) | salt (32 bytes)``; the per-file key is
  HKDF-SHA256(BACKUP_KEY bytes, salt). Then one record per chunk of at most
  ``chunk_size`` plaintext bytes: ``final flag (u8) | ciphertext length (u32 BE) | ciphertext+tag``.
  The nonce is the chunk index, and the header, chunk index and final flag are
  authenticated, so reordered, dropped, truncated or appended chunks fail to decrypt.
* ``.zip.enc`` (older backups): one Fernet token over the whole zip. Still readable;
  it is decrypted as a stream and the HMAC is checked before the output is used.
"""

import base64
import binascii
import hashlib
import json
import os
import sqlite3
import stat
import struct
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hmac import HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import VideoVersion

CHUNKED_MAGIC = b"PPBKGCM1"
CHUNKED_SUFFIX = ".encc"
LEGACY_SUFFIX = ".enc"
CHUNK_SIZE = 16 * 1024 * 1024
MAX_CHUNK_SIZE = 64 * 1024 * 1024
COPY_BUFFER = 1024 * 1024
LEGACY_BASE64_BLOCK = 4 * 1024 * 1024
_HKDF_INFO = b"pixel-and-parameters/backup/aes-256-gcm-chunked/v1"
_SALT_BYTES = 32
_TAG_BYTES = 16
_RECORD_HEADER = struct.Struct(">BI")
# Already-compressed media gain nothing from deflate; storing them saves minutes of CPU.
_STORED_SUFFIXES = {".mp4", ".jpg", ".jpeg", ".png", ".webm", ".mov"}
_TEMP_PREFIX = ".tmp-backup-"


def _key_bytes(key: str) -> bytes:
    Fernet(key.encode())  # validates the key format exactly as before
    return base64.urlsafe_b64decode(key.encode())


def _file_key(key: str, salt: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=_HKDF_INFO).derive(_key_bytes(key))


def _chunk_aad(header: bytes, index: int, final: bool) -> bytes:
    return header + struct.pack(">QB", index, 1 if final else 0)


def _nonce(index: int) -> bytes:
    return index.to_bytes(12, "big")


class _EncryptingWriter:
    """Write-only, non-seekable stream that encrypts into ``raw`` one chunk at a time.

    zipfile accepts non-seekable outputs (it writes data descriptors), so the plaintext zip
    never touches the disk. Call ``finish()`` after the ZipFile is closed.
    """

    def __init__(self, raw, key: str, chunk_size: int | None = None):
        self._raw = raw
        self._chunk_size = chunk_size or CHUNK_SIZE
        salt = os.urandom(_SALT_BYTES)
        self._header = CHUNKED_MAGIC + struct.pack(">I", self._chunk_size) + salt
        self._aead = AESGCM(_file_key(key, salt))
        self._buffer = bytearray()
        self._index = 0
        self._finished = False
        raw.write(self._header)

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def write(self, data) -> int:
        if self._finished:
            raise ValueError("backup_writer_finished")
        self._buffer += data
        while len(self._buffer) >= self._chunk_size:
            self._emit(bytes(self._buffer[: self._chunk_size]), final=False)
            del self._buffer[: self._chunk_size]
        return len(data)

    def flush(self) -> None:
        self._raw.flush()

    def _emit(self, plain: bytes, final: bool) -> None:
        ciphertext = self._aead.encrypt(_nonce(self._index), plain, _chunk_aad(self._header, self._index, final))
        self._raw.write(_RECORD_HEADER.pack(1 if final else 0, len(ciphertext)))
        self._raw.write(ciphertext)
        self._index += 1

    def finish(self) -> None:
        if not self._finished:
            self._emit(bytes(self._buffer), final=True)
            self._buffer = bytearray()
            self._finished = True
            self._raw.flush()


def _read_exact(handle, size: int) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise ValueError("backup_truncated")
    return data


def _decrypt_chunked(source, out, key: str) -> None:
    """``source`` is positioned just after CHUNKED_MAGIC."""
    rest = _read_exact(source, 4 + _SALT_BYTES)
    chunk_size = struct.unpack(">I", rest[:4])[0]
    if not 0 < chunk_size <= MAX_CHUNK_SIZE:
        raise ValueError("backup_bad_header")
    header = CHUNKED_MAGIC + rest
    aead = AESGCM(_file_key(key, rest[4:]))
    index = 0
    while True:
        flag, length = _RECORD_HEADER.unpack(_read_exact(source, _RECORD_HEADER.size))
        if flag not in (0, 1) or not _TAG_BYTES <= length <= chunk_size + _TAG_BYTES:
            raise ValueError("backup_bad_chunk")
        ciphertext = _read_exact(source, length)
        try:
            out.write(aead.decrypt(_nonce(index), ciphertext, _chunk_aad(header, index, flag == 1)))
        except InvalidTag:
            raise ValueError("backup_decrypt_failed") from None
        index += 1
        if flag == 1:
            if source.read(1):
                raise ValueError("backup_trailing_data")
            return


def _base64_blocks(source, block: int):
    carry = b""
    while data := source.read(block):
        data = carry + data.translate(None, b" \t\r\n")
        cut = len(data) - len(data) % 4
        carry = data[cut:]
        if cut:
            try:
                yield base64.urlsafe_b64decode(data[:cut])
            except binascii.Error:
                raise ValueError("backup_decrypt_failed") from None
    if carry:
        raise ValueError("backup_decrypt_failed")


def _decrypt_legacy_fernet(source, out, key: str, block: int | None = None) -> None:
    """Streaming equivalent of ``Fernet(key).decrypt(token)`` for one whole-file token.

    Token: version 0x80 | timestamp (8) | IV (16) | AES-128-CBC ciphertext | HMAC-SHA256 (32).
    The 32-byte tail is held back until the end, then the HMAC is checked. The caller must
    discard ``out`` when this raises (verify and restore write it into a temporary directory).
    """
    raw_key = _key_bytes(key)
    mac = HMAC(raw_key[:16], hashes.SHA256())
    pending = b""
    decryptor = unpadder = None
    for decoded in _base64_blocks(source, block or LEGACY_BASE64_BLOCK):
        data = pending + decoded
        if decryptor is None:
            if len(data) < 25:
                pending = data
                continue
            if data[0] != 0x80:
                raise ValueError("backup_decrypt_failed")
            mac.update(data[:25])
            decryptor = Cipher(algorithms.AES(raw_key[16:]), modes.CBC(data[9:25])).decryptor()
            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            data = data[25:]
        if len(data) <= 32:
            pending = data
            continue
        body, pending = data[:-32], data[-32:]
        mac.update(body)
        out.write(unpadder.update(decryptor.update(body)))
    if decryptor is None or len(pending) != 32:
        raise ValueError("backup_decrypt_failed")
    try:
        mac.verify(pending)
        out.write(unpadder.update(decryptor.finalize()) + unpadder.finalize())
    except (InvalidSignature, ValueError):
        raise ValueError("backup_decrypt_failed") from None


def is_encrypted_backup(path: Path) -> bool:
    return path.suffix in (LEGACY_SUFFIX, CHUNKED_SUFFIX)


def decrypt_backup_to(path: Path, out_path: Path, key: str) -> None:
    """Decrypt either encrypted format into ``out_path`` without loading it into memory."""
    with path.open("rb") as source, out_path.open("wb") as out:
        if source.read(len(CHUNKED_MAGIC)) == CHUNKED_MAGIC:
            _decrypt_chunked(source, out, key)
        else:
            source.seek(0)
            _decrypt_legacy_fernet(source, out, key)


def _scratch_dir(*candidates: Path) -> str | None:
    """Prefer a directory on the data volume next to the backup over the container's /tmp."""
    for candidate in candidates:
        if candidate.is_dir() and os.access(candidate, os.W_OK):
            return str(candidate)
    return None


@contextmanager
def _plain_archive(path: Path, *scratch: Path):
    """Yield a path to the plaintext zip: the file itself, or a temporary decrypted copy."""
    if not is_encrypted_backup(path):
        yield path
        return
    key = get_settings().backup_key
    if not key:
        raise ValueError("backup_key_required")
    with tempfile.TemporaryDirectory(prefix=_TEMP_PREFIX, dir=_scratch_dir(*scratch, path.parent)) as temp:
        archive_path = Path(temp) / "backup.zip"
        decrypt_backup_to(path, archive_path, key)
        yield archive_path


def _check_member_paths(archive: zipfile.ZipFile, target: Path) -> None:
    root = target.resolve()
    for member in archive.infolist():
        name = member.filename
        path = Path(name)
        if not name or name.startswith(("/", "\\")) or path.is_absolute() or path.drive or ".." in path.parts or "\\" in name or stat.S_ISLNK(member.external_attr >> 16):
            raise ValueError("backup_unsafe_path")
        destination = (root / path).resolve()
        if root != destination and root not in destination.parents:
            raise ValueError("backup_unsafe_path")


def _extract_safely(archive: zipfile.ZipFile, target: Path) -> None:
    _check_member_paths(archive, target)
    archive.extractall(target.resolve())


def _add_file(archive: zipfile.ZipFile, path: Path, arcname: str) -> str:
    """Copy one file into the archive in COPY_BUFFER pieces and return its SHA-256."""
    info = zipfile.ZipInfo.from_file(path, arcname)
    info.compress_type = zipfile.ZIP_STORED if path.suffix.lower() in _STORED_SUFFIXES else zipfile.ZIP_DEFLATED
    digest = hashlib.sha256()
    with path.open("rb") as source, archive.open(info, "w") as target:
        while chunk := source.read(COPY_BUFFER):
            digest.update(chunk)
            target.write(chunk)
    return digest.hexdigest()


def _write_archive(archive: zipfile.ZipFile, db: Session, db_path: Path) -> None:
    archive.write(db_path, "some.db")
    hashes = {}
    for video in db.query(VideoVersion).filter(VideoVersion.status.in_(["APPROVED", "SCHEDULED", "PUBLISHED"])).all():
        for name in ("manifest.json", "rights.json", "video.mp4", "thumbnail.jpg", "post.json"):
            path = Path(video.output_dir) / name
            if path.exists():
                relative = f"versions/{video.id}/{name}"
                hashes[relative] = _add_file(archive, path, relative)
    archive.writestr("backup-manifest.json", json.dumps({"created_at_utc": datetime.now(timezone.utc).isoformat(), "files_sha256": hashes}, indent=2))


def remove_stale_temp_dirs(directory: Path, older_than_seconds: int = 86400) -> list[str]:
    """Scratch directories of runs that were killed (OOM, container stop) are never cleaned up
    by TemporaryDirectory, and each holds a copy of the database or a decrypted archive."""
    import shutil
    import time

    cutoff = time.time() - older_than_seconds
    removed = []
    for path in directory.glob(f"{_TEMP_PREFIX}*"):
        if path.is_dir() and path.stat().st_mtime < cutoff:
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path.name)
    return removed


def create_backup(db: Session, destination: Path | None = None, verify: bool = True) -> dict:
    settings = get_settings()
    destination = destination or settings.data_dir / "backups"
    destination.mkdir(parents=True, exist_ok=True)
    remove_stale_temp_dirs(destination)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    encrypted = bool(settings.backup_key)
    final = destination / (f"some-backup-{stamp}.zip{CHUNKED_SUFFIX}" if encrypted else f"some-backup-{stamp}.zip")
    with tempfile.TemporaryDirectory(prefix=_TEMP_PREFIX, dir=destination) as temp:
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
        # Written inside the temp dir and renamed at the end, so a killed run never leaves
        # a half-written some-backup-* that pruning or the restore drill would pick up.
        partial = root / "backup.partial"
        with partial.open("wb") as raw:
            if encrypted:
                writer = _EncryptingWriter(raw, settings.backup_key)
                with zipfile.ZipFile(writer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    _write_archive(archive, db, db_path)
                writer.finish()
            else:
                with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    _write_archive(archive, db, db_path)
            raw.flush()
            os.fsync(raw.fileno())
        os.replace(partial, final)
    result = {"path": str(final), "encrypted": encrypted, "verified": False, "external_offsite": False, "bytes": final.stat().st_size}
    if verify:
        result["verified"] = verify_backup(final)
    return result


def verify_backup(path: Path) -> bool:
    """Check every member's CRC and manifest hash by streaming it, then the database's integrity.

    Only some.db is extracted; the videos are read straight out of the archive.
    """
    with _plain_archive(path) as archive_path, zipfile.ZipFile(archive_path) as archive:
        with tempfile.TemporaryDirectory(prefix=_TEMP_PREFIX, dir=_scratch_dir(path.parent)) as temp:
            _check_member_paths(archive, Path(temp))
            names = set(archive.namelist())
            if "some.db" not in names or "backup-manifest.json" not in names:
                raise ValueError("backup_incomplete")
            expected = json.loads(archive.read("backup-manifest.json"))["files_sha256"]
            if not set(expected) <= names:
                raise ValueError("backup_file_hash_mismatch")
            for info in archive.infolist():
                digest = hashlib.sha256()
                try:
                    with archive.open(info) as member:
                        while chunk := member.read(COPY_BUFFER):
                            digest.update(chunk)
                except (zipfile.BadZipFile, EOFError, OSError):
                    raise ValueError("backup_zip_corrupt") from None
                if info.filename in expected and digest.hexdigest() != expected[info.filename]:
                    raise ValueError("backup_file_hash_mismatch")
            connection = sqlite3.connect(archive.extract("some.db", temp))
            try:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("backup_database_integrity_failed")
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "video_versions" not in tables:
                    raise ValueError("backup_schema_missing")
            finally:
                connection.close()
    return True


def restore_to_directory(path: Path, target: Path) -> dict:
    if target.exists() and any(target.iterdir()):
        raise ValueError("restore_target_must_be_empty")
    target.mkdir(parents=True, exist_ok=True)
    with _plain_archive(path, target.parent) as archive_path, zipfile.ZipFile(archive_path) as archive:
        _extract_safely(archive, target)
    connection = sqlite3.connect(target / "some.db")
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    return {"restored_to": str(target), "integrity": integrity, "publish_enabled": False, "paid_jobs_enabled": False, "note": "No environment/secrets restored; external publishing remains disabled by configuration."}


def offsite_configured() -> bool:
    settings = get_settings()
    return bool(settings.offsite_webdav_url and settings.offsite_username and settings.offsite_password)


def upload_offsite(path: Path) -> dict:
    """Upload one encrypted backup to a WebDAV folder (e.g. a storage box) and verify its size.

    Unencrypted backups are never sent off the server. The provider and price are
    the owner's decision; nothing is uploaded until OFFSITE_* settings exist.
    The file is streamed from disk with an explicit Content-Length.
    """
    import httpx

    settings = get_settings()
    if not offsite_configured():
        return {"status": "not_configured"}
    if not is_encrypted_backup(path):
        raise ValueError("offsite_requires_encrypted_backup")
    if not settings.offsite_webdav_url.startswith("https://"):
        raise ValueError("offsite_requires_https")
    url = settings.offsite_webdav_url.rstrip("/") + "/" + path.name
    auth = (settings.offsite_username, settings.offsite_password)
    size = path.stat().st_size
    digest = hashlib.sha256()
    sent = 0

    def body():
        nonlocal sent
        with path.open("rb") as handle:
            while chunk := handle.read(COPY_BUFFER):
                digest.update(chunk)
                sent += len(chunk)
                yield chunk

    response = httpx.put(url, content=body(), headers={"Content-Length": str(size)}, auth=auth, timeout=300)
    response.raise_for_status()
    if sent != size:
        raise ValueError("offsite_upload_incomplete")
    head = httpx.head(url, auth=auth, timeout=60)
    head.raise_for_status()
    remote_size = int(head.headers.get("content-length", -1))
    if remote_size != size:
        raise ValueError("offsite_size_mismatch")
    return {"status": "uploaded", "name": path.name, "bytes": size, "sha256": digest.hexdigest()}


def restore_drill(backup_dir: Path, drill_root: Path) -> dict:
    """Monthly proof that the newest backup can actually be restored. The restored copy is removed afterwards."""
    import shutil

    candidates = sorted(backup_dir.glob("some-backup-*.zip*"), key=lambda item: item.name, reverse=True)
    if not candidates:
        raise ValueError("no_backup_to_restore")
    latest = candidates[0]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = drill_root / stamp
    started = datetime.now(timezone.utc)
    try:
        result = restore_to_directory(latest, target)
        counts = {}
        connection = sqlite3.connect(target / "some.db")
        try:
            for table in ("video_versions", "publications", "metric_snapshots", "jobs"):
                counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            connection.close()
    finally:
        shutil.rmtree(target, ignore_errors=True)
    report = {"backup": latest.name, "integrity": result["integrity"], "row_counts": counts, "seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 2), "restored_copy_removed": True, "at": started.isoformat()}
    if result["integrity"] != "ok":
        raise ValueError("restore_drill_integrity_failed")
    drill_root.mkdir(parents=True, exist_ok=True)
    (drill_root / f"drill-{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
