"""Story 2.8 (carried item #4) — `serialize_integration`'s decrypt fallback.

Only the ciphertext-specific `decryption_failed` error gets the masked
"••••" fallback. A misconfigured/missing `VAIC_ENCRYPTION_KEY` (deployment
error, not a per-row data issue) must fail loud instead of silently
rendering the mask for every integration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.crypto import encrypt_secret
from app.core.errors import ValidationError
from app.core.settings import get_settings
from app.modules.agent_builder.integration_service import serialize_integration
from app.modules.agent_builder.models import ApiIntegration


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _integration(ciphertext: str) -> ApiIntegration:
    now = datetime.now(UTC)
    return ApiIntegration(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        name="Demo",
        base_url="https://stub.example.com",
        auth_header_encrypted=ciphertext,
        schema_=None,
        created_at=now,
        updated_at=now,
    )


def test_decryption_failed_falls_back_to_masked_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bad/mismatched ciphertext (but a configured key) -> masked fallback, not a raise."""
    monkeypatch.setenv("VAIC_ENCRYPTION_KEY", "Qn0gDeH7NIVztbAzXnSVw43RqsrrbaEONNY6TvSGIW4=")
    integration = _integration("not-a-valid-fernet-token")

    payload = serialize_integration(integration)

    assert payload["auth_header_masked"] == "••••"


def test_missing_encryption_key_fails_loud_not_masked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A misconfigured VAIC_ENCRYPTION_KEY must raise, never silently render '••••'."""
    monkeypatch.setenv("VAIC_ENCRYPTION_KEY", "")
    integration = _integration("irrelevant-ciphertext")

    with pytest.raises(ValidationError, match="VAIC_ENCRYPTION_KEY"):
        serialize_integration(integration)


def test_round_trip_still_masks_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity: a correctly-encrypted header still round-trips through the mask."""
    monkeypatch.setenv("VAIC_ENCRYPTION_KEY", "Qn0gDeH7NIVztbAzXnSVw43RqsrrbaEONNY6TvSGIW4=")
    ciphertext = encrypt_secret("Bearer super-secret-token-abcd1234")
    integration = _integration(ciphertext)

    payload = serialize_integration(integration)

    assert payload["auth_header_masked"] == "Bearer ••••1234"
