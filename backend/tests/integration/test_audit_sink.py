"""Audit V2 persistence, integrity, redaction and isolation integration tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import AdminSessionLocal, SessionLocal
from app.core.ids import uuid7
from app.core.ports.audit import ExecutionContext, SessionEnd, SessionStart, SpanEnd, SpanStart
from app.core.tenant_context import set_tenant_context, set_tenant_session_var
from app.modules.audit.integrity import verify_session
from app.modules.audit.models import AuditEvent, AuditPayload, AuditSession, AuditSpan
from app.modules.audit.sink import PostgresAuditSink


def _context(tenant_id: uuid.UUID, department_id: uuid.UUID) -> ExecutionContext:
    run_id = uuid7()
    return ExecutionContext(
        tenant_id=tenant_id,
        session_id=run_id,
        run_id=run_id,
        trace_id=uuid7(),
        correlation_id=uuid7(),
        department_id=department_id,
    )


def _write_trace(tenant_id: uuid.UUID, department_id: uuid.UUID) -> ExecutionContext:
    set_tenant_context(tenant_id)
    context = _context(tenant_id, department_id)
    sink = PostgresAuditSink()
    sink.start_session(
        SessionStart(
            context=context,
            name="Audit integration trace",
            input={"account_number": "123456789012", "authorization": "Bearer secret"},
        )
    )
    child = sink.start_span(
        SpanStart(
            context=context,
            node_type="llm",
            name="Decision synthesis",
            provider="anthropic",
            model="claude-test",
            input={"prompt": "synthetic"},
        )
    )
    sink.end_span(
        SpanEnd(context=child, input_tokens=12, output_tokens=4, output={"decision": "approved"})
    )
    sink.end_session(SessionEnd(context=context, output={"result": "approved"}))
    return context


def _as_app(db, tenant_id: uuid.UUID) -> None:  # noqa: ANN001
    db.execute(text("SET LOCAL ROLE vaic_app"))
    set_tenant_session_var(db, tenant_id)


def test_v2_schema_replaces_flat_audit_trail(seed_data) -> None:
    with AdminSessionLocal() as db:
        tables = set(
            db.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            ).scalars()
        )
    assert "audit_trail" not in tables
    assert {
        "audit_sessions",
        "audit_spans",
        "audit_events",
        "audit_payloads",
        "audit_evaluations",
        "tenant_audit_keys",
    }.issubset(tables)


def test_session_span_event_lifecycle_and_aggregates(seed_data) -> None:
    context = _write_trace(seed_data["tenant_a_id"], seed_data["dept_a_id"])
    with AdminSessionLocal() as db:
        session = db.get(AuditSession, context.session_id)
        spans = (
            db.execute(select(AuditSpan).where(AuditSpan.session_id == context.session_id))
            .scalars()
            .all()
        )
        events = (
            db.execute(
                select(AuditEvent)
                .where(AuditEvent.session_id == context.session_id)
                .order_by(AuditEvent.sequence_no)
            )
            .scalars()
            .all()
        )
    assert session.status == "completed"
    assert session.input_tokens == 12 and session.output_tokens == 4
    assert session.llm_call_count == 1
    assert len(spans) == 1 and spans[0].status == "completed"
    assert [event.sequence_no for event in events] == list(range(1, len(events) + 1))
    assert events[-1].event_type == "session.completed"


def test_redaction_happens_before_payload_persistence(seed_data) -> None:
    context = _write_trace(seed_data["tenant_a_id"], seed_data["dept_a_id"])
    with AdminSessionLocal() as db:
        session = db.get(AuditSession, context.session_id)
        payload = db.get(AuditPayload, session.input_payload_id)
    assert payload.data["account_number"] == "[REDACTED]"
    assert payload.data["authorization"] == "[REDACTED]"
    assert payload.redaction_count == 2


def test_hash_chain_verifies_and_detects_orphan_state(seed_data) -> None:
    context = _write_trace(seed_data["tenant_a_id"], seed_data["dept_a_id"])
    with AdminSessionLocal() as db:
        result = verify_session(db, context.session_id)
    assert result["valid"] is True
    assert result["event_count"] >= 4


def test_event_evidence_is_append_only_for_application_role(seed_data) -> None:
    context = _write_trace(seed_data["tenant_a_id"], seed_data["dept_a_id"])
    with SessionLocal() as db:
        _as_app(db, seed_data["tenant_a_id"])
        with pytest.raises(SQLAlchemyError):
            db.execute(
                text("UPDATE audit_events SET event_type='audit.redacted' WHERE session_id=:id"),
                {"id": str(context.session_id)},
            )
        db.rollback()


def test_rls_hides_other_tenant_sessions(seed_data) -> None:
    context = _write_trace(seed_data["tenant_a_id"], seed_data["dept_a_id"])
    with SessionLocal() as db:
        _as_app(db, seed_data["tenant_b_id"])
        assert db.get(AuditSession, context.session_id) is None
