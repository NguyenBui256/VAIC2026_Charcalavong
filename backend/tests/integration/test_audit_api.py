"""Audit V2 read API, RBAC, graph and signed export tests."""

from __future__ import annotations

import base64

from app.core.auth import create_access_token
from app.core.ids import uuid7
from app.core.ports.audit import ExecutionContext, SessionEnd, SessionStart, SpanEnd, SpanStart
from app.core.tenant_context import set_tenant_context
from app.modules.audit.signing import verify_document
from app.modules.audit.sink import PostgresAuditSink


def _headers(seed_data, tenant: str = "a", role: str = "manager") -> dict[str, str]:
    token = create_access_token(
        {
            "user_id": str(seed_data[f"user_{tenant}_id"]),
            "tenant_id": str(seed_data[f"tenant_{tenant}_id"]),
            "department_id": str(seed_data[f"dept_{tenant}_id"]),
            "role": role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _trace(seed_data) -> ExecutionContext:
    set_tenant_context(seed_data["tenant_a_id"])
    run_id = uuid7()
    context = ExecutionContext(
        tenant_id=seed_data["tenant_a_id"],
        department_id=seed_data["dept_a_id"],
        session_id=run_id,
        run_id=run_id,
        trace_id=uuid7(),
        correlation_id=uuid7(),
    )
    sink = PostgresAuditSink()
    sink.start_session(
        SessionStart(
            context=context,
            name="API trace",
            initiator_user_id=seed_data["user_a_id"],
        )
    )
    span = sink.start_span(
        SpanStart(
            context=context,
            node_type="tool",
            name="Policy calculator",
            actor_type="tool",
            tool_name="calculator",
            input={"password": "secret"},
        )
    )
    sink.end_span(SpanEnd(context=span, output={"value": 42}))
    sink.end_session(SessionEnd(context=context, output={"decision": "pass"}))
    return context


def test_manager_can_read_session_graph_and_events(api_client, seed_data) -> None:
    context = _trace(seed_data)
    headers = _headers(seed_data)
    detail = api_client.get(f"/audit/sessions/{context.session_id}", headers=headers)
    graph = api_client.get(f"/audit/sessions/{context.session_id}/graph", headers=headers)
    events = api_client.get(f"/audit/sessions/{context.session_id}/events", headers=headers)
    assert detail.status_code == graph.status_code == events.status_code == 200
    assert detail.json()["data"]["integrity"]["valid"] is True
    assert len(graph.json()["data"]["nodes"]) == 1
    assert events.json()["data"][-1]["event_type"] == "session.completed"


def test_cross_tenant_session_is_not_disclosed(api_client, seed_data) -> None:
    context = _trace(seed_data)
    response = api_client.get(
        f"/audit/sessions/{context.session_id}", headers=_headers(seed_data, tenant="b")
    )
    assert response.status_code == 404


def test_signed_export_and_public_key(api_client, seed_data) -> None:
    context = _trace(seed_data)
    headers = _headers(seed_data)
    response = api_client.get(f"/audit/sessions/{context.session_id}/export", headers=headers)
    assert response.status_code == 200
    exported = response.json()["data"]
    assert exported["signature"]["algorithm"] == "Ed25519"
    assert exported["document"]["integrity"]["valid"] is True
    key = api_client.get(f"/audit/keys/{exported['signature']['key_id']}/public", headers=headers)
    assert key.status_code == 200
    assert key.json()["data"]["fingerprint"] == exported["signature"]["key_fingerprint"]
    verify_document(
        base64.b64decode(key.json()["data"]["public_key"]),
        exported["document"],
        exported["signature"]["signature"],
    )
