"""T9.1 — app.core.crypto: encrypt/decrypt round-trip, missing key, mask (AC2)."""

from __future__ import annotations

import pytest

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.core.errors import ValidationError
from app.core.settings import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Settings is `lru_cache`d — clear so monkeypatched env vars take effect."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_round_trip_encrypt_decrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAIC_ENCRYPTION_KEY", "Qn0gDeH7NIVztbAzXnSVw43RqsrrbaEONNY6TvSGIW4=")
    plaintext = "Bearer super-secret-token-abcd"
    ciphertext = encrypt_secret(plaintext)
    assert ciphertext != plaintext
    assert decrypt_secret(ciphertext) == plaintext


def test_ciphertext_differs_from_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAIC_ENCRYPTION_KEY", "Qn0gDeH7NIVztbAzXnSVw43RqsrrbaEONNY6TvSGIW4=")
    ciphertext = encrypt_secret("plain-value")
    assert "plain-value" not in ciphertext


def test_missing_key_raises_clear_error_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAIC_ENCRYPTION_KEY", "")
    with pytest.raises(ValidationError, match="VAIC_ENCRYPTION_KEY"):
        encrypt_secret("value")


def test_malformed_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAIC_ENCRYPTION_KEY", "not-a-valid-fernet-key")
    with pytest.raises(ValidationError, match="malformed"):
        encrypt_secret("value")


def test_mask_secret_never_leaks_more_than_last_4_chars() -> None:
    masked = mask_secret("Bearer abcdefgh1234wxyz")
    assert masked == "Bearer ••••wxyz"
    assert "abcdefgh1234" not in masked


def test_mask_secret_no_scheme_prefix() -> None:
    masked = mask_secret("supersecrettoken")
    assert masked == "••••oken"
    assert "supersecrettoken"[:-4] not in masked


def test_mask_secret_empty_string() -> None:
    assert mask_secret("") == ""
