# Graph Workflow Execution Engine (3B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a resumable, state-driven engine that executes a builder-authored DAG run in topological order, pauses at human-gated nodes for Approve/Retry/Override/Reject decisions, and runs the reject→rollback protocol.

**Architecture:** A new `graph_engine.graph_orchestrate` walks the run's immutable `graph_snapshot`, resolving each node's input from its parents' outputs and dispatching the node's agent via `AgentExecutor.execute_task`. All engine state is recomputed from `run_node_executions` + `graph_snapshot` on each (re)entry — nothing survives a pause. Human decisions and rollback confirms are recorded through a new `graph_routes` router + `graph_review` service, each ending by re-enqueuing `run_workflow(resume=True)`. The flat `orchestrate_run` path is untouched; the worker branches on the presence of `graph_snapshot`.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy (ORM + `text()` CAS), arq (Redis jobs), Alembic (Postgres migrations), Postgres row-level security (RLS).

## Global Constraints

- **No new tests.** Project preference (CLAUDE.md) overrides the skill's TDD default: do NOT write test files unless the user explicitly asks. Each task's verification is an import/smoke check, not a test suite.
- **Do not auto-run** `typecheck`/`lint`/`test`/`build`/`format`. Run only the explicit verification command in each task.
- All backend code lives under `backend/`. Paths below are repo-relative.
- **RLS re-assertion:** after every `commit()` (each CAS commits), call `_reassert_rls(session)` before the next DB statement — `SET LOCAL ROLE` / tenant var are transaction-scoped. Reuse `app.modules.orchestrator.service._reassert_rls`.
- **State transitions go through CAS**, never bare ORM assignment. Runs use `transition_and_audit` (existing); nodes use the new `transition_node_status` (Task 3).
- **Audit** every state-changing endpoint action via the existing `_audit(session, dict(...))` helper (`app.modules.orchestrator.service`) → `PostgresAuditSink`. Never write audit rows with direct SQL.
- **Run statuses** (`workflow_runs`): `pending, running, awaiting_human, completed, failed, timed_out`.
- **Node statuses** (`run_node_executions`): `pending, running, awaiting_approval, completed, failed, rejected, skipped, rolled_back`. Do NOT add new node statuses (open question resolved: an in-flight rollback is signalled by the pending `run_rollback_requests` row, node stays `awaiting_approval`).
- **JSONB writes** mirror the existing flat path: pass `json.dumps(value)` in `extra_cols` (same as `orchestrate_run`'s `{"result": json.dumps(result)}`).
- **Modularize** any file exceeding ~200 lines; kebab-case long descriptive filenames.
- **Role constant** in migrations: `APP_ROLE = "vaic_app"`; RLS grant is `SELECT, INSERT, UPDATE` (no DELETE).

---

### Task 1: `descendants` topology helper

Pure function; foundation for rollback subtree invalidation. No `descendants` exists in `graph_validation.py` today.

**Files:**
- Modify: `backend/app/modules/orchestrator/graph_validation.py`

**Interfaces:**
- Produces: `descendants(node_keys: list[str], edges: list[tuple[str, str]], target: str) -> set[str]` — all nodes reachable from `target`, `target` excluded.

- [ ] **Step 1: Add the function and export it**

At the end of `backend/app/modules/orchestrator/graph_validation.py`, add:

```python
def descendants(
    node_keys: list[str], edges: list[tuple[str, str]], target: str
) -> set[str]:
    """All node keys reachable from `target` following edge direction.

    `target` itself is excluded. Assumes an already-validated DAG.
    """
    adjacency: dict[str, list[str]] = {k: [] for k in node_keys}
    for src, dst in edges:
        adjacency[src].append(dst)
    seen: set[str] = set()
    stack = list(adjacency.get(target, []))
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, []))
    seen.discard(target)
    return seen
```

Then add `"descendants"` to the module's `__all__` list (currently `GraphValidationError, assert_valid_graph, root_keys, parents_by_key, topological_order`).

- [ ] **Step 2: Verify it imports and behaves**

Run:
```bash
cd backend && python -c "from app.modules.orchestrator.graph_validation import descendants; print(sorted(descendants(['A','B','C','D'], [('A','B'),('B','C'),('A','D')], 'A'))); print(sorted(descendants(['A','B','C','D'], [('A','B'),('B','C'),('A','D')], 'B')))"
```
Expected output:
```
['B', 'C', 'D']
['C']
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/orchestrator/graph_validation.py
git commit -m "feat(orchestrator): descendants() topology helper for rollback (3B)"
```

---

### Task 2: `RunRollbackRequest` model + Alembic migration

Adds the `run_rollback_requests` table (tenant-scoped RLS). Node status CHECK is NOT changed (open question resolved).

**Files:**
- Modify: `backend/app/modules/orchestrator/models.py`
- Create: `backend/alembic/versions/d4e5f6a7b8c9_create_run_rollback_requests.py`

**Interfaces:**
- Produces: ORM model `RunRollbackRequest` with columns `id, tenant_id, run_id, requester_node_key, target_node_key, reason, status, decided_by, decided_at, created_at`. Statuses: `pending, accepted, refused`. Table `run_rollback_requests`.

- [ ] **Step 1: Add the model**

In `backend/app/modules/orchestrator/models.py`, add near the other status tuples (top of file, beside `NODE_EXECUTION_STATUSES`):

```python
ROLLBACK_STATUSES = ("pending", "accepted", "refused")
```

After the `RunNodeExecution` class, add:

```python
class RunRollbackRequest(Base):
    """A reject-driven request to roll a run back to a chosen parent node (3B).

    Created `pending` when a human rejects a gated node. The target parent's
    approver confirms (accepted) or refuses (refused); an auto target parent
    (no approvers) is auto-accepted at reject time.
    """

    __tablename__ = "run_rollback_requests"
    __table_args__ = (
        CheckConstraint(
            f"status IN {ROLLBACK_STATUSES!r}",
            name="ck_run_rollback_requests_status",
        ),
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
    requester_node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target_node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

(Confirm `CheckConstraint, ForeignKey, String, Text, DateTime, Mapped, mapped_column, func, uuid7, UUID` are already imported at the top of `models.py` — they are used by the existing models, so no new imports are needed.)

- [ ] **Step 2: Create the migration**

Create `backend/alembic/versions/d4e5f6a7b8c9_create_run_rollback_requests.py`:

```python
"""create run_rollback_requests table (3B)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-18 12:00:00.000000

Adds the reject->rollback request table with tenant-scoped RLS.
Node/run status CHECK constraints are unchanged (an in-flight rollback is
signalled by a pending row here, not a new node status).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"

ROLLBACK_STATUSES = ("pending", "accepted", "refused")


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
    op.create_table(
        "run_rollback_requests",
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
        sa.Column("requester_node_key", sa.String(64), nullable=False),
        sa.Column("target_node_key", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"status IN {ROLLBACK_STATUSES!r}",
            name="ck_run_rollback_requests_status",
        ),
    )
    op.create_index(
        "ix_run_rollback_requests_tenant_id",
        "run_rollback_requests",
        ["tenant_id"],
    )
    op.create_index(
        "ix_run_rollback_requests_run_id",
        "run_rollback_requests",
        ["run_id"],
    )
    op.create_index(
        "ix_run_rollback_requests_status",
        "run_rollback_requests",
        ["status"],
    )
    _enable_rls("run_rollback_requests")


def downgrade() -> None:
    _disable_rls("run_rollback_requests")
    op.drop_table("run_rollback_requests")
```

- [ ] **Step 3: Verify the model imports and migration is discoverable**

Run:
```bash
cd backend && python -c "from app.modules.orchestrator.models import RunRollbackRequest; print(RunRollbackRequest.__tablename__)"
```
Expected: `run_rollback_requests`

Then confirm Alembic sees a single-head linear history:
```bash
cd backend && alembic heads
```
Expected: exactly one head, `d4e5f6a7b8c9 (head)`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/orchestrator/models.py backend/alembic/versions/d4e5f6a7b8c9_create_run_rollback_requests.py
git commit -m "feat(orchestrator): RunRollbackRequest model + RLS migration (3B)"
```

---

### Task 3: `transition_node_status` CAS helper

A compare-and-set primitive for `run_node_executions` (mirrors `transition_run_status`), with an optional extra WHERE clause used for first-wins reject.

**Files:**
- Modify: `backend/app/modules/orchestrator/state.py`

**Interfaces:**
- Produces: `transition_node_status(session, node_id, *, from_status, to_status, extra_cols=None, extra_where=None) -> bool` — CAS on `run_node_executions.status`, stamping `started_at`/`completed_at`; commits; returns `rowcount == 1`.

- [ ] **Step 1: Add the node CAS clauses and function**

In `backend/app/modules/orchestrator/state.py`, near `_RUN_CAS_SET_CLAUSES`, add:

```python
_NODE_CAS_SET_CLAUSES = [
    "status=CAST(:to AS varchar)",
    "started_at = CASE WHEN CAST(:to AS varchar)='running' "
    "THEN now() ELSE started_at END",
    "completed_at = CASE WHEN CAST(:to AS varchar) "
    "IN ('completed','failed','rejected') THEN now() ELSE completed_at END",
]
```

Then add the function (mirrors `transition_run_status`; `text` and `Session` are already imported in this module):

```python
def transition_node_status(
    session: Session,
    node_id: uuid.UUID | str,
    *,
    from_status: str,
    to_status: str,
    extra_cols: dict[str, Any] | None = None,
    extra_where: str | None = None,
) -> bool:
    """CAS transition on a `run_node_executions` row (AD-6 style).

    `extra_where` is ANDed into the WHERE clause (e.g. ``"decision IS NULL"``
    for a first-wins reject that keeps `status` unchanged). Returns True iff
    exactly one row was updated.
    """
    set_clauses = list(_NODE_CAS_SET_CLAUSES)
    params: dict[str, Any] = {
        "to": to_status,
        "from": from_status,
        "id": str(node_id),
    }
    if extra_cols:
        set_clauses.extend(f"{key}=:{key}" for key in extra_cols)
        params.update(extra_cols)

    where = "id=:id AND status=CAST(:from AS varchar)"
    if extra_where:
        where += f" AND {extra_where}"

    sql = text(f"UPDATE run_node_executions SET {', '.join(set_clauses)} WHERE {where}")
    result = session.execute(sql, params)
    session.commit()
    return result.rowcount == 1
```

(Confirm `uuid`, `Any`, `text`, `Session` are already imported at the top of `state.py` — they are used by `transition_run_status`.)

- [ ] **Step 2: Verify it imports**

Run:
```bash
cd backend && python -c "from app.modules.orchestrator.state import transition_node_status; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/orchestrator/state.py
git commit -m "feat(orchestrator): transition_node_status CAS primitive (3B)"
```

---

### Task 4: `graph_engine.py` — the execution engine

The core loop: walk topo order, resolve inputs, dispatch agents, pause at gated nodes, finalize.

**Files:**
- Create: `backend/app/modules/orchestrator/graph_engine.py`

**Interfaces:**
- Consumes: `transition_node_status` (Task 3), `descendants`/`parents_by_key`/`topological_order` (Task 1 + existing), `_reassert_rls`/`_audit` (`service.py`), `AgentExecutor` (`agent_builder`), `get_agent` (`agent_builder.agent_executor`), `transition_and_audit` (`state.py`), `WorkflowRun`/`RunNodeExecution` (`models.py`).
- Produces:
  - `load_graph(snapshot: dict) -> tuple[list[str], dict[str, dict], list[tuple[str, str]]]` → `(node_keys, nodes_by_key, edges)`.
  - `async graph_orchestrate(session, run_id, *, executor=None) -> None`.
  - `async run_node(session, run, row, node, parent_keys, execs, *, executor) -> TaskExecutionResult | None`.
  - `finalize_run(session, run_id, node_keys) -> None`.

- [ ] **Step 1: Write the module**

Create `backend/app/modules/orchestrator/graph_engine.py`:

```python
"""Graph workflow execution engine (Sub-project 3B).

Walks a run's immutable `graph_snapshot` in topological order, resolving each
node's input from its parents' outputs, dispatching the node's agent, and
pausing the whole run at human-gated nodes. Fully state-driven: everything is
recomputed from `run_node_executions` + `graph_snapshot` on each (re)entry, so
`graph_orchestrate` is safe to re-run on the `resume=True` path.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.ids import uuid7
from app.modules.agent_builder.agent_executor import AgentExecutor, get_agent
from app.modules.orchestrator.graph_validation import (
    parents_by_key,
    topological_order,
)
from app.modules.orchestrator.models import RunNodeExecution, WorkflowRun
from app.modules.orchestrator.service import _audit, _reassert_rls
from app.modules.orchestrator.state import (
    transition_and_audit,
    transition_node_status,
)


def load_graph(
    snapshot: dict[str, Any],
) -> tuple[list[str], dict[str, dict[str, Any]], list[tuple[str, str]]]:
    """Parse a stored snapshot into (node_keys, nodes_by_key, edges)."""
    node_keys = [n["node_key"] for n in snapshot["nodes"]]
    nodes_by_key = {n["node_key"]: n for n in snapshot["nodes"]}
    edges = [(e["from"], e["to"]) for e in snapshot["edges"]]
    return node_keys, nodes_by_key, edges


def _load_run(session: Session, run_id: uuid.UUID | str) -> WorkflowRun:
    run = session.get(WorkflowRun, uuid.UUID(str(run_id)))
    if run is None:
        raise RuntimeError(f"graph_orchestrate: run {run_id} not found")
    return run


def _load_node_execs(
    session: Session, run_id: uuid.UUID | str
) -> dict[str, RunNodeExecution]:
    # populate_existing (M-3): the session uses expire_on_commit=False and all
    # node state is mutated via raw-SQL CAS commits that never touch the
    # identity-mapped instances. Without populate_existing this re-query would
    # return STALE cached rows (e.g. status still 'pending' after a committed
    # completion), causing the engine to re-pick a done node and spin forever.
    # Mirrors service.aggregate_run.
    rows = (
        session.query(RunNodeExecution)
        .filter(RunNodeExecution.run_id == uuid.UUID(str(run_id)))
        .execution_options(populate_existing=True)
        .all()
    )
    return {r.node_key: r for r in rows}


def _has_pending_rollback(session: Session, run_id: uuid.UUID | str) -> bool:
    from app.modules.orchestrator.models import RunRollbackRequest

    return (
        session.query(RunRollbackRequest)
        .filter(
            RunRollbackRequest.run_id == uuid.UUID(str(run_id)),
            RunRollbackRequest.status == "pending",
        )
        .first()
        is not None
    )


def _set_run_awaiting_human(session: Session, run_id: uuid.UUID | str) -> None:
    _reassert_rls(session)
    transition_and_audit(
        session,
        kind="run",
        entity_id=run_id,
        run_id=run_id,
        from_status="running",
        to_status="awaiting_human",
    )
    _reassert_rls(session)


def _build_node_payload(
    node: dict[str, Any], resolved_input: dict[str, Any], guidance: str | None
) -> dict[str, Any]:
    """Reuse the flat path's TaskSchemaModel shape (open question resolved)."""
    summary = node.get("label", "") or ""
    if guidance:
        summary = f"{summary}\n\nReviewer guidance: {guidance}"
    return {
        "task": {"summary": summary},
        "target_agent_id": node["agent_id"],
        "input": resolved_input,
        "output": {},
        "expected": [],
        "criteria": node.get("config", {}) or {},
    }


def _node_department(session: Session, agent_id: uuid.UUID | str) -> uuid.UUID:
    return get_agent(session, agent_id).department_id


async def run_node(
    session: Session,
    run: WorkflowRun,
    row: RunNodeExecution,
    node: dict[str, Any],
    parent_keys: list[str],
    execs: dict[str, RunNodeExecution],
    *,
    executor: Any | None = None,
) -> Any:
    """CAS pending->running, resolve input, dispatch the agent.

    Returns the `TaskExecutionResult` on success, or None if the node was
    marked `failed` (infra error) or the pending->running CAS was lost.
    """
    resolved_input: dict[str, Any] = (
        dict(run.input or {})
        if not parent_keys
        else {p: execs[p].output for p in parent_keys}
    )
    _reassert_rls(session)
    # Clear the prior decision slate whenever a node (re-)enters running so a
    # retried node returns to awaiting_approval with decision=NULL (else the
    # review service's `decision IS NULL` first-wins guard would 409 forever)
    # and no stale output survives a failed re-run. `guidance` is intentionally
    # PRESERVED — the agent prompt appends it on a retry/rollback re-run.
    won = transition_node_status(
        session,
        row.id,
        from_status="pending",
        to_status="running",
        extra_cols={
            "input": json.dumps(resolved_input),
            "output": None,
            "decision": None,
            "decided_by": None,
            "reason": None,
            "decided_at": None,
        },
    )
    if not won:
        return None
    _reassert_rls(session)
    payload = _build_node_payload(node, resolved_input, row.guidance)
    executor = executor or AgentExecutor(session)
    dept_id = _node_department(session, row.agent_id)
    try:
        return await executor.execute_task(
            row.agent_id,
            payload,
            tenant_id=row.tenant_id,
            department_id=dept_id,
        )
    except Exception as exc:  # infra error -> node fails, run finalizes failed
        _reassert_rls(session)
        transition_node_status(
            session, row.id, from_status="running", to_status="failed"
        )
        _reassert_rls(session)
        _audit(
            session,
            dict(
                run_id=str(run.id),
                step_id=str(uuid7()),
                agent_id=str(row.agent_id),
                type="graph_node.failed",
                input={"node_key": row.node_key},
                output={"error": str(exc)},
                latency_ms=0,
            ),
        )
        return None


def finalize_run(session: Session, run_id: uuid.UUID | str, node_keys: list[str]) -> None:
    """Aggregate node outputs into run.result; CAS running->completed/failed."""
    _reassert_rls(session)
    execs = _load_node_execs(session, run_id)
    result = {k: execs[k].output for k in node_keys if k in execs}
    any_failed = any(execs[k].status == "failed" for k in node_keys if k in execs)
    to_status = "failed" if any_failed else "completed"
    _reassert_rls(session)
    transition_and_audit(
        session,
        kind="run",
        entity_id=run_id,
        run_id=run_id,
        from_status="running",
        to_status=to_status,
        extra_cols={"result": json.dumps(result)},
    )
    _reassert_rls(session)


async def graph_orchestrate(
    session: Session, run_id: uuid.UUID | str, *, executor: Any | None = None
) -> None:
    """Engine entrypoint. Re-enterable; recomputes state each call."""
    _reassert_rls(session)
    run = _load_run(session, run_id)
    snapshot = run.graph_snapshot
    node_keys, nodes_by_key, edges = load_graph(snapshot)
    parents = parents_by_key(node_keys, edges)
    order = topological_order(node_keys, edges)

    while True:
        _reassert_rls(session)
        run = _load_run(session, run_id)
        execs = _load_node_execs(session, run_id)

        # Guard 1: a pending rollback blocks all forward progress.
        if _has_pending_rollback(session, run_id):
            _set_run_awaiting_human(session, run_id)
            return

        # Guard 2: a node awaiting a human decision -> pause.
        if any(r.status == "awaiting_approval" for r in execs.values()):
            _set_run_awaiting_human(session, run_id)
            return

        # Guard 3: next runnable node in topo order.
        nxt = None
        for key in order:
            r = execs[key]
            if r.status == "pending" and all(
                execs[p].status == "completed" for p in parents[key]
            ):
                nxt = r
                break
        if nxt is None:
            finalize_run(session, run_id, node_keys)
            return

        node = nodes_by_key[nxt.node_key]
        res = await run_node(
            session, run, nxt, node, parents[nxt.node_key], execs, executor=executor
        )
        if res is None:  # failed or lost race -> re-loop (guard 3 will finalize)
            continue

        _reassert_rls(session)
        if nxt.approver_user_ids:  # human-gated -> pause for review
            transition_node_status(
                session,
                nxt.id,
                from_status="running",
                to_status="awaiting_approval",
                extra_cols={"output": json.dumps(res.output)},
            )
            _set_run_awaiting_human(session, run_id)
            return
        # Non-gated node: fail the run if the agent reported an unsuccessful
        # result (no human to catch it), consistent with the flat path's
        # _has_succeeded_task. Gated nodes above still pause for review.
        to_status = "completed" if res.success else "failed"
        transition_node_status(
            session,
            nxt.id,
            from_status="running",
            to_status=to_status,
            extra_cols={"output": json.dumps(res.output)},
        )
        # continue loop
```

- [ ] **Step 2: Verify it imports (resolves `get_agent` path)**

Run:
```bash
cd backend && python -c "from app.modules.orchestrator.graph_engine import graph_orchestrate, run_node, finalize_run, load_graph; print('ok')"
```
Expected: `ok`

If the import fails on `get_agent`, locate it and fix the import line only:
```bash
cd backend && grep -rn "def get_agent" app/modules/agent_builder/
```
Import `get_agent` from the module where it is defined (adjust the `from app.modules.agent_builder... import ... get_agent` line accordingly). Re-run the smoke import until it prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/orchestrator/graph_engine.py
git commit -m "feat(orchestrator): graph execution engine loop + run_node + finalize (3B)"
```

---

### Task 5: Worker routing — dispatch graph runs to the engine

Branch `run_workflow` on `graph_snapshot`; add the `awaiting_human→running` resume CAS for graph runs. Flat path unchanged.

**Files:**
- Modify: `backend/app/workers/orchestrator_worker.py`

**Interfaces:**
- Consumes: `graph_orchestrate` (Task 4), `_transition` (existing helper in this file), `WorkflowRun` (`models.py`).

- [ ] **Step 1: Add imports**

In `backend/app/workers/orchestrator_worker.py`, add to the imports block:

```python
from app.modules.orchestrator.graph_engine import graph_orchestrate
from app.modules.orchestrator.models import WorkflowRun
```

- [ ] **Step 2: Branch on graph_snapshot in `run_workflow`**

Replace the body of `run_workflow` after the `loop = asyncio.get_running_loop()` line (the current `if not resume: ... await orchestrate_run(session, run_id)`) with:

```python
    # Branch: graph runs (immutable graph_snapshot present) go to the 3B engine;
    # graphless runs keep the flat orchestrate_run path (unchanged).
    run = session.get(WorkflowRun, uuid.UUID(run_id))
    is_graph = run is not None and run.graph_snapshot is not None

    if is_graph:
        # Fresh dispatch: pending->running. Resume of a paused run: awaiting_human->running.
        from_status = "awaiting_human" if resume else "pending"
        won = await loop.run_in_executor(
            None, _transition, session, tenant_id, run_id, from_status, "running"
        )
        if not won:
            logger.debug(
                "run_workflow: lost %s->running race run_id=%s", from_status, run_id
            )
            return
        await graph_orchestrate(session, run_id)
        return

    # Flat path (unchanged).
    if not resume:
        won = await loop.run_in_executor(
            None, _transition, session, tenant_id, run_id, "pending", "running"
        )
        if not won:
            logger.debug("run_workflow: lost pending->running race run_id=%s", run_id)
            return
    await orchestrate_run(session, run_id)
```

(The initial `session.get(WorkflowRun, ...)` read runs under the RLS the `@tenant_aware_job` decorator set on the session's open transaction, before any CAS commit — safe.)

- [ ] **Step 3: Verify the worker module imports**

Run:
```bash
cd backend && python -c "from app.workers.orchestrator_worker import run_workflow; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/workers/orchestrator_worker.py
git commit -m "feat(orchestrator): route graph runs to engine + resume CAS (3B)"
```

---

### Task 6: `graph_review.py` — decision + rollback service

Implements approve/retry/override/reject and rollback accept/refuse, plus the nodes-listing read. No HTTP here; endpoints (Task 7) call these.

**Files:**
- Create: `backend/app/modules/orchestrator/graph_review.py`

**Interfaces:**
- Consumes: `transition_node_status` (Task 3), `descendants`/`parents_by_key` (Task 1 + existing), `load_graph` (Task 4), `_reassert_rls`/`_audit` (`service.py`), `serialize_run_node_execution` (`graph_serialization.py`), `WorkflowRun`/`RunNodeExecution`/`RunRollbackRequest` (`models.py`).
- Produces:
  - `record_decision(session, run_id, node_key, *, action, actor_user_id, guidance=None, output=None, reason=None, target_node_key=None) -> dict` (raises `ReviewError` on invalid state/authz/args).
  - `confirm_rollback(session, run_id, rollback_id, *, accept, actor_user_id) -> dict`.
  - `list_run_nodes(session, run_id) -> dict` → `{"nodes": [...], "rollbacks": {"pending": [...], "refused": [...]}}`.
  - `class ReviewError(Exception)` carrying `.status_code: int`.

- [ ] **Step 1: Write the module**

Create `backend/app/modules/orchestrator/graph_review.py`:

```python
"""Human-review decision + rollback service for graph runs (Sub-project 3B).

Pure service layer (no HTTP). Each decision mutates `run_node_executions` /
`run_rollback_requests` via CAS and the caller (graph_routes) re-enqueues
`run_workflow(resume=True)`.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.ids import uuid7
from app.modules.orchestrator.graph_engine import load_graph
from app.modules.orchestrator.graph_serialization import serialize_run_node_execution
from app.modules.orchestrator.graph_validation import descendants, parents_by_key
from app.modules.orchestrator.models import (
    RunNodeExecution,
    RunRollbackRequest,
    WorkflowRun,
)
from app.modules.orchestrator.service import _audit, _reassert_rls
from app.modules.orchestrator.state import transition_node_status

_VALID_ACTIONS = ("approve", "retry", "override", "reject")


class ReviewError(Exception):
    """Service-level error with an HTTP status hint."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _load_run(session: Session, run_id: uuid.UUID | str) -> WorkflowRun:
    run = session.get(WorkflowRun, uuid.UUID(str(run_id)))
    if run is None:
        raise ReviewError(404, "run not found")
    return run


def _get_node(
    session: Session, run_id: uuid.UUID | str, node_key: str
) -> RunNodeExecution:
    # populate_existing: stale identity-map guard after raw-SQL CAS commits
    # (session uses expire_on_commit=False); mirrors graph_engine._load_node_execs.
    row = (
        session.query(RunNodeExecution)
        .filter(
            RunNodeExecution.run_id == uuid.UUID(str(run_id)),
            RunNodeExecution.node_key == node_key,
        )
        .execution_options(populate_existing=True)
        .first()
    )
    if row is None:
        raise ReviewError(404, f"node {node_key} not found")
    return row


def _require_approver(row_or_keys: Any, actor_user_id: uuid.UUID | str) -> None:
    approvers = (
        row_or_keys.approver_user_ids
        if hasattr(row_or_keys, "approver_user_ids")
        else row_or_keys
    ) or []
    if str(actor_user_id) not in [str(a) for a in approvers]:
        raise ReviewError(403, "caller is not an approver of this node")


def _audit_decision(
    session: Session, run_id: uuid.UUID | str, node_key: str, action: str, actor: Any
) -> None:
    _reassert_rls(session)
    _audit(
        session,
        dict(
            run_id=str(run_id),
            step_id=str(uuid7()),
            agent_id="",
            type=f"graph_node.{action}",
            input={"node_key": node_key, "actor": str(actor)},
            output={},
            latency_ms=0,
        ),
    )


# --- node decisions ----------------------------------------------------------


def record_decision(
    session: Session,
    run_id: uuid.UUID | str,
    node_key: str,
    *,
    action: str,
    actor_user_id: uuid.UUID | str,
    guidance: str | None = None,
    output: dict[str, Any] | None = None,
    reason: str | None = None,
    target_node_key: str | None = None,
) -> dict[str, Any]:
    if action not in _VALID_ACTIONS:
        raise ReviewError(400, f"invalid action: {action}")
    row = _get_node(session, run_id, node_key)
    if row.status != "awaiting_approval":
        raise ReviewError(409, "node is not awaiting a decision")
    _require_approver(row, actor_user_id)

    common = {"decided_by": str(actor_user_id), "decided_at": _now_sql_marker()}

    if action == "approve":
        _cas_or_conflict(
            session, row.id, "awaiting_approval", "completed",
            {**common, "decision": "approve"},
        )
    elif action == "retry":
        _cas_or_conflict(
            session, row.id, "awaiting_approval", "pending",
            {**common, "decision": "retry", "guidance": guidance},
        )
    elif action == "override":
        _cas_or_conflict(
            session, row.id, "awaiting_approval", "completed",
            {**common, "decision": "override", "output": json.dumps(output or {})},
        )
    else:  # reject
        return _do_reject(
            session, run_id, row, actor_user_id, reason, target_node_key
        )

    _audit_decision(session, run_id, node_key, action, actor_user_id)
    _reassert_rls(session)
    return serialize_run_node_execution(_get_node(session, run_id, node_key))


def _now_sql_marker() -> Any:
    # decided_at is stamped by SQL now() via a dedicated UPDATE below; the
    # CAS helper writes plain params, so we set decided_at through text().
    return None


def _cas_or_conflict(
    session: Session,
    node_id: uuid.UUID,
    from_status: str,
    to_status: str,
    extra_cols: dict[str, Any],
) -> None:
    # Drop the decided_at sentinel; stamp it via a follow-up now() update.
    cols = {k: v for k, v in extra_cols.items() if v is not None or k == "guidance"}
    cols.pop("decided_at", None)
    _reassert_rls(session)
    # extra_where "decision IS NULL" enforces first-wins AND locks out
    # approve/retry/override once the node has been rejected (reject keeps
    # status awaiting_approval but sets decision='reject').
    won = transition_node_status(
        session,
        node_id,
        from_status=from_status,
        to_status=to_status,
        extra_cols=cols,
        extra_where="decision IS NULL",
    )
    if not won:
        raise ReviewError(409, "node already decided")
    _reassert_rls(session)
    session.execute(
        text("UPDATE run_node_executions SET decided_at=now() WHERE id=:id"),
        {"id": str(node_id)},
    )
    session.commit()
    _reassert_rls(session)


def _do_reject(
    session: Session,
    run_id: uuid.UUID | str,
    row: RunNodeExecution,
    actor_user_id: uuid.UUID | str,
    reason: str | None,
    target_node_key: str | None,
) -> dict[str, Any]:
    run = _load_run(session, run_id)
    node_keys, _nodes_by_key, edges = load_graph(run.graph_snapshot)
    parents = parents_by_key(node_keys, edges)
    if not target_node_key or target_node_key not in parents.get(row.node_key, []):
        raise ReviewError(400, "target_node_key must be a parent of the node")

    # First-wins on reject: node stays awaiting_approval, but decision must be NULL.
    _reassert_rls(session)
    won = transition_node_status(
        session,
        row.id,
        from_status="awaiting_approval",
        to_status="awaiting_approval",
        extra_cols={"decision": "reject", "reason": reason, "decided_by": str(actor_user_id)},
        extra_where="decision IS NULL",
    )
    if not won:
        raise ReviewError(409, "node already decided")
    _reassert_rls(session)
    session.execute(
        text("UPDATE run_node_executions SET decided_at=now() WHERE id=:id"),
        {"id": str(row.id)},
    )
    session.commit()

    _reassert_rls(session)
    req = RunRollbackRequest(
        id=uuid7(),
        tenant_id=row.tenant_id,
        run_id=uuid.UUID(str(run_id)),
        requester_node_key=row.node_key,
        target_node_key=target_node_key,
        reason=reason,
        status="pending",
    )
    session.add(req)
    session.commit()
    _audit_decision(session, run_id, row.node_key, "reject", actor_user_id)

    # Auto target parent (no approvers) -> auto-accept inline.
    _reassert_rls(session)  # _audit_decision committed -> RLS scope dropped
    target_row = _get_node(session, run_id, target_node_key)
    if not (target_row.approver_user_ids or []):
        _reassert_rls(session)
        _accept_rollback(session, run_id, req, decided_by=None)

    _reassert_rls(session)
    return serialize_run_node_execution(_get_node(session, run_id, row.node_key))


# --- rollback confirm --------------------------------------------------------


def confirm_rollback(
    session: Session,
    run_id: uuid.UUID | str,
    rollback_id: uuid.UUID | str,
    *,
    accept: bool,
    actor_user_id: uuid.UUID | str,
) -> dict[str, Any]:
    req = session.get(RunRollbackRequest, uuid.UUID(str(rollback_id)))
    if req is None or str(req.run_id) != str(run_id):
        raise ReviewError(404, "rollback request not found")
    if req.status != "pending":
        raise ReviewError(409, "rollback already resolved")
    target_row = _get_node(session, run_id, req.target_node_key)
    _require_approver(target_row, actor_user_id)

    if accept:
        _accept_rollback(session, run_id, req, decided_by=actor_user_id)
    else:
        _refuse_rollback(session, run_id, req, decided_by=actor_user_id)
    _reassert_rls(session)
    return {"id": str(req.id), "status": "accepted" if accept else "refused"}


def _reset_node_to_pending(
    session: Session, node_id: uuid.UUID, *, guidance: str | None = None
) -> None:
    session.execute(
        text(
            """UPDATE run_node_executions
               SET status='pending', output=NULL, decision=NULL, decided_by=NULL,
                   reason=NULL, guidance=:guidance, decided_at=NULL,
                   started_at=NULL, completed_at=NULL, input=NULL
               WHERE id=:id"""
        ),
        {"id": str(node_id), "guidance": guidance},
    )
    session.commit()


def _accept_rollback(
    session: Session,
    run_id: uuid.UUID | str,
    req: RunRollbackRequest,
    *,
    decided_by: uuid.UUID | str | None,
) -> None:
    _reassert_rls(session)
    session.execute(
        text(
            "UPDATE run_rollback_requests SET status='accepted', decided_by=:by, "
            "decided_at=now() WHERE id=:id"
        ),
        {"by": str(decided_by) if decided_by else None, "id": str(req.id)},
    )
    session.commit()

    _reassert_rls(session)
    run = _load_run(session, run_id)
    node_keys, _nodes_by_key, edges = load_graph(run.graph_snapshot)
    desc = descendants(node_keys, edges, req.target_node_key)

    # Mark the whole descendant subtree rolled_back, then pending (spec 5.3).
    for key in desc:
        node = _get_node(session, run_id, key)
        session.execute(
            text("UPDATE run_node_executions SET status='rolled_back' WHERE id=:id"),
            {"id": str(node.id)},
        )
    session.commit()
    _reassert_rls(session)
    for key in desc:
        node = _get_node(session, run_id, key)
        _reset_node_to_pending(session, node.id)
        _reassert_rls(session)

    # Reset the target itself -> pending with the reject reason as guidance.
    target = _get_node(session, run_id, req.target_node_key)
    _reset_node_to_pending(session, target.id, guidance=req.reason)
    _reassert_rls(session)
    _audit(
        session,
        dict(
            run_id=str(run_id),
            step_id=str(uuid7()),
            agent_id="",
            type="graph_rollback.accepted",
            input={"target": req.target_node_key, "requester": req.requester_node_key},
            output={"descendants": sorted(desc)},
            latency_ms=0,
        ),
    )
    _reassert_rls(session)


def _refuse_rollback(
    session: Session,
    run_id: uuid.UUID | str,
    req: RunRollbackRequest,
    *,
    decided_by: uuid.UUID | str,
) -> None:
    _reassert_rls(session)
    session.execute(
        text(
            "UPDATE run_rollback_requests SET status='refused', decided_by=:by, "
            "decided_at=now() WHERE id=:id"
        ),
        {"by": str(decided_by), "id": str(req.id)},
    )
    session.commit()
    # Return the rejecting node to a fresh awaiting_approval decision state:
    # clear its reject decision so it can be Approve/Retry/Override'd again.
    _reassert_rls(session)
    node = _get_node(session, run_id, req.requester_node_key)
    session.execute(
        text(
            "UPDATE run_node_executions SET decision=NULL, decided_by=NULL, "
            "reason=NULL, decided_at=NULL WHERE id=:id"
        ),
        {"id": str(node.id)},
    )
    session.commit()
    _reassert_rls(session)
    _audit(
        session,
        dict(
            run_id=str(run_id),
            step_id=str(uuid7()),
            agent_id="",
            type="graph_rollback.refused",
            input={"target": req.target_node_key, "requester": req.requester_node_key},
            output={},
            latency_ms=0,
        ),
    )
    _reassert_rls(session)


# --- read model --------------------------------------------------------------


def list_run_nodes(session: Session, run_id: uuid.UUID | str) -> dict[str, Any]:
    _reassert_rls(session)
    rows = (
        session.query(RunNodeExecution)
        .filter(RunNodeExecution.run_id == uuid.UUID(str(run_id)))
        .execution_options(populate_existing=True)
        .all()
    )
    reqs = (
        session.query(RunRollbackRequest)
        .filter(RunRollbackRequest.run_id == uuid.UUID(str(run_id)))
        .execution_options(populate_existing=True)
        .all()
    )

    def _ser_req(r: RunRollbackRequest) -> dict[str, Any]:
        return {
            "id": str(r.id),
            "requester_node_key": r.requester_node_key,
            "target_node_key": r.target_node_key,
            "reason": r.reason,
            "status": r.status,
        }

    return {
        "nodes": [serialize_run_node_execution(r) for r in rows],
        "rollbacks": {
            "pending": [_ser_req(r) for r in reqs if r.status == "pending"],
            "refused": [_ser_req(r) for r in reqs if r.status == "refused"],
        },
    }
```

- [ ] **Step 2: Verify it imports**

Run:
```bash
cd backend && python -c "from app.modules.orchestrator.graph_review import record_decision, confirm_rollback, list_run_nodes, ReviewError; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/orchestrator/graph_review.py
git commit -m "feat(orchestrator): graph review + rollback service (3B)"
```

---

### Task 7: `graph_routes.py` — HTTP endpoints + mount

The three backend endpoints, each ending by enqueuing `run_workflow(resume=True)`.

**Files:**
- Create: `backend/app/modules/orchestrator/graph_routes.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `record_decision`/`confirm_rollback`/`list_run_nodes`/`ReviewError` (Task 6), `get_tenant_session`/`get_arq_pool`/`enqueue_job_with_context` (existing).
- Produces: FastAPI `router` (prefix `/workflows`) with:
  - `GET /workflows/runs/{run_id}/nodes`
  - `POST /workflows/runs/{run_id}/nodes/{node_key}/decision`
  - `POST /workflows/runs/{run_id}/rollbacks/{rollback_id}/confirm`

- [ ] **Step 1: Write the router**

Create `backend/app/modules/orchestrator/graph_routes.py`:

```python
"""Backend HTTP endpoints for graph run review + rollback (Sub-project 3B).

UI is 3C (this router is polled). Every state-changing endpoint records its
decision, audits it, and re-enqueues run_workflow(resume=True).
"""
from __future__ import annotations

import uuid
from typing import Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.arq_pool import get_arq_pool
from app.core.deps import get_tenant_session
from app.core.jobs import enqueue_job_with_context
from app.modules.orchestrator.graph_review import (
    ReviewError,
    confirm_rollback,
    list_run_nodes,
    record_decision,
)

router = APIRouter(prefix="/workflows", tags=["workflows-graph"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _err(message: str) -> dict[str, Any]:
    return {"data": None, "error": {"message": message}, "meta": {}}


def _actor_user_id(request: Request) -> uuid.UUID:
    return uuid.UUID(str(request.state.user_id))


class DecisionRequest(BaseModel):
    action: str
    guidance: str | None = None
    output: dict[str, Any] | None = None
    reason: str | None = None
    target_node_key: str | None = None


class ConfirmRequest(BaseModel):
    accept: bool


@router.get("/runs/{run_id}/nodes")
async def list_nodes_route(
    run_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    return JSONResponse(status_code=200, content=_ok(list_run_nodes(session, run_id)))


@router.post("/runs/{run_id}/nodes/{node_key}/decision")
async def node_decision_route(
    run_id: uuid.UUID,
    node_key: str,
    body: DecisionRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> JSONResponse:
    try:
        data = record_decision(
            session,
            run_id,
            node_key,
            action=body.action,
            actor_user_id=_actor_user_id(request),
            guidance=body.guidance,
            output=body.output,
            reason=body.reason,
            target_node_key=body.target_node_key,
        )
    except ReviewError as exc:
        return JSONResponse(status_code=exc.status_code, content=_err(exc.message))
    await enqueue_job_with_context(pool, "run_workflow", run_id=str(run_id), resume=True)
    return JSONResponse(status_code=200, content=_ok(data))


@router.post("/runs/{run_id}/rollbacks/{rollback_id}/confirm")
async def rollback_confirm_route(
    run_id: uuid.UUID,
    rollback_id: uuid.UUID,
    body: ConfirmRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> JSONResponse:
    try:
        data = confirm_rollback(
            session,
            run_id,
            rollback_id,
            accept=body.accept,
            actor_user_id=_actor_user_id(request),
        )
    except ReviewError as exc:
        return JSONResponse(status_code=exc.status_code, content=_err(exc.message))
    await enqueue_job_with_context(pool, "run_workflow", run_id=str(run_id), resume=True)
    return JSONResponse(status_code=200, content=_ok(data))
```

- [ ] **Step 2: Mount the router in `main.py`**

In `backend/app/main.py`, next to the existing orchestrator router import (around line 35, `... import router as workflows_router`), add:

```python
from app.modules.orchestrator.graph_routes import router as workflows_graph_router
```

And next to `app.include_router(workflows_router)` (around line 103), add:

```python
app.include_router(workflows_graph_router)
```

- [ ] **Step 3: Verify the app imports with both routers mounted**

Run:
```bash
cd backend && python -c "from app.main import app; paths = sorted({r.path for r in app.routes}); print([p for p in paths if 'nodes' in p or 'rollbacks' in p])"
```
Expected (order may vary):
```
['/workflows/runs/{run_id}/nodes', '/workflows/runs/{run_id}/nodes/{node_key}/decision', '/workflows/runs/{run_id}/rollbacks/{rollback_id}/confirm']
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/orchestrator/graph_routes.py backend/app/main.py
git commit -m "feat(orchestrator): graph review/rollback endpoints mounted (3B)"
```

---

## Notes for the executor

- **`get_agent` import (Task 4):** the smoke import will surface the correct path if `from app.modules.agent_builder.agent_executor import ... get_agent` doesn't resolve. Fix only that import line.
- **JSONB via `json.dumps` in `extra_cols`:** this mirrors the shipped flat path (`orchestrate_run` writes `{"result": json.dumps(result)}` into JSONB `workflow_runs.result`). If the DB rejects a text→jsonb assignment at runtime, wrap the affected `extra_cols` value's SET clause with an explicit `CAST(... AS jsonb)` — but match the existing path first.
- **`decided_at`:** stamped via a follow-up `now()` UPDATE (SQL time), not a Python timestamp — consistent with the CAS helpers' `started_at`/`completed_at` handling and avoids clock-skew params.
- **Migration:** `alembic upgrade head` is intentionally NOT in a task step (project preference: don't auto-run build steps). Run it manually before exercising a graph run.

## Open questions

- **`_node_department` source of truth:** the plan reuses `get_agent(session, agent_id).department_id`. If a node should be able to target an agent outside its own department, that assumption needs revisiting (out of scope for 3B; the flat path makes the same assumption).
- **Override output validation:** stored verbatim (spec open-question resolved as "no validation for the demo"). Revisit if 3C needs a typed contract.
- **Orphan recovery for graph runs:** `resume_orphaned_runs` re-enqueues `status='running'` runs with `resume=True`; the new worker branch CASes `awaiting_human→running` on resume, so a graph run crash-orphaned *while already `running`* (mid-engine, not paused) is a no-op and won't self-heal. The flat path has the same class of limitation and 3B's spec is silent on it. Options if needed: make the graph resume CAS accept either `awaiting_human` or `running` as the from-state, or have `resume_orphaned_runs` special-case graph runs. Deferred — confirm acceptable for the demo.
