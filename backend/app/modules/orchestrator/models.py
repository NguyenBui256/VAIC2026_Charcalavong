"""Orchestrator SQLAlchemy models.

Story 3.1: the `workflows` table — Workflow definition CRUD only (name,
description, constraints, owner, pre-provisioned confidence/escalation
config). `workflow_runs`/`tasks` (Run lifecycle) arrive in Story 3.2 — do
NOT add Run/Task columns here (Dev Notes "Scope Boundaries", YAGNI).

RLS policy (mirrors `agents`/`tools`, applied by the accompanying migration):
    tenant_id = current_setting('app.tenant_id')::uuid  (ENABLE + FORCE)

No soft-delete: Workflows have no DELETE AC in Story 3.1.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7

# Enum values (exact, AC7) — CHECK constraints rather than Postgres ENUM
# types (mirrors `agents.status`'s String pattern) so future value
# additions (e.g. Story 3.6's `awaiting_human` consumers) never need an
# `ALTER TYPE` dance.
RUN_STATUSES = ("pending", "running", "awaiting_human", "completed", "failed", "timed_out")
TASK_STATUSES = ("pending", "claimed", "completed", "failed")


class Workflow(Base):
    """A Workflow definition — natural-language description + constraints.

    `description` is an opaque run-time hint passed to the Orchestrator at
    Run time; Story 3.1 never decomposes it (AC2). `confidence_threshold`
    and `escalation_timeout_seconds` are pre-provisioned here (cheap now)
    to avoid a follow-up migration for Story 3.5/3.6.
    """

    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    confidence_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.7, server_default="0.7"
    )
    escalation_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300, server_default="300"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkflowRun(Base):
    """A single execution of a Workflow (Story 3.2).

    `status` transitions ONLY via `orchestrator.state.transition_run_status`
    (AD-6, compare-and-set) — never a bare ORM `.status = ...` assignment
    followed by `commit()` (that would be a SELECT-then-UPDATE race).

    Story 3.2 only proves the state-machine skeleton: `pending -> running
    -> completed` (no-op). Decomposition (3.3), dispatch (3.4), escalation
    (3.6) populate `result` / drive `awaiting_human` in later stories.
    """

    __tablename__ = "workflow_runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN {RUN_STATUSES!r}", name="ck_workflow_runs_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    input: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Task(Base):
    """A unit of work dispatched to a Specialist Agent within a Run.

    Schema finalized in Story 3.2 (per Dev Notes — avoids a follow-up
    migration for Story 3.4); no Task rows are created/claimed here.
    `target_agent_id` is a DB-level FK into Epic-2's `agents` table — AD-1
    only forbids importing internal Python models cross-module, not FK
    references (Dev Notes).
    """

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            f"status IN {TASK_STATUSES!r}", name="ck_tasks_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    schema_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
