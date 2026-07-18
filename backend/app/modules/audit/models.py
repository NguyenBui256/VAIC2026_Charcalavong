"""SQLAlchemy models for Audit V2."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class AuditSession(Base):
    __tablename__ = "audit_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    workflow_version: Mapped[str] = mapped_column(String(128), default="")
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_sessions.id")
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    trigger_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    initiator_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    current_span_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    input_payload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    result_payload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    failure_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    llm_call_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)
    rag_call_count: Mapped[int] = mapped_column(Integer, default=0)
    agent_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    escalation_count: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cached_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=0)
    human_wait_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    critical_path_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    last_sequence: Mapped[int] = mapped_column(BigInteger, default=0)
    last_hash: Mapped[str] = mapped_column(String(64), default="")
    schema_version: Mapped[int] = mapped_column(Integer, default=2)
    completeness_status: Mapped[str] = mapped_column(String(32), default="complete")
    redaction_count: Mapped[int] = mapped_column(Integer, default=0)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (UniqueConstraint("tenant_id", "run_id", name="uq_audit_session_run"),)


class AuditSpan(Base):
    __tablename__ = "audit_spans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_sessions.id"), nullable=False
    )
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    logical_node_id: Mapped[str] = mapped_column(String(255), default="")
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_type: Mapped[str] = mapped_column(String(32), default="system")
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="running")
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    ttft_ms: Mapped[int | None] = mapped_column(BigInteger)
    provider: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(255), default="")
    tool_name: Mapped[str] = mapped_column(String(255), default="")
    tool_version: Mapped[str] = mapped_column(String(128), default="")
    kb_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kb_version: Mapped[str] = mapped_column(String(128), default="")
    error_code: Mapped[str] = mapped_column(String(128), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cached_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=0)
    input_payload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    output_payload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class AuditPayload(Base):
    __tablename__ = "audit_payloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    content_type: Mapped[str] = mapped_column(String(128), default="application/json")
    classification: Mapped[str] = mapped_column(String(32), default="confidential")
    data: Mapped[Any] = mapped_column(JSONB, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    redaction_count: Mapped[int] = mapped_column(Integer, default=0)
    redaction_paths: Mapped[list[str]] = mapped_column(JSONB, default=list)
    policy_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_sessions.id"), nullable=False
    )
    span_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    sequence_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    event_type: Mapped[str] = mapped_column(String(96), nullable=False)
    phase: Mapped[str] = mapped_column(String(16), default="instant")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    actor_type: Mapped[str] = mapped_column(String(32), default="system")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str | None] = mapped_column(String(32))
    input_payload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_payloads.id")
    )
    output_payload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_payloads.id")
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, default=2)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "sequence_no", name="uq_audit_event_sequence"),
    )


class AuditEvaluation(Base):
    __tablename__ = "audit_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_sessions.id"), nullable=False
    )
    evaluator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(128), default="")
    evaluator_type: Mapped[str] = mapped_column(String(32), default="rule")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 5))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    evidence_span_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(255), default="")
    overall_pass: Mapped[bool | None] = mapped_column(Boolean)
    summary: Mapped[str] = mapped_column(Text, default="")
    assessment: Mapped[str] = mapped_column(Text, default="")
    insights: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    strengths: Mapped[list[str]] = mapped_column(JSONB, default=list)
    context_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    latency_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvaluationCriterion(Base):
    __tablename__ = "audit_evaluation_criteria"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditEvaluationJob(Base):
    __tablename__ = "audit_evaluation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_sessions.id"), nullable=False
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requester_role: Mapped[str] = mapped_column(String(64), nullable=False)
    requester_department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    criteria_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    phase: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    error_code: Mapped[str] = mapped_column(String(128), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    evaluation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    boundary_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    boundary_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantAuditKey(Base):
    __tablename__ = "tenant_audit_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    algorithm: Mapped[str] = mapped_column(String(32), default="Ed25519")
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_private_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("tenant_id", "version", name="uq_tenant_audit_key_version"),)
