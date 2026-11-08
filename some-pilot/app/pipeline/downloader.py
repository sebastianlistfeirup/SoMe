import ipaddress
import mimetypes
import socket
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from app.config import get_settings


class UnsafeDownload(ValueError):
    pass


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeDownload("only_https_public_urls_without_credentials")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeDownload("dns_resolution_failed") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise UnsafeDownload("private_or_non_global_address_blocked")


def detect_media_type(path: Path) -> str:
    with path.open("rb") as handle:
        header = handle.read(32)
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video/mp4"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "audio/wav"
    raise UnsafeDownload("unknown_or_disallowed_file_signature")


def download(url: str, quarantine: Path) -> tuple[Path, dict]:
    settings = get_settings()
    quarantine.mkdir(parents=True, exist_ok=True)
    current = url
    redirects = 0
    with httpx.Client(follow_redirects=False, timeout=settings.download_timeout_seconds) as client:
        while True:
            validate_public_url(current)
            with client.stream("GET", current, headers={"User-Agent": "SoMePilot/0.1"}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if redirects >= 5 or "location" not in response.headers:
                        raise UnsafeDownload("too_many_or_invalid_redirects")
                    current = urljoin(current, response.headers["location"])
                    redirects += 1
                    continue
                response.raise_for_status()
                length = response.headers.get("content-length")
                if length and int(length) > settings.download_max_bytes:
                    raise UnsafeDownload("file_too_large")
                content_type = response.headers.get("content-type", "").split(";")[0]
                if content_type and not (content_type.startswith(("video/", "image/", "audio/")) or content_type == "application/octet-stream"):
                    raise UnsafeDownload("content_type_not_media")
                target = quarantine / f"{uuid.uuid4()}.download"
                size = 0
                with target.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > settings.download_max_bytes:
                            handle.close()
                            target.unlink(missing_ok=True)
                            raise UnsafeDownload("file_too_large_while_streaming")
                        handle.write(chunk)
                detected = detect_media_type(target)
                suffix = mimetypes.guess_extension(detected) or ".bin"
                final = target.with_suffix(suffix)
                target.rename(final)
                return final, {"source_url": url, "final_url": current, "bytes": size, "media_type": detected, "redirects": redirects}
