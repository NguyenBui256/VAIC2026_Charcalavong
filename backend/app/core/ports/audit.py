"""Audit V2 port: Trace Session -> Execution Span -> immutable Event."""

from __future__ import annotations

import uuid
from contextlib import AbstractContextManager
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

AuditStatus = Literal[
    "pending",
    "running",
    "awaiting_human",
    "completed",
    "failed",
    "timed_out",
    "cancelled",
    "skipped",
]
PayloadClassification = Literal["internal", "confidential", "restricted"]


class ExecutionContext(BaseModel):
    tenant_id: uuid.UUID
    session_id: uuid.UUID
    run_id: uuid.UUID
    trace_id: uuid.UUID
    span_id: uuid.UUID | None = None
    parent_span_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    attempt_no: int = Field(default=1, ge=1)
    correlation_id: uuid.UUID


class SessionStart(BaseModel):
    context: ExecutionContext
    workflow_id: uuid.UUID | None = None
    workflow_version: str = ""
    parent_session_id: uuid.UUID | None = None
    trigger_type: Literal["manual", "schedule", "app_event", "follow_up", "system"] = "manual"
    trigger_id: uuid.UUID | None = None
    source_event_id: uuid.UUID | None = None
    initiator_user_id: uuid.UUID | None = None
    name: str = ""
    input: Any = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SpanStart(BaseModel):
    context: ExecutionContext
    node_type: str
    name: str
    actor_type: Literal["orchestrator", "agent", "tool", "user", "system"] = "system"
    logical_node_id: str = ""
    provider: str = ""
    model: str = ""
    tool_name: str = ""
    tool_version: str = ""
    kb_id: uuid.UUID | None = None
    kb_version: str = ""
    input: Any = None
    classification: PayloadClassification = "confidential"
    attributes: dict[str, Any] = Field(default_factory=dict)


class EventRecord(BaseModel):
    context: ExecutionContext
    event_type: str
    phase: Literal["instant", "start", "progress", "end"] = "instant"
    severity: Literal["debug", "info", "warning", "error", "critical"] = "info"
    status: AuditStatus | None = None
    occurred_at: datetime | None = None
    input: Any = None
    output: Any = None
    classification: PayloadClassification = "confidential"
    attributes: dict[str, Any] = Field(default_factory=dict)


class SpanEnd(BaseModel):
    context: ExecutionContext
    status: AuditStatus = "completed"
    output: Any = None
    error_code: str = ""
    error_message: str = ""
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: Decimal = Decimal("0")
    ttft_ms: int | None = Field(default=None, ge=0)
    classification: PayloadClassification = "confidential"
    attributes: dict[str, Any] = Field(default_factory=dict)


class SessionEnd(BaseModel):
    context: ExecutionContext
    status: AuditStatus = "completed"
    output: Any = None
    failure_summary: str = ""
    classification: PayloadClassification = "confidential"
    attributes: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class AuditPort(Protocol):
    """Only application-facing write contract for Audit V2."""

    def start_session(self, value: SessionStart) -> ExecutionContext: ...
    def start_span(self, value: SpanStart) -> ExecutionContext: ...
    def emit_event(self, value: EventRecord) -> uuid.UUID: ...
    def end_span(self, value: SpanEnd) -> None: ...
    def end_session(self, value: SessionEnd) -> None: ...
    def span(self, value: SpanStart) -> AbstractContextManager[ExecutionContext]: ...


__all__ = [
    "AuditPort",
    "AuditStatus",
    "EventRecord",
    "ExecutionContext",
    "PayloadClassification",
    "SessionEnd",
    "SessionStart",
    "SpanEnd",
    "SpanStart",
]
