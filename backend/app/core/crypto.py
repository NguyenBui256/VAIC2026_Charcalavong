"""Stored-credential crypto — Fernet symmetric encrypt/decrypt + masking.

Story 2.7 T1 (AR-14 stored credentials / NFR-6). The Fernet key comes from
`Settings.encryption_key` (`VAIC_ENCRYPTION_KEY` env var). Mirrors the
Story 1.6 LLM-key convention: a missing/blank key raises a clear error
**when encrypt/decrypt is called**, not at import time — so the app can
still boot (and other, unrelated endpoints work) even if this key was
never configured.

`mask_secret` is the only thing allowed to leave the backend for a stored
credential (AC2) — callers must never serialize the plaintext or ciphertext.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import ValidationError
from app.core.settings import get_settings

__all__ = ["encrypt_secret", "decrypt_secret", "mask_secret"]


def _fernet() -> Fernet:
    """Build a `Fernet` instance from `VAIC_ENCRYPTION_KEY`.

    Raises a clear `ValidationError` at call time if the key is missing or
    malformed — never at import time (Story 1.6 convention).
    """
    key = get_settings().encryption_key
    if not key:
        raise ValidationError(
            "VAIC_ENCRYPTION_KEY is not configured — cannot encrypt/decrypt "
            "stored credentials. Set a urlsafe base64 32-byte Fernet key.",
            code="encryption_key_missing",
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "VAIC_ENCRYPTION_KEY is malformed — must be a urlsafe base64 "
            "32-byte Fernet key.",
            code="encryption_key_invalid",
        ) from exc


def encrypt_secret(plaintext: str) -> str:
    """Encrypt `plaintext` (e.g. an auth header) into a Fernet token string."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a Fernet token string back to plaintext. Raises on bad token."""
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValidationError(
            "Stored credential could not be decrypted — ciphertext invalid "
            "or key mismatch.",
            code="decryption_failed",
        ) from exc


def mask_secret(plaintext: str) -> str:
    """Display-safe mask — reveals at most the last 4 chars (AC2).

    Preserves a leading auth-scheme word if present (e.g. "Bearer" in
    "Bearer abc123xyz") for readability: "Bearer ••••3xyz".
    """
    if not plaintext:
        return ""
    scheme, _, rest = plaintext.partition(" ")
    if rest and scheme.isalpha():
        tail = rest[-4:] if len(rest) >= 4 else rest
        return f"{scheme} ••••{tail}"
    tail = plaintext[-4:] if len(plaintext) >= 4 else plaintext
    return f"••••{tail}"
