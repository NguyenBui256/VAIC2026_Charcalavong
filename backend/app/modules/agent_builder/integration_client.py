"""Runtime API Integration client — outbound HTTP call + audit (Story 2.7 T6).

`call_integration` is the callable a Tool (Story 2.6) dispatches through when
it references an API Integration during a Workflow Run. It is the ONLY place
the decrypted auth header touches an outbound request — NFR-9 forbids it
from ever entering `audit.log()` input/output, a logger, or an exception
message. The header lives only in a local variable and the outbound request
object; it is never placed in a dict that flows to `audit.log()`.

`test_integration` is the config-time "Test Integration" affordance (AC9). It
pings `GET {base_url}/health` with the decrypted header and reports
connected/disconnected WITHOUT writing to `audit_trail` (OQ-1: Test pings
are diagnostic, not Workflow Run steps) and WITHOUT returning the header.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.crypto import decrypt_secret
from app.core.deps import crud_audit_ids
from app.core.ids import utcnow_iso_ms
from app.core.ports.audit import AuditEntry, AuditPort
from app.modules.agent_builder.integration_service import get_integration

__all__ = ["call_integration", "test_integration"]


def _auth_headers(auth_header: str) -> dict[str, str]:
    """Build the outbound header dict. The plaintext lives ONLY here."""
    return {"Authorization": auth_header} if auth_header else {}


def _safe_json(response: httpx.Response) -> Any:
    """Best-effort JSON parse of a response body; falls back to None."""
    try:
        return response.json()
    except ValueError:
        return None


def _emit_call_audit(
    audit: AuditPort,
    *,
    integration_id: uuid.UUID,
    agent_id: uuid.UUID,
    path: str,
    method: str,
    status_code: int,
    latency_ms: int,
) -> None:
    """Emit exactly one `integration.called` audit entry — METADATA ONLY (AC5, AC7)."""
    run_id, step_id = crud_audit_ids(str(integration_id))
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(agent_id),
            ts=utcnow_iso_ms(),
            type="integration.called",
            input={"integration_id": str(integration_id), "path": path, "method": method},
            output={"status_code": status_code, "latency_ms": latency_ms},
            latency_ms=latency_ms,
            model="",
        )
    )


def call_integration(
    session: Session,
    *,
    agent_id: uuid.UUID,
    integration_id: uuid.UUID,
    path: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    audit: AuditPort | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Dispatch a Tool's call through a registered Integration (AC4, AC5, AC6).

    Issues `{method} {base_url}/{path}` with the decrypted auth header
    attached. Updates `last_used_at` (AC8) and emits exactly one
    `integration.called` audit entry with metadata only — never the header.
    """
    integration = get_integration(session, agent_id=agent_id, integration_id=integration_id)
    plaintext_header = decrypt_secret(integration.auth_header_encrypted)
    url = f"{integration.base_url.rstrip('/')}/{path.lstrip('/')}"

    owns_client = client is None
    http_client = client or httpx.Client(timeout=10.0)
    started = time.monotonic()
    try:
        response = http_client.request(
            method, url, headers=_auth_headers(plaintext_header), json=body
        )
    finally:
        if owns_client:
            http_client.close()
    latency_ms = int((time.monotonic() - started) * 1000)

    integration.last_used_at = datetime.now(UTC)
    session.commit()

    _emit_call_audit(
        audit or PostgresAuditSink(),
        integration_id=integration.id,
        agent_id=integration.agent_id,
        path=path,
        method=method,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )
    return {
        "status_code": response.status_code,
        "latency_ms": latency_ms,
        "response": _safe_json(response),
    }


def test_integration(
    session: Session,
    *,
    agent_id: uuid.UUID,
    integration_id: uuid.UUID,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Test Integration affordance (AC9) — pings `GET {base_url}/health`.

    Diagnostic only: does NOT write `audit_trail` and does NOT return the
    header — only `{status, status_code, latency_ms}`.
    """
    integration = get_integration(session, agent_id=agent_id, integration_id=integration_id)
    plaintext_header = decrypt_secret(integration.auth_header_encrypted)
    url = f"{integration.base_url.rstrip('/')}/health"

    owns_client = client is None
    http_client = client or httpx.Client(timeout=10.0)
    started = time.monotonic()
    try:
        response = http_client.get(url, headers=_auth_headers(plaintext_header))
        status_code = response.status_code
    except httpx.HTTPError:
        latency_ms = int((time.monotonic() - started) * 1000)
        return {"status": "disconnected", "status_code": 0, "latency_ms": latency_ms}
    finally:
        if owns_client:
            http_client.close()

    latency_ms = int((time.monotonic() - started) * 1000)
    status = "connected" if 200 <= status_code < 300 else "disconnected"
    return {"status": status, "status_code": status_code, "latency_ms": latency_ms}
