# Graph Workflow Data Model (3A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the persistence layer for builder-authored DAG workflows — definition tables (nodes/edges/approvers), per-run runtime state (`run_node_executions` + `graph_snapshot`), snapshot-on-run-create, and graph validation helpers.

**Architecture:** New SQLAlchemy models in `app/modules/orchestrator/models.py`, one Alembic migration mirroring the existing RLS pattern, pure-function graph validation + topology helpers in a focused module, and a snapshot builder wired into `create_run`. Data model only — no execution engine, no APIs, no UI.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 (sync, `Mapped`/`mapped_column`), Alembic, PostgreSQL 18 (JSONB, RLS), pydantic-settings.

## Global Constraints

- All tenant-scoped tables use RLS: `ENABLE` + `FORCE` + `tenant_isolation_policy` (`tenant_id = current_setting('app.tenant_id')::uuid`, USING + WITH CHECK) + `GRANT SELECT, INSERT, UPDATE` to role `vaic_app`. No DELETE grant (no delete AC).
- All ids are UUIDv7, generated app-side via `app.core.ids.uuid7` (PK has no DB default; app supplies it).
- Status columns use `String(32)` + a `CheckConstraint`, never a Postgres ENUM type (repo convention, `orchestrator/models.py`).
- Every FK declares an explicit `ondelete`. Timestamps are `TIMESTAMP(timezone=True)`; `created_at`/`updated_at` default `server_default=sa.text("now()")`.
- Domain services read `tenant_context.get()` — NEVER accept `tenant_id` as an argument (consistency convention).
- New Alembic migration `down_revision = "b2c3d4e5f6a7"` (current head).
- Per user preference: NO pytest test files are committed. Each task ends with a manual verification command + a commit of source only.
- Files > 200 LOC should be modularized; use kebab-case long descriptive names for new modules.

---

### Task 1: Graph definition + runtime models

**Files:**
- Modify: `backend/app/modules/orchestrator/models.py` (add import `UniqueConstraint`; add `NODE_EXECUTION_STATUSES`; add 4 model classes; add `graph_snapshot` column to `WorkflowRun`)

**Interfaces:**
- Produces: `WorkflowNode`, `WorkflowEdge`, `WorkflowNodeApprover`, `RunNodeExecution` ORM classes; `NODE_EXECUTION_STATUSES` tuple; `WorkflowRun.graph_snapshot` mapped column.

- [ ] **Step 1: Add `UniqueConstraint` to the sqlalchemy import**

In `backend/app/modules/orchestrator/models.py`, change the import line:

```python
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
```

- [ ] **Step 2: Add the node-execution status tuple**

Below the existing `TASK_STATUSES = (...)` line, add:

```python
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
```

- [ ] **Step 3: Add `graph_snapshot` column to `WorkflowRun`**

In class `WorkflowRun`, after the `result` column, add:

```python
    # Sub-project 3A: immutable copy of the workflow graph (nodes+edges+
    # approvers) taken at run creation. NULL for legacy flat runs (no graph).
    graph_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 4: Append the four new model classes**

At the end of `backend/app/modules/orchestrator/models.py`, add:

```python
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
```

- [ ] **Step 5: Verify the models import and mappers configure**

Run:

```bash
cd backend && .venv/Scripts/python.exe -c "from sqlalchemy.orm import configure_mappers; import app.modules.orchestrator.models as m; configure_mappers(); print(m.WorkflowNode.__tablename__, m.WorkflowEdge.__tablename__, m.WorkflowNodeApprover.__tablename__, m.RunNodeExecution.__tablename__, len(m.NODE_EXECUTION_STATUSES))"
```

Expected: `workflow_nodes workflow_edges workflow_node_approvers run_node_executions 8` with no mapper errors.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/orchestrator/models.py
git commit -m "feat(orchestrator): graph workflow ORM models (3A)"
```

---

### Task 2: Alembic migration for the graph tables

**Files:**
- Create: `backend/alembic/versions/c3d4e5f6a7b8_create_graph_workflow_tables.py`

**Interfaces:**
- Consumes: model shapes from Task 1 (table/column names must match exactly).
- Produces: DB tables `workflow_nodes`, `workflow_edges`, `workflow_node_approvers`, `run_node_executions`; column `workflow_runs.graph_snapshot`.

- [ ] **Step 1: Create the migration file**

Create `backend/alembic/versions/c3d4e5f6a7b8_create_graph_workflow_tables.py`:

```python
"""create graph workflow tables (3A)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-18 09:00:00.000000

Sub-project 3A: builder-authored DAG workflow data model. Definition tables
(workflow_nodes / workflow_edges / workflow_node_approvers) + per-run runtime
state (run_node_executions) + a graph_snapshot column on workflow_runs.
Mirrors the RLS + grant DDL pattern of 39dfa51cec0c (workflow_runs/tasks).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"

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


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy
            ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
        """
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO {APP_ROLE};")


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def upgrade() -> None:
    op.add_column(
        "workflow_runs",
        sa.Column("graph_snapshot", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "workflow_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("position_x", sa.Float(), nullable=False, server_default="0"),
        sa.Column("position_y", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("workflow_id", "node_key", name="uq_workflow_nodes_key"),
    )
    op.create_index("ix_workflow_nodes_tenant_id", "workflow_nodes", ["tenant_id"])
    op.create_index("ix_workflow_nodes_workflow_id", "workflow_nodes", ["workflow_id"])

    op.create_table(
        "workflow_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "from_node_id", "to_node_id", name="uq_workflow_edges_pair"
        ),
    )
    op.create_index("ix_workflow_edges_tenant_id", "workflow_edges", ["tenant_id"])
    op.create_index("ix_workflow_edges_workflow_id", "workflow_edges", ["workflow_id"])

    op.create_table(
        "workflow_node_approvers",
        sa.Column(
            "node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_workflow_node_approvers_tenant_id",
        "workflow_node_approvers",
        ["tenant_id"],
    )
    op.create_index(
        "ix_workflow_node_approvers_user_id", "workflow_node_approvers", ["user_id"]
    )

    op.create_table(
        "run_node_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_key", sa.String(64), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="pending"
        ),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column(
            "approver_user_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"status IN {NODE_EXECUTION_STATUSES!r}",
            name="ck_run_node_executions_status",
        ),
        sa.UniqueConstraint("run_id", "node_key", name="uq_run_node_executions_key"),
    )
    op.create_index(
        "ix_run_node_executions_tenant_id", "run_node_executions", ["tenant_id"]
    )
    op.create_index(
        "ix_run_node_executions_run_id", "run_node_executions", ["run_id"]
    )
    op.create_index(
        "ix_run_node_executions_status", "run_node_executions", ["status"]
    )

    _enable_rls("workflow_nodes")
    _enable_rls("workflow_edges")
    _enable_rls("workflow_node_approvers")
    _enable_rls("run_node_executions")


def downgrade() -> None:
    _disable_rls("run_node_executions")
    _disable_rls("workflow_node_approvers")
    _disable_rls("workflow_edges")
    _disable_rls("workflow_nodes")
    op.drop_table("run_node_executions")
    op.drop_table("workflow_node_approvers")
    op.drop_table("workflow_edges")
    op.drop_table("workflow_nodes")
    op.drop_column("workflow_runs", "graph_snapshot")
```

- [ ] **Step 2: Verify migration is the single head**

Run:

```bash
cd backend && .venv/Scripts/python.exe -m alembic heads
```

Expected: exactly one head, `c3d4e5f6a7b8 (head)`.

- [ ] **Step 3: Apply the migration (round-trip)**

Ensure infra is up (`docker compose --env-file infra/.env -f infra/docker-compose.yml up -d`), then run:

```bash
cd backend && .venv/Scripts/python.exe -m alembic upgrade head && .venv/Scripts/python.exe -m alembic downgrade -1 && .venv/Scripts/python.exe -m alembic upgrade head
```

Expected: all three commands succeed with no error (up → down drops cleanly → up recreates).

- [ ] **Step 4: Introspect the new schema**

Run:

```bash
cd backend && .venv/Scripts/python.exe -c "from sqlalchemy import create_engine, inspect; from app.core.settings import get_settings; i=inspect(create_engine(get_settings().database_admin_url)); print(sorted(c['name'] for c in i.get_columns('run_node_executions'))); print('graph_snapshot' in {c['name'] for c in i.get_columns('workflow_runs')})"
```

Expected: prints the full `run_node_executions` column list and `True` for `graph_snapshot`.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/c3d4e5f6a7b8_create_graph_workflow_tables.py
git commit -m "feat(orchestrator): migration for graph workflow tables (3A)"
```

---

### Task 3: Graph validation + topology helpers

**Files:**
- Create: `backend/app/modules/orchestrator/graph_validation.py`

**Interfaces:**
- Produces:
  - `class GraphValidationError(ValueError)`
  - `assert_valid_graph(node_keys: list[str], edges: list[tuple[str, str]]) -> None`
  - `root_keys(node_keys: list[str], edges: list[tuple[str, str]]) -> list[str]`
  - `parents_by_key(node_keys: list[str], edges: list[tuple[str, str]]) -> dict[str, list[str]]`
  - `topological_order(node_keys: list[str], edges: list[tuple[str, str]]) -> list[str]`

- [ ] **Step 1: Create the module**

Create `backend/app/modules/orchestrator/graph_validation.py`:

```python
"""Pure graph validation + topology helpers for the DAG workflow model (3A).

No DB / ORM here -- these operate on plain `node_key` strings and
`(from_key, to_key)` edge tuples so 3D authoring, seed scripts, and the 3B
engine all reuse them. `assert_valid_graph` is the single gate every
graph-definition write must pass.
"""

from __future__ import annotations

from collections import deque

__all__ = [
    "GraphValidationError",
    "assert_valid_graph",
    "root_keys",
    "parents_by_key",
    "topological_order",
]


class GraphValidationError(ValueError):
    """Raised when a node/edge set is not a valid DAG."""


def assert_valid_graph(node_keys: list[str], edges: list[tuple[str, str]]) -> None:
    """Raise `GraphValidationError` on a malformed graph.

    Rejects: duplicate node keys, edges referencing an unknown key, a
    self-loop, a duplicate edge, or any cycle (the edge set must be a DAG).
    """
    seen: set[str] = set()
    for key in node_keys:
        if key in seen:
            raise GraphValidationError(f"duplicate node_key: {key!r}")
        seen.add(key)

    edge_seen: set[tuple[str, str]] = set()
    for src, dst in edges:
        if src not in seen:
            raise GraphValidationError(f"edge references unknown from-node: {src!r}")
        if dst not in seen:
            raise GraphValidationError(f"edge references unknown to-node: {dst!r}")
        if src == dst:
            raise GraphValidationError(f"self-loop on node: {src!r}")
        if (src, dst) in edge_seen:
            raise GraphValidationError(f"duplicate edge: {src!r} -> {dst!r}")
        edge_seen.add((src, dst))

    # Kahn's algorithm: if the topological pass cannot consume every node,
    # a cycle exists.
    indegree = {k: 0 for k in node_keys}
    adjacency: dict[str, list[str]] = {k: [] for k in node_keys}
    for src, dst in edges:
        indegree[dst] += 1
        adjacency[src].append(dst)
    queue = deque(k for k in node_keys if indegree[k] == 0)
    consumed = 0
    while queue:
        node = queue.popleft()
        consumed += 1
        for child in adjacency[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if consumed != len(node_keys):
        raise GraphValidationError("graph contains a cycle")


def parents_by_key(
    node_keys: list[str], edges: list[tuple[str, str]]
) -> dict[str, list[str]]:
    """Map each node key to its parent keys (order = edge declaration order)."""
    parents: dict[str, list[str]] = {k: [] for k in node_keys}
    for src, dst in edges:
        if dst in parents:
            parents[dst].append(src)
    return parents


def root_keys(node_keys: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Node keys with no incoming edge -- they receive the run input directly."""
    has_parent = {dst for _, dst in edges}
    return [k for k in node_keys if k not in has_parent]


def topological_order(
    node_keys: list[str], edges: list[tuple[str, str]]
) -> list[str]:
    """Return node keys in a valid execution order. Assumes a valid DAG
    (call `assert_valid_graph` first)."""
    indegree = {k: 0 for k in node_keys}
    adjacency: dict[str, list[str]] = {k: [] for k in node_keys}
    for src, dst in edges:
        indegree[dst] += 1
        adjacency[src].append(dst)
    queue = deque(k for k in node_keys if indegree[k] == 0)
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for child in adjacency[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return order
```

- [ ] **Step 2: Verify the helpers (valid + cyclic + roots)**

Run:

```bash
cd backend && .venv/Scripts/python.exe -c "
from app.modules.orchestrator.graph_validation import assert_valid_graph, root_keys, parents_by_key, topological_order, GraphValidationError
nk=['A','B','C']; ok=[('A','B'),('A','C')]
assert_valid_graph(nk, ok)
assert root_keys(nk, ok)==['A'], root_keys(nk, ok)
assert parents_by_key(nk, ok)=={'A':[],'B':['A'],'C':['A']}
assert topological_order(nk, ok)[0]=='A'
try:
    assert_valid_graph(nk, [('A','B'),('B','C'),('C','A')]); raise SystemExit('cycle not caught')
except GraphValidationError as e:
    print('cycle rejected:', e)
try:
    assert_valid_graph(nk, [('A','Z')]); raise SystemExit('unknown ref not caught')
except GraphValidationError as e:
    print('unknown ref rejected:', e)
print('OK')
"
```

Expected: prints `cycle rejected: ...`, `unknown ref rejected: ...`, `OK`; no assertion error.

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/orchestrator/graph_validation.py
git commit -m "feat(orchestrator): DAG graph validation + topology helpers (3A)"
```

---

### Task 4: Snapshot builder + `create_run` integration

**Files:**
- Create: `backend/app/modules/orchestrator/graph_snapshot.py`
- Modify: `backend/app/modules/orchestrator/service.py` (import + call inside `create_run`)

**Interfaces:**
- Consumes: `WorkflowNode`, `WorkflowEdge`, `WorkflowNodeApprover`, `RunNodeExecution` (Task 1); `assert_valid_graph` (Task 3).
- Produces:
  - `build_graph_snapshot(session: Session, workflow_id: uuid.UUID) -> dict | None`
  - `create_run_node_executions(session: Session, run: WorkflowRun, snapshot: dict) -> list[RunNodeExecution]`

- [ ] **Step 1: Create the snapshot module**

Create `backend/app/modules/orchestrator/graph_snapshot.py`:

```python
"""Snapshot the live workflow graph into a Run at creation time (3A).

`build_graph_snapshot` reads the current nodes/edges/approvers (RLS-scoped)
and returns the immutable JSON shape stored on `WorkflowRun.graph_snapshot`;
`create_run_node_executions` materializes one `pending` runtime row per node.
Returns `None` when the workflow has no graph -- the caller then falls back
to the legacy flat run path unchanged.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.orchestrator.graph_validation import assert_valid_graph
from app.modules.orchestrator.models import (
    RunNodeExecution,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeApprover,
    WorkflowRun,
)

__all__ = ["build_graph_snapshot", "create_run_node_executions"]


def build_graph_snapshot(session: Session, workflow_id: uuid.UUID) -> dict | None:
    """Read the live graph for `workflow_id`; return the snapshot dict or None.

    None means "no graph" (zero nodes) -- the legacy flat path applies. A
    non-empty graph is validated (`assert_valid_graph`) before snapshotting so
    a corrupt definition fails loudly at run creation, not mid-execution.
    """
    nodes = list(
        session.execute(
            select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
        ).scalars().all()
    )
    if not nodes:
        return None

    edges = list(
        session.execute(
            select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        ).scalars().all()
    )
    node_by_id = {n.id: n for n in nodes}
    edge_key_pairs = [
        (node_by_id[e.from_node_id].node_key, node_by_id[e.to_node_id].node_key)
        for e in edges
        if e.from_node_id in node_by_id and e.to_node_id in node_by_id
    ]
    assert_valid_graph([n.node_key for n in nodes], edge_key_pairs)

    approvers = list(
        session.execute(
            select(WorkflowNodeApprover).where(
                WorkflowNodeApprover.node_id.in_([n.id for n in nodes])
            )
        ).scalars().all()
    )
    approvers_by_node: dict[uuid.UUID, list[str]] = {}
    for a in approvers:
        approvers_by_node.setdefault(a.node_id, []).append(str(a.user_id))

    return {
        "nodes": [
            {
                "node_key": n.node_key,
                "label": n.label,
                "agent_id": str(n.agent_id),
                "config": n.config or {},
                "position": {"x": n.position_x, "y": n.position_y},
                "approver_user_ids": approvers_by_node.get(n.id, []),
            }
            for n in nodes
        ],
        "edges": [{"from": src, "to": dst} for src, dst in edge_key_pairs],
    }


def create_run_node_executions(
    session: Session, run: WorkflowRun, snapshot: dict
) -> list[RunNodeExecution]:
    """Materialize one `pending` RunNodeExecution per node in the snapshot."""
    rows = [
        RunNodeExecution(
            tenant_id=run.tenant_id,
            run_id=run.id,
            node_key=node["node_key"],
            agent_id=uuid.UUID(node["agent_id"]),
            status="pending",
            approver_user_ids=node.get("approver_user_ids", []),
        )
        for node in snapshot["nodes"]
    ]
    session.add_all(rows)
    return rows
```

- [ ] **Step 2: Wire snapshot into `create_run`**

In `backend/app/modules/orchestrator/service.py`, add the import near the other orchestrator imports:

```python
from app.modules.orchestrator.graph_snapshot import (
    build_graph_snapshot,
    create_run_node_executions,
)
```

Then in `create_run`, replace the run-creation block. The current code is:

```python
    workflow = get_workflow(session, workflow_id)
    tenant_id = tenant_context.get()
    run = WorkflowRun(
        id=uuid7(),
        tenant_id=tenant_id,
        workflow_id=workflow.id,
        status="pending",
        input=input or {},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
```

Replace it with:

```python
    workflow = get_workflow(session, workflow_id)
    tenant_id = tenant_context.get()
    snapshot = build_graph_snapshot(session, workflow.id)
    run = WorkflowRun(
        id=uuid7(),
        tenant_id=tenant_id,
        workflow_id=workflow.id,
        status="pending",
        input=input or {},
        graph_snapshot=snapshot,
    )
    session.add(run)
    session.flush()  # assign run.id before inserting child node-execution rows
    if snapshot is not None:
        create_run_node_executions(session, run, snapshot)
    session.commit()
    session.refresh(run)
    return run
```

- [ ] **Step 3: Verify snapshot end-to-end against the DB**

Write a throwaway script (NOT committed) at the scratchpad path and run it. It seeds a tenant/user/department/agent/workflow + a 3-node graph (A→B,C), creates a run, and asserts the snapshot + rows. Create `C:/Users/Admin/AppData/Local/Temp/claude/D--MPT-VAIC2026-Charcalavong/d722d304-ba68-481f-8f1e-21d4ddb597df/scratchpad/verify_3a.py`:

```python
import uuid
from sqlalchemy import text
from app.core.db import AdminSessionLocal
from app.core.ids import uuid7
from app.core.tenant_context import set_tenant_context
from app.modules.orchestrator.models import (
    Workflow, WorkflowNode, WorkflowEdge, RunNodeExecution,
)
from app.modules.orchestrator.service import create_run

s = AdminSessionLocal()
tid = uuid7(); uid = uuid7(); did = uuid7()
s.execute(text("INSERT INTO tenants (id, name) VALUES (:i, 'v3a')"), {"i": tid})
s.execute(text("INSERT INTO users (id, tenant_id, email) VALUES (:i,:t,'u@v.co')"), {"i": uid, "t": tid})
s.execute(text("INSERT INTO departments (id, tenant_id, name) VALUES (:i,:t,'d')"), {"i": did, "t": tid})
aid = uuid7()
s.execute(text("INSERT INTO agents (id, tenant_id, department_id, owner_id, name, system_prompt) "
               "VALUES (:i,:t,:d,:o,'a','p')"), {"i": aid, "t": tid, "d": did, "o": uid})
wf = Workflow(id=uuid7(), tenant_id=tid, owner_id=uid, name="w", description="d", version=1)
s.add(wf); s.flush()
nA = WorkflowNode(id=uuid7(), tenant_id=tid, workflow_id=wf.id, node_key="A", label="A", agent_id=aid)
nB = WorkflowNode(id=uuid7(), tenant_id=tid, workflow_id=wf.id, node_key="B", label="B", agent_id=aid)
nC = WorkflowNode(id=uuid7(), tenant_id=tid, workflow_id=wf.id, node_key="C", label="C", agent_id=aid)
s.add_all([nA, nB, nC]); s.flush()
s.add_all([
    WorkflowEdge(id=uuid7(), tenant_id=tid, workflow_id=wf.id, from_node_id=nA.id, to_node_id=nB.id),
    WorkflowEdge(id=uuid7(), tenant_id=tid, workflow_id=wf.id, from_node_id=nA.id, to_node_id=nC.id),
])
s.commit()
set_tenant_context(tid)
run = create_run(s, wf.id, role="builder", input={"x": 1})
assert run.graph_snapshot is not None, "snapshot missing"
assert len(run.graph_snapshot["nodes"]) == 3, run.graph_snapshot
assert len(run.graph_snapshot["edges"]) == 2, run.graph_snapshot
rows = s.query(RunNodeExecution).filter(RunNodeExecution.run_id == run.id).all()
assert {r.node_key for r in rows} == {"A", "B", "C"}, rows
assert all(r.status == "pending" for r in rows)
# cleanup
s.execute(text("DELETE FROM tenants WHERE id=:i"), {"i": tid}); s.commit()
print("3A snapshot verify OK")
```

Run:

```bash
cd backend && .venv/Scripts/python.exe C:/Users/Admin/AppData/Local/Temp/claude/D--MPT-VAIC2026-Charcalavong/d722d304-ba68-481f-8f1e-21d4ddb597df/scratchpad/verify_3a.py
```

Expected: `3A snapshot verify OK`. (If the `tenants`/`users` insert columns differ from the real schema, adjust the seed SQL to match the actual columns — introspect with `\d tenants`.) Delete the script after.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/orchestrator/graph_snapshot.py backend/app/modules/orchestrator/service.py
git commit -m "feat(orchestrator): snapshot graph into run on create (3A)"
```

---

### Task 5: Serialization helpers for the new entities

**Files:**
- Create: `backend/app/modules/orchestrator/graph_serialization.py`

**Interfaces:**
- Consumes: `RunNodeExecution` (Task 1).
- Produces:
  - `serialize_run_node_execution(row: RunNodeExecution) -> dict`
  - `serialize_graph_snapshot(snapshot: dict | None) -> dict | None` (pass-through; the stored shape is already response-ready)

- [ ] **Step 1: Create the serialization module**

Create `backend/app/modules/orchestrator/graph_serialization.py`:

```python
"""Response shapes for graph runtime entities (3A).

Consumed by the Tracking UI + review endpoints (3C). Timestamps are ISO 8601
with millisecond precision (AR-14), matching `service.serialize_run`.
"""

from __future__ import annotations

from app.modules.orchestrator.models import RunNodeExecution

__all__ = ["serialize_run_node_execution", "serialize_graph_snapshot"]


def _iso_ms(dt) -> str | None:
    return dt.isoformat(timespec="milliseconds") if dt else None


def serialize_run_node_execution(row: RunNodeExecution) -> dict:
    """Response payload for one per-node runtime row."""
    return {
        "id": str(row.id),
        "run_id": str(row.run_id),
        "node_key": row.node_key,
        "agent_id": str(row.agent_id),
        "status": row.status,
        "input": row.input,
        "output": row.output,
        "approver_user_ids": row.approver_user_ids or [],
        "decision": row.decision,
        "decided_by": str(row.decided_by) if row.decided_by else None,
        "reason": row.reason,
        "guidance": row.guidance,
        "decided_at": _iso_ms(row.decided_at),
        "started_at": _iso_ms(row.started_at),
        "completed_at": _iso_ms(row.completed_at),
        "created_at": _iso_ms(row.created_at),
    }


def serialize_graph_snapshot(snapshot: dict | None) -> dict | None:
    """The stored snapshot is already response-ready; return it verbatim."""
    return snapshot
```

- [ ] **Step 2: Verify serialization shape (no DB needed)**

Run:

```bash
cd backend && .venv/Scripts/python.exe -c "
import uuid
from app.modules.orchestrator.models import RunNodeExecution
from app.modules.orchestrator.graph_serialization import serialize_run_node_execution
r = RunNodeExecution(id=uuid.uuid4(), tenant_id=uuid.uuid4(), run_id=uuid.uuid4(), node_key='A', agent_id=uuid.uuid4(), status='pending', approver_user_ids=[])
d = serialize_run_node_execution(r)
assert d['node_key']=='A' and d['status']=='pending' and d['decided_by'] is None and d['approver_user_ids']==[]
print('serialize OK:', sorted(d.keys()))
"
```

Expected: `serialize OK: [...]` listing all keys; no assertion error.

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/orchestrator/graph_serialization.py
git commit -m "feat(orchestrator): serialization for graph runtime entities (3A)"
```

---

## Self-Review

**Spec coverage:**
- §3.1 definition tables (nodes/edges/approvers) → Task 1 (models) + Task 2 (migration). ✓
- §3.2 runtime tables (`graph_snapshot` + `run_node_executions`) + status enum → Task 1 + Task 2. ✓
- §4 snapshot-on-create + flat fallback → Task 4. ✓
- §5 validation (dup keys, unknown refs, dup edge, cycle) → Task 3 (`assert_valid_graph`); approver-tenant-membership check is enforced by the `users` FK + RLS at insert (authoring wiring is 3D, noted). ✓
- §7 deliverables: models (T1), migration (T2), snapshot logic (T4), validation helpers (T3), serialization (T5). ✓

**Placeholder scan:** No TBD/TODO; all code blocks complete; every verification has an exact command + expected output.

**Type consistency:** `node_key`/`agent_id`/`approver_user_ids`/`status` names match across models (T1), migration (T2), snapshot (T4), serialization (T5). `assert_valid_graph(node_keys, edges)` signature identical in T3 definition and T4 usage. Snapshot dict shape (`nodes[].node_key`, `edges[].from/to`) consistent between T4 producer and the spec §3.2.

**Note (self-review finding, folded in):** §5 lists "approver user_id must be a tenant member" as a validation. That check needs a DB (user lookup), so it is NOT in the pure `graph_validation.py`; it is enforced structurally by the `workflow_node_approvers.user_id` FK + tenant RLS, and the explicit authoring-time check lands in 3D. Flagged so it is not mistaken for a gap.

## Open questions
- The Task 4 Step 3 seed SQL assumes `tenants(name)`, `users(email)`, `departments(name)`, `agents(system_prompt)` columns. If the real schema differs, adjust the seed inserts (introspect first). This affects only the throwaway verification, not shipped code.
