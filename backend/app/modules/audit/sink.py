"""Transactional Audit V2 sink and projections."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.ids import uuid7
from app.core.ports.audit import (
    AuditPort,
    EventRecord,
    ExecutionContext,
    SessionEnd,
    SessionStart,
    SpanEnd,
    SpanStart,
)
from app.core.settings import get_settings
from app.core.tenant_context import set_tenant_session_var, tenant_context
from app.modules.audit.context import reset_execution_context, set_execution_context
from app.modules.audit.models import AuditEvent, AuditPayload, AuditSession, AuditSpan
from app.modules.audit.redaction import redact_payload
from app.modules.audit.taxonomy import SCHEMA_VERSION, validate_event_type

logger = logging.getLogger(__name__)

_DOMAIN_EVENT_START = {
    "orchestrator": "orchestrator.planning_started",
    "task": "task.claimed",
    "agent": "agent.started",
    "llm": "llm.started",
    "tool": "tool.requested",
    "kb": "kb.query_started",
    "escalation": "escalation.created",
    "mini_app": "mini_app.schema_emitted",
    "app_event": "app_event.emitted",
    "evaluation": "evaluation.started",
}
_DOMAIN_EVENT_END = {
    "orchestrator": ("orchestrator.aggregated", "orchestrator.decision_recorded"),
    "task": ("task.completed", "task.failed"),
    "agent": ("agent.completed", "agent.failed"),
    "llm": ("llm.completed", "llm.failed"),
    "tool": ("tool.completed", "tool.failed"),
    "kb": ("kb.cited", "kb.access_rejected"),
    "escalation": ("escalation.resolved", "escalation.timed_out"),
    "mini_app": ("mini_app.provisioned", "mini_app.failed"),
    "app_event": ("app_event.delivered", "app_event.gap_detected"),
    "evaluation": ("evaluation.completed", "evaluation.failed"),
}


class PostgresAuditSink(AuditPort):
    """Single writer for evidence plus Session/Span read projections."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    @contextmanager
    def _transaction(self, tenant_id: uuid.UUID) -> Iterator[Session]:
        active_tenant = tenant_context.get()
        if active_tenant != tenant_id:
            raise RuntimeError("Audit tenant does not match the active execution tenant")
        owns = self._session is None
        session = self._session or SessionLocal()
        try:
            role = get_settings().app_db_role or "vaic_app"
            session.execute(text(f"SET LOCAL ROLE {role}"))
            set_tenant_session_var(session, tenant_id)
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if owns:
                session.close()

    def start_session(self, value: SessionStart) -> ExecutionContext:
        ctx = value.context
        with self._transaction(ctx.tenant_id) as db:
            input_payload = self._store_payload(db, ctx, value.input, "confidential")
            db.add(
                AuditSession(
                    id=ctx.session_id,
                    tenant_id=ctx.tenant_id,
                    run_id=ctx.run_id,
                    department_id=ctx.department_id,
                    workflow_id=value.workflow_id,
                    workflow_version=value.workflow_version,
                    correlation_id=ctx.correlation_id,
                    parent_session_id=value.parent_session_id,
                    trace_id=ctx.trace_id,
                    name=value.name,
                    trigger_type=value.trigger_type,
                    trigger_id=value.trigger_id,
                    source_event_id=value.source_event_id,
                    initiator_user_id=value.initiator_user_id,
                    status="running",
                    input_payload_id=input_payload.id if input_payload else None,
                    started_at=datetime.now(UTC),
                    attributes=jsonable_encoder(value.attributes),
                )
            )
            db.flush()
            self._append_event(
                db,
                EventRecord(
                    context=ctx,
                    event_type="session.created",
                    phase="start",
                    status="running",
                    input=value.input,
                    attributes={"trigger_type": value.trigger_type, **value.attributes},
                ),
            )
        self._notify(ctx.session_id)
        return ctx

    def start_span(self, value: SpanStart) -> ExecutionContext:
        parent = value.context.span_id or value.context.parent_span_id
        span_ctx = value.context.model_copy(
            update={
                "parent_span_id": parent,
                "span_id": uuid7(),
            }
        )
        with self._transaction(span_ctx.tenant_id) as db:
            input_payload = self._store_payload(db, span_ctx, value.input, value.classification)
            db.add(
                AuditSpan(
                    id=span_ctx.span_id,
                    tenant_id=span_ctx.tenant_id,
                    session_id=span_ctx.session_id,
                    parent_span_id=span_ctx.parent_span_id,
                    logical_node_id=value.logical_node_id,
                    task_id=span_ctx.task_id,
                    agent_id=span_ctx.agent_id,
                    department_id=span_ctx.department_id,
                    actor_type=value.actor_type,
                    node_type=value.node_type,
                    name=value.name,
                    attempt_no=span_ctx.attempt_no,
                    status="running",
                    provider=value.provider,
                    model=value.model,
                    tool_name=value.tool_name,
                    tool_version=value.tool_version,
                    kb_id=value.kb_id,
                    kb_version=value.kb_version,
                    input_payload_id=input_payload.id if input_payload else None,
                    attributes=jsonable_encoder(value.attributes),
                )
            )
            session_row = db.execute(
                select(AuditSession).where(AuditSession.id == span_ctx.session_id).with_for_update()
            ).scalar_one()
            session_row.current_span_id = span_ctx.span_id
            domain = _domain(value.node_type)
            self._append_event(
                db,
                EventRecord(
                    context=span_ctx,
                    event_type=_DOMAIN_EVENT_START[domain],
                    phase="start",
                    status="running",
                    input=value.input,
                    attributes={
                        "name": value.name,
                        "node_type": value.node_type,
                        **value.attributes,
                    },
                ),
                locked_session=session_row,
            )
        self._notify(span_ctx.session_id)
        return span_ctx

    def emit_event(self, value: EventRecord) -> uuid.UUID:
        with self._transaction(value.context.tenant_id) as db:
            event = self._append_event(db, value)
        self._notify(value.context.session_id)
        return event.id

    def end_span(self, value: SpanEnd) -> None:
        ctx = value.context
        if ctx.span_id is None:
            raise ValueError("end_span requires context.span_id")
        now = datetime.now(UTC)
        with self._transaction(ctx.tenant_id) as db:
            span = db.execute(
                select(AuditSpan).where(AuditSpan.id == ctx.span_id).with_for_update()
            ).scalar_one()
            output_payload = self._store_payload(db, ctx, value.output, value.classification)
            span.status = value.status
            span.ended_at = now
            span.duration_ms = max(0, int((now - span.started_at).total_seconds() * 1000))
            span.ttft_ms = value.ttft_ms
            span.error_code = value.error_code
            span.error_message = value.error_message
            span.input_tokens = value.input_tokens
            span.output_tokens = value.output_tokens
            span.cached_tokens = value.cached_tokens
            span.reasoning_tokens = value.reasoning_tokens
            span.estimated_cost_usd = value.estimated_cost_usd
            span.output_payload_id = output_payload.id if output_payload else None
            span.attributes = {**(span.attributes or {}), **jsonable_encoder(value.attributes)}
            session_row = db.execute(
                select(AuditSession).where(AuditSession.id == ctx.session_id).with_for_update()
            ).scalar_one()
            self._aggregate_span(session_row, span)
            domain = _domain(span.node_type)
            candidate = _DOMAIN_EVENT_END[domain][0 if value.status == "completed" else 1]
            self._append_event(
                db,
                EventRecord(
                    context=ctx,
                    event_type=candidate,
                    phase="end",
                    status=value.status,
                    output=value.output,
                    severity="error" if value.status == "failed" else "info",
                    attributes={
                        "duration_ms": span.duration_ms,
                        "error_code": value.error_code,
                        "error_message": value.error_message,
                        "input_tokens": value.input_tokens,
                        "output_tokens": value.output_tokens,
                        "cached_tokens": value.cached_tokens,
                        "reasoning_tokens": value.reasoning_tokens,
                        "estimated_cost_usd": str(value.estimated_cost_usd),
                        **value.attributes,
                    },
                ),
                locked_session=session_row,
            )
        self._notify(ctx.session_id)

    def end_session(self, value: SessionEnd) -> None:
        ctx = value.context
        now = datetime.now(UTC)
        with self._transaction(ctx.tenant_id) as db:
            session_row = db.execute(
                select(AuditSession).where(AuditSession.id == ctx.session_id).with_for_update()
            ).scalar_one()
            payload = self._store_payload(db, ctx, value.output, value.classification)
            session_row.status = value.status
            session_row.ended_at = now
            session_row.current_span_id = None
            session_row.result_payload_id = payload.id if payload else None
            session_row.failure_summary = value.failure_summary
            session_row.attributes = {
                **(session_row.attributes or {}),
                **jsonable_encoder(value.attributes),
            }
            suffix = (
                value.status
                if value.status in {"completed", "failed", "timed_out", "cancelled"}
                else "failed"
            )
            self._append_event(
                db,
                EventRecord(
                    context=ctx,
                    event_type=f"session.{suffix}",
                    phase="end",
                    status=value.status,
                    output=value.output,
                    severity="error" if value.status == "failed" else "info",
                    attributes={"failure_summary": value.failure_summary, **value.attributes},
                ),
                locked_session=session_row,
            )
        self._notify(ctx.session_id)

    @contextmanager
    def span(self, value: SpanStart) -> Iterator[ExecutionContext]:
        ctx = self.start_span(value)
        token = set_execution_context(ctx)
        try:
            yield ctx
        except Exception as exc:
            self.end_span(
                SpanEnd(
                    context=ctx,
                    status="failed",
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            raise
        else:
            self.end_span(SpanEnd(context=ctx))
        finally:
            reset_execution_context(token)

    def _store_payload(
        self,
        db: Session,
        ctx: ExecutionContext,
        value: Any,
        classification: str,
    ) -> AuditPayload | None:
        if value is None:
            return None
        cleaned = redact_payload(jsonable_encoder(value))
        canonical = _canonical(cleaned.value)
        payload = AuditPayload(
            id=uuid7(),
            tenant_id=ctx.tenant_id,
            department_id=ctx.department_id,
            classification=classification,
            data=cleaned.value,
            byte_size=len(canonical),
            sha256=hashlib.sha256(canonical).hexdigest(),
            redaction_count=cleaned.count,
            redaction_paths=list(cleaned.paths),
        )
        db.add(payload)
        db.flush()
        return payload

    def _append_event(
        self,
        db: Session,
        value: EventRecord,
        *,
        locked_session: AuditSession | None = None,
    ) -> AuditEvent:
        validate_event_type(value.event_type)
        row = (
            locked_session
            or db.execute(
                select(AuditSession)
                .where(AuditSession.id == value.context.session_id)
                .with_for_update()
            ).scalar_one()
        )
        input_payload = self._store_payload(db, value.context, value.input, value.classification)
        output_payload = self._store_payload(db, value.context, value.output, value.classification)
        sequence = row.last_sequence + 1
        event_id = uuid7()
        occurred = value.occurred_at or datetime.now(UTC)
        evidence = {
            "event_id": str(event_id),
            "session_id": str(value.context.session_id),
            "span_id": str(value.context.span_id or ""),
            "sequence_no": sequence,
            "occurred_at": occurred.isoformat(),
            "event_type": value.event_type,
            "status": value.status,
            "input_digest": input_payload.sha256 if input_payload else "",
            "output_digest": output_payload.sha256 if output_payload else "",
            "attributes": jsonable_encoder(value.attributes),
            "prev_hash": row.last_hash,
        }
        event_hash = hashlib.sha256(_canonical(evidence)).hexdigest()
        event = AuditEvent(
            id=event_id,
            tenant_id=value.context.tenant_id,
            session_id=value.context.session_id,
            span_id=value.context.span_id,
            parent_span_id=value.context.parent_span_id,
            sequence_no=sequence,
            occurred_at=occurred,
            event_type=value.event_type,
            phase=value.phase,
            severity=value.severity,
            actor_type="agent" if value.context.agent_id else "system",
            actor_id=value.context.agent_id,
            status=value.status,
            input_payload_id=input_payload.id if input_payload else None,
            output_payload_id=output_payload.id if output_payload else None,
            attributes=jsonable_encoder(value.attributes),
            schema_version=SCHEMA_VERSION,
            prev_hash=row.last_hash,
            event_hash=event_hash,
        )
        db.add(event)
        row.last_sequence = sequence
        row.last_hash = event_hash
        row.redaction_count += sum(
            payload.redaction_count for payload in (input_payload, output_payload) if payload
        )
        db.flush()
        return event

    @staticmethod
    def _aggregate_span(session: AuditSession, span: AuditSpan) -> None:
        session.input_tokens += span.input_tokens
        session.output_tokens += span.output_tokens
        session.cached_tokens += span.cached_tokens
        session.reasoning_tokens += span.reasoning_tokens
        session.estimated_cost_usd = Decimal(session.estimated_cost_usd or 0) + Decimal(
            span.estimated_cost_usd or 0
        )
        session.critical_path_ms = max(session.critical_path_ms, span.duration_ms or 0)
        if span.node_type == "llm":
            session.llm_call_count += 1
        elif span.node_type == "tool":
            session.tool_call_count += 1
        elif span.node_type == "kb":
            session.rag_call_count += 1
        elif span.node_type == "agent":
            session.agent_count += 1
        elif span.node_type == "escalation":
            session.escalation_count += 1
        if span.attempt_no > 1:
            session.retry_count += 1

    @staticmethod
    def _notify(session_id: uuid.UUID) -> None:
        try:
            import redis

            client = redis.Redis.from_url(get_settings().redis_url)
            client.publish(f"audit:{session_id}", "updated")
            client.close()
        except Exception:
            logger.debug("Audit SSE notification unavailable", exc_info=True)


def _domain(node_type: str) -> str:
    domain = node_type.split(".", 1)[0]
    if domain not in _DOMAIN_EVENT_START:
        raise ValueError(f"Unsupported audit node type: {node_type}")
    return domain


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


__all__ = ["PostgresAuditSink"]
