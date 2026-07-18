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

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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

# Graph workflow (Sub-project 3A). Per-node runtime status; defined in full
# now so 3B/3C/3E populate values without an ALTER. Mirrors the CHECK-not-ENUM
# convention used by RUN_STATUSES / TASK_STATUSES above.
NODE_EXECUTION_STATUSES = (
    "pending",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
    "rejected",
    "skipped",
    "rolled_back",
)


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
    # Sub-project 3A: immutable copy of the workflow graph (nodes+edges+
    # approvers) taken at run creation. NULL for legacy flat runs (no graph).
    graph_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
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


class WorkflowNode(Base):
    """A node in a Workflow graph — one bound Specialist Agent (3A)."""

    __tablename__ = "workflow_nodes"
    __table_args__ = (
        UniqueConstraint("workflow_id", "node_key", name="uq_workflow_nodes_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    position_x: Mapped[float] = mapped_column(
        Float, nullable=False, default=0, server_default="0"
    )
    position_y: Mapped[float] = mapped_column(
        Float, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkflowEdge(Base):
    """A directed dependency edge (parent -> child) in a Workflow graph (3A).

    No field-mapping column: data flow is whole-output merge (a child's input
    is the merge of every parent's output, keyed by parent `node_key`).
    """

    __tablename__ = "workflow_edges"
    __table_args__ = (
        UniqueConstraint("from_node_id", "to_node_id", name="uq_workflow_edges_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    from_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkflowNodeApprover(Base):
    """M2M: a graph node assigned to a human approver (3A).

    Zero rows for a node => auto (non-gated). >=1 row => human-gated; the
    first approver's decision resolves the node (first-wins, enforced in 3C).
    """

    __tablename__ = "workflow_node_approvers"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RunNodeExecution(Base):
    """Mutable per-node runtime state within a Run (3A).

    One row per graph node per run, created at run creation with
    `status='pending'`. `input`/`output`/`decision*` are populated by the
    execution engine (3B) and review flow (3C); 3A only defines the shape.
    """

    __tablename__ = "run_node_executions"
    __table_args__ = (
        CheckConstraint(
            f"status IN {NODE_EXECUTION_STATUSES!r}",
            name="ck_run_node_executions_status",
        ),
        UniqueConstraint("run_id", "node_key", name="uq_run_node_executions_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    approver_user_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
