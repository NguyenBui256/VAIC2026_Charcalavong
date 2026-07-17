"""T9.3/T9.4 — `integration_client.call_integration`/`test_integration`.

Uses `httpx.MockTransport` (no real network) and a `FakeAudit` (no real DB).
T9.4 is the MANDATORY NFR-9 no-leak test — the load-bearing security
assertion for AC7: the auth header must never appear in the AuditEntry
input/output, the call result, or captured log output.
"""

from __future__ import annotations

import logging
import uuid

import httpx
import pytest

from app.core.crypto import encrypt_secret
from app.core.ports.audit import AuditEntry
from app.core.settings import get_settings
from app.modules.agent_builder import integration_client as ic
from app.modules.agent_builder.models import ApiIntegration

SECRET_TOKEN = "Bearer super-secret-token-abcd1234"


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    monkeypatch.setenv("VAIC_ENCRYPTION_KEY", "Qn0gDeH7NIVztbAzXnSVw43RqsrrbaEONNY6TvSGIW4=")
    yield
    get_settings.cache_clear()


class FakeSession:
    def __init__(self) -> None:
        self.committed = 0

    def commit(self) -> None:
        self.committed += 1


class FakeAudit:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


def _make_integration(auth_header: str = SECRET_TOKEN) -> ApiIntegration:
    return ApiIntegration(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        name="demo-gmail",
        base_url="https://stub.example",
        auth_header_encrypted=encrypt_secret(auth_header),
        schema_=None,
    )


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# AC4/AC5/AC6 — call_integration hits {base_url}/{path} with header attached
# ---------------------------------------------------------------------------

def test_call_integration_hits_base_url_path_with_auth_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration = _make_integration()
    monkeypatch.setattr(
        ic, "get_integration", lambda session, *, agent_id, integration_id: integration
    )
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"ok": True})

    audit = FakeAudit()
    session = FakeSession()
    result = ic.call_integration(
        session,
        agent_id=integration.agent_id,
        integration_id=integration.id,
        path="messages/send",
        method="POST",
        body={"to": "x"},
        audit=audit,
        client=_mock_client(handler),
    )

    assert captured["url"] == "https://stub.example/messages/send"
    assert captured["auth"] == SECRET_TOKEN
    assert result["status_code"] == 200
    assert result["response"] == {"ok": True}
    assert session.committed == 1


def test_call_integration_emits_exactly_one_audit_entry_with_exact_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration = _make_integration()
    monkeypatch.setattr(
        ic, "get_integration", lambda session, *, agent_id, integration_id: integration
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    audit = FakeAudit()
    ic.call_integration(
        FakeSession(),
        agent_id=integration.agent_id,
        integration_id=integration.id,
        path="messages/send",
        method="POST",
        audit=audit,
        client=_mock_client(handler),
    )

    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry.type == "integration.called"
    assert entry.input == {
        "integration_id": str(integration.id),
        "path": "messages/send",
        "method": "POST",
    }
    assert entry.output == {"status_code": 200, "latency_ms": entry.latency_ms}


# ---------------------------------------------------------------------------
# T9.4 — MANDATORY NFR-9 no-leak test (AC7)
# ---------------------------------------------------------------------------

def test_auth_header_never_leaks_into_audit_or_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The header value must be absent from AuditEntry.input/output and logs."""
    integration = _make_integration()
    monkeypatch.setattr(
        ic, "get_integration", lambda session, *, agent_id, integration_id: integration
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    audit = FakeAudit()
    with caplog.at_level(logging.DEBUG):
        result = ic.call_integration(
            FakeSession(),
            agent_id=integration.agent_id,
            integration_id=integration.id,
            path="messages/send",
            method="POST",
            audit=audit,
            client=_mock_client(handler),
        )

    entry = audit.entries[0]
    assert SECRET_TOKEN not in str(entry.input)
    assert SECRET_TOKEN not in str(entry.output)
    assert SECRET_TOKEN not in str(result)
    assert SECRET_TOKEN not in caplog.text


def test_test_integration_never_returns_header(monkeypatch: pytest.MonkeyPatch) -> None:
    integration = _make_integration()
    monkeypatch.setattr(
        ic, "get_integration", lambda session, *, agent_id, integration_id: integration
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == SECRET_TOKEN
        return httpx.Response(200, json={"status": "ok"})

    result = ic.test_integration(
        FakeSession(),
        agent_id=integration.agent_id,
        integration_id=integration.id,
        client=_mock_client(handler),
    )

    assert result == {
        "status": "connected",
        "status_code": 200,
        "latency_ms": result["latency_ms"],
    }
    assert SECRET_TOKEN not in str(result)
    assert set(result.keys()) == {"status", "status_code", "latency_ms"}


def test_test_integration_disconnected_on_non_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    integration = _make_integration()
    monkeypatch.setattr(
        ic, "get_integration", lambda session, *, agent_id, integration_id: integration
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    result = ic.test_integration(
        FakeSession(),
        agent_id=integration.agent_id,
        integration_id=integration.id,
        client=_mock_client(handler),
    )
    assert result["status"] == "disconnected"
    assert result["status_code"] == 503


def test_test_integration_disconnected_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    integration = _make_integration()
    monkeypatch.setattr(
        ic, "get_integration", lambda session, *, agent_id, integration_id: integration
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    result = ic.test_integration(
        FakeSession(),
        agent_id=integration.agent_id,
        integration_id=integration.id,
        client=_mock_client(handler),
    )
    assert result == {
        "status": "disconnected",
        "status_code": 0,
        "latency_ms": result["latency_ms"],
    }
