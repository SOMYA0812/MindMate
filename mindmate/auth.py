"""Local account security for MindMate.

MindMate stays offline, so there is no external identity provider. Passwords are
derived with PBKDF2-HMAC-SHA256 from the Python standard library, using a
per-user random salt and a high iteration count. Only the derived hash is ever
stored; plain-text passwords are never written to the database or a log.

Because there is no email service, account recovery uses a one-time recovery
code generated at sign-up. Only its hash is stored. The code is shown once and
the user is asked to keep it somewhere safe.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

PASSWORD_ITERATIONS = 600_000
RECOVERY_ITERATIONS = 250_000
PASSWORD_MIN_LENGTH = 8
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 32

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def validate_username(username: str) -> str | None:
    """Return a human-readable error, or ``None`` when the username is valid."""
    value = (username or "").strip()
    if len(value) < USERNAME_MIN_LENGTH:
        return f"Use at least {USERNAME_MIN_LENGTH} characters for your username."
    if len(value) > USERNAME_MAX_LENGTH:
        return f"Keep your username under {USERNAME_MAX_LENGTH} characters."
    if not _USERNAME_RE.match(value):
        return "Use only letters, numbers, dots, dashes or underscores."
    return None


def validate_password(password: str) -> str | None:
    """Return a human-readable error, or ``None`` when the password is acceptable."""
    value = password or ""
    if len(value) < PASSWORD_MIN_LENGTH:
        return f"Use at least {PASSWORD_MIN_LENGTH} characters."
    if not any(ch.isalpha() for ch in value):
        return "Include at least one letter."
    if not any(ch.isdigit() for ch in value):
        return "Include at least one number."
    if value.strip() != value:
        return "Do not start or end the password with a space."
    return None


def hash_secret(secret: str, *, iterations: int = PASSWORD_ITERATIONS,
                salt: str | None = None) -> tuple[str, str, int]:
    """Return ``(salt_hex, hash_hex, iterations)`` for a secret."""
    salt_hex = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", secret.encode("utf-8"), bytes.fromhex(salt_hex), iterations
    )
    return salt_hex, derived.hex(), iterations


def verify_secret(secret: str, salt_hex: str, expected_hash: str, iterations: int) -> bool:
    if not salt_hex or not expected_hash or not iterations:
        return False
    try:
        salt_bytes = bytes.fromhex(salt_hex)
        iterations_int = int(iterations)
    except (ValueError, TypeError):
        return False
    candidate_bytes = hashlib.pbkdf2_hmac(
        "sha256", secret.encode("utf-8"), salt_bytes, iterations_int
    )
    return hmac.compare_digest(candidate_bytes.hex(), expected_hash)


def generate_recovery_code() -> str:
    """A readable, high-entropy recovery code such as ``MM-7K2P-Q9XD-4RTM``."""
    groups = [
        "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(4))
        for _ in range(3)
    ]
    return "MM-" + "-".join(groups)


def normalize_recovery_code(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (code or "")).upper()


def recovery_matches(code: str, salt_hex: str, expected_hash: str, iterations: int) -> bool:
    return verify_secret(normalize_recovery_code(code), salt_hex, expected_hash, iterations)
