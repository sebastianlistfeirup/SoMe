"""RFC 6238 time-based one-time passwords (30 s, 6 digits, SHA-1) without extra dependencies.

The shared secret is stored encrypted with a key derived from APP_SECRET_KEY.
Codes are accepted one step either side for clock drift, and a used step can
never be replayed. Recovery codes are stored as Argon2 hashes and work once.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

STEP_SECONDS = 30
DIGITS = 6
ISSUER = "SoMe-maskinen"
_hasher = PasswordHasher()


def _fernet() -> Fernet:
    key = get_settings().app_secret_key
    if len(key) < 16:
        raise ValueError("app_secret_key_required_for_2fa")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("totp:" + key).encode()).digest()))


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("totp_secret_unreadable") from exc


def code_at(secret: str, step: int) -> str:
    padded = secret + "=" * (-len(secret) % 8)
    digest = hmac.new(base64.b32decode(padded, casefold=True), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def verify(secret: str, code: str, last_step: int | None = None, now: float | None = None, window: int = 1) -> int | None:
    """Return the matched step, or None. Steps at or before last_step are rejected (no replay)."""
    code = "".join(character for character in code if character.isdigit())
    if len(code) != DIGITS:
        return None
    current = int((now if now is not None else time.time()) // STEP_SECONDS)
    for step in range(current - window, current + window + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(username: str, secret: str) -> str:
    label = quote(f"{ISSUER}:{username}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"


def qr_svg(uri: str) -> str:
    """Inline SVG QR code for the otpauth URI (scanning avoids typing the 32-character key)."""
    import segno

    return segno.make(uri, error="m").svg_inline(scale=6, border=4, dark="#101828", light="#ffffff")


def grouped(secret: str) -> str:
    return " ".join(secret[index:index + 4] for index in range(0, len(secret), 4))


def new_recovery_codes(count: int = 8) -> tuple[list[str], list[str]]:
    codes = [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(count)]
    return codes, [_hasher.hash(code) for code in codes]


def use_recovery_code(hashes: list[str], code: str) -> list[str] | None:
    """Return the remaining hashes if the code matched (it is consumed), else None."""
    cleaned = code.strip().lower()
    for index, stored in enumerate(hashes):
        try:
            _hasher.verify(stored, cleaned)
        except (VerificationError, VerifyMismatchError):
            continue
        return hashes[:index] + hashes[index + 1:]
    return None
