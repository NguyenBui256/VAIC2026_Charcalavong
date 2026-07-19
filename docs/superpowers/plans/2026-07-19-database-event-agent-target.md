# Database Event → Agent Target Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a Mini-App Database row event (e.g. `row.created`) trigger **either a Workflow (existing) or a single Agent (new)**, reusing the existing outbox → 5s-cron → dispatch pipeline; and make the Actions page reachable + able to pick the target.

**Architecture:** Extend `action_bindings` with `target_type` + nullable `agent_id` (workflow_id becomes nullable, CHECK exactly-one). `dispatch_pending_events` branches per target: workflows keep the `create_run` + `run_workflow` path; agents enqueue a new `run_agent_task` ARQ job that runs `AgentExecutor.execute_task`, persists the result into `ActionEvent.result`, and sends a completion notification (Log + notify — no row write-back). Frontend adds a Workflow|Agent selector and re-enables the sidebar nav item.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 ORM, Alembic, ARQ (Redis), FastAPI, Postgres 18 (RLS); React 19 + TypeScript, TanStack Query, `@xyflow` unaffected, existing `vaic-*` design tokens + `lucide-react`.

## Global Constraints

- **No automated tests** — project override (`CLAUDE.md`): do not write or run tests. Verification is **manual** (alembic upgrade / running app).
- **Do not auto-run** typecheck / lint / build / format — only if the user asks.
- **No new dependencies.**
- **Reuse the existing pipeline** — do NOT rebuild events; extend `backend/app/modules/action/`.
- **Agent output = Log + notify** — store full result in `ActionEvent.result`; notify with a short summary. No write-back to the mini-app row.
- **Event types unchanged** — the `event_type` CHECK stays `row.created/updated/deleted`.
- Services stay transport-agnostic (take a `Session`, never enqueue). Only routes/workers enqueue (AD-1). Re-assert RLS (`_reassert`) after every commit inside worker-side service functions.
- New Alembic migration `down_revision = "ac20actions01"` (verified current head).
- Commit after each task. Trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: Data model — `target_type` + `agent_id` on `action_bindings`

**Files:**
- Modify: `backend/app/modules/action/models.py` (ActionBinding columns + CHECK)
- Create: `backend/alembic/versions/ad30agenttarget01_action_binding_agent_target.py`

**Interfaces:**
- Consumes: existing `agents` table (`agents.id`).
- Produces: `ActionBinding.target_type: str` (`'workflow'|'agent'`, default `'workflow'`), `ActionBinding.agent_id: uuid.UUID | None`; `ActionBinding.workflow_id` now `nullable`. Consumed by Tasks 2 & 3.

- [ ] **Step 1: Add columns + CHECK to the ORM model**

In `backend/app/modules/action/models.py`, add a target-types tuple near the top constants (after line 19):

```python
TARGET_TYPES = ("workflow", "agent")
```

Replace the `ActionBinding.__table_args__` block (currently the `UniqueConstraint` + one `CheckConstraint`) with:

```python
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_action_bindings_tenant_name"),
        CheckConstraint(
            "event_type IN ('row.created','row.updated','row.deleted')",
            name="ck_action_bindings_event_type",
        ),
        CheckConstraint(
            "(target_type = 'workflow' AND workflow_id IS NOT NULL AND agent_id IS NULL) "
            "OR (target_type = 'agent' AND agent_id IS NOT NULL AND workflow_id IS NULL)",
            name="ck_action_bindings_target",
        ),
    )
```

Change the `workflow_id` column to be nullable, and add `target_type` + `agent_id`. Replace the existing `workflow_id` mapped_column with these three (keep column order tidy — `target_type` before, `agent_id` after):

```python
    target_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="workflow", server_default="workflow"
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True
    )
```

- [ ] **Step 2: Write the Alembic migration**

Create `backend/alembic/versions/ad30agenttarget01_action_binding_agent_target.py`:

```python
"""action_bindings: add target_type + agent_id; workflow_id becomes nullable.

Lets a binding target EITHER a workflow (existing) OR a single agent (new).
Backfills existing rows to target_type='workflow'. CHECK enforces exactly one
target matching the discriminator. No new RLS policy needed (column adds on an
already-RLS table).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ad30agenttarget01"
down_revision: str | Sequence[str] | None = "ac20actions01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "action_bindings",
        sa.Column("target_type", sa.String(16), nullable=False, server_default="workflow"),
    )
    op.add_column(
        "action_bindings",
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    # Existing rows all targeted a workflow — backfill is implicit via the
    # server_default; make workflow_id nullable now that agent_id can carry it.
    op.alter_column("action_bindings", "workflow_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.create_check_constraint(
        "ck_action_bindings_target",
        "action_bindings",
        "(target_type = 'workflow' AND workflow_id IS NOT NULL AND agent_id IS NULL) "
        "OR (target_type = 'agent' AND agent_id IS NOT NULL AND workflow_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_action_bindings_target", "action_bindings", type_="check")
    op.alter_column("action_bindings", "workflow_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_column("action_bindings", "agent_id")
    op.drop_column("action_bindings", "target_type")
```

- [ ] **Step 3: Manual verify — migration applies**

Run (backend dir): `uv run alembic upgrade head`
Expected: completes with no error; `uv run alembic current` shows `ad30agenttarget01 (head)`. In psql: `\d action_bindings` shows `target_type`, nullable `workflow_id`, `agent_id`, and constraint `ck_action_bindings_target`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/action/models.py backend/alembic/versions/ad30agenttarget01_action_binding_agent_target.py
git commit -m "feat(action): action_bindings target_type + agent_id (workflow_id nullable)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Service validation + serialization + HTTP routes

**Files:**
- Modify: `backend/app/modules/action/service.py` (create/update/serialize + `_validate_target`)
- Modify: `backend/app/modules/action/routes.py` (request models + handler calls)

**Interfaces:**
- Consumes: `ActionBinding` fields from Task 1; `TARGET_TYPES`.
- Produces:
  - `create_binding(session, *, principal, name, database_id, event_type, target_type, workflow_id, agent_id, notify_user_ids, is_active=True) -> ActionBinding`
  - `update_binding(session, binding_id, *, name, database_id, event_type, target_type, workflow_id, agent_id, notify_user_ids, is_active) -> ActionBinding`
  - `serialize_binding(b)` returns dict incl. `"target_type"`, `"workflow_id" (str|None)`, `"agent_id" (str|None)`.

- [ ] **Step 1: Update the model import + add `_validate_target` in service.py**

In `backend/app/modules/action/service.py`, change the models import (line 19) to include `TARGET_TYPES`:

```python
from app.modules.action.models import EVENT_TYPES, TARGET_TYPES, ActionBinding, ActionEvent
```

Add this validator next to `_validate_event_type` (after it, ~line 100):

```python
def _validate_target(
    target_type: str, workflow_id: uuid.UUID | None, agent_id: uuid.UUID | None
) -> None:
    if target_type not in TARGET_TYPES:
        raise ConflictError(f"target_type must be one of {TARGET_TYPES}")
    if target_type == "workflow" and (workflow_id is None or agent_id is not None):
        raise ConflictError("workflow target requires workflow_id and no agent_id")
    if target_type == "agent" and (agent_id is None or workflow_id is not None):
        raise ConflictError("agent target requires agent_id and no workflow_id")
```

- [ ] **Step 2: Update `create_binding`**

Replace the whole `create_binding` function with:

```python
def create_binding(
    session: Session, *, principal: MiniAppPrincipal, name: str,
    database_id: uuid.UUID, event_type: str, target_type: str,
    workflow_id: uuid.UUID | None, agent_id: uuid.UUID | None,
    notify_user_ids: list[uuid.UUID], is_active: bool = True,
) -> ActionBinding:
    _validate_event_type(event_type)
    _validate_target(target_type, workflow_id, agent_id)
    if _name_taken(session, principal.tenant_id, name):
        raise ConflictError(f"an action named '{name}' already exists")
    b = ActionBinding(
        tenant_id=principal.tenant_id, owner_id=principal.user_id, name=name,
        database_id=database_id, event_type=event_type, target_type=target_type,
        workflow_id=workflow_id, agent_id=agent_id,
        notify_user_ids=notify_user_ids, is_active=is_active,
    )
    session.add(b)
    session.commit()
    session.refresh(b)
    return b
```

- [ ] **Step 3: Update `update_binding`**

Replace the whole `update_binding` function with (recomputes effective target and re-validates whenever any target field changes):

```python
def update_binding(
    session: Session, binding_id: uuid.UUID, *,
    name: str | None, database_id: uuid.UUID | None, event_type: str | None,
    target_type: str | None, workflow_id: uuid.UUID | None, agent_id: uuid.UUID | None,
    notify_user_ids: list[uuid.UUID] | None, is_active: bool | None,
) -> ActionBinding:
    b = get_binding(session, binding_id)
    if name is not None and name != b.name:
        if _name_taken(session, b.tenant_id, name):
            raise ConflictError(f"an action named '{name}' already exists")
        b.name = name
    if database_id is not None:
        b.database_id = database_id
    if event_type is not None:
        _validate_event_type(event_type)
        b.event_type = event_type

    # Resolve the effective target from the patch, then validate + apply
    # atomically so we never leave both/neither target id set.
    if target_type is not None or workflow_id is not None or agent_id is not None:
        new_type = target_type if target_type is not None else b.target_type
        if new_type == "workflow":
            new_wf = workflow_id if workflow_id is not None else b.workflow_id
            new_ag = None
        else:  # "agent"
            new_ag = agent_id if agent_id is not None else b.agent_id
            new_wf = None
        _validate_target(new_type, new_wf, new_ag)
        b.target_type = new_type
        b.workflow_id = new_wf
        b.agent_id = new_ag

    if notify_user_ids is not None:
        b.notify_user_ids = notify_user_ids
    if is_active is not None:
        b.is_active = is_active
    b.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(b)
    return b
```

- [ ] **Step 4: Update `serialize_binding`**

Replace the `serialize_binding` function with:

```python
def serialize_binding(b: ActionBinding) -> dict[str, Any]:
    return {
        "id": str(b.id), "name": b.name, "database_id": str(b.database_id),
        "event_type": b.event_type, "target_type": b.target_type,
        "workflow_id": str(b.workflow_id) if b.workflow_id else None,
        "agent_id": str(b.agent_id) if b.agent_id else None,
        "notify_user_ids": [str(u) for u in (b.notify_user_ids or [])],
        "is_active": b.is_active, "owner_id": str(b.owner_id),
        "created_at": b.created_at.isoformat(), "updated_at": b.updated_at.isoformat(),
    }
```

- [ ] **Step 5: Update the request models + handlers in routes.py**

In `backend/app/modules/action/routes.py`, replace `CreateActionRequest` and `UpdateActionRequest`:

```python
class CreateActionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    database_id: uuid.UUID
    event_type: str = "row.created"
    target_type: str = "workflow"
    workflow_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    notify_user_ids: list[uuid.UUID] = Field(default_factory=list)
    is_active: bool = True


class UpdateActionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    database_id: uuid.UUID | None = None
    event_type: str | None = None
    target_type: str | None = None
    workflow_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    notify_user_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None
```

Replace the `svc.create_binding(...)` call inside `create_action_route`:

```python
    b = svc.create_binding(
        session, principal=_principal(request), name=body.name,
        database_id=body.database_id, event_type=body.event_type,
        target_type=body.target_type, workflow_id=body.workflow_id, agent_id=body.agent_id,
        notify_user_ids=body.notify_user_ids, is_active=body.is_active,
    )
```

Replace the `svc.update_binding(...)` call inside `update_action_route`:

```python
    b = svc.update_binding(
        session, binding_id, name=body.name, database_id=body.database_id,
        event_type=body.event_type, target_type=body.target_type,
        workflow_id=body.workflow_id, agent_id=body.agent_id,
        notify_user_ids=body.notify_user_ids, is_active=body.is_active,
    )
```

- [ ] **Step 6: Manual verify — API accepts an agent binding**

Restart the backend (`uv run uvicorn app.main:app --reload --port 8000`). With an auth token, POST `/actions` with `{"name":"t1","database_id":"<db>","event_type":"row.created","target_type":"agent","agent_id":"<agent>"}` → 201 and the returned JSON has `target_type:"agent"`, `agent_id` set, `workflow_id:null`. POST with `target_type:"agent"` but no `agent_id` → 409 "agent target requires agent_id…". GET `/actions` still returns existing workflow bindings with `target_type:"workflow"`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/action/service.py backend/app/modules/action/routes.py
git commit -m "feat(action): binding CRUD accepts agent target + exactly-one validation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Dispatch branch + `run_agent_task` job

**Files:**
- Modify: `backend/app/modules/action/service.py` (`DispatchOutcome`, `AgentTaskSpec`, dispatch branch, `claim_agent_task`, `finalize_agent_event`)
- Modify: `backend/app/modules/action/worker.py` (enqueue branch + `run_agent_task` job)
- Modify: `backend/scripts/run_worker.py` (register `run_agent_task`)

**Interfaces:**
- Consumes: `create_run` (orchestrator), `AgentExecutor` (`agent_builder.agent_executor`), `get_agent` (`agent_builder.service`), `create_notification` (`notification.service`), `ActionEvent`/`ActionBinding` from Task 1.
- Produces:
  - `@dataclass DispatchOutcome(run_ids: list[str], agent_tasks: list[dict[str,str]])` — each agent task `{"event_id","binding_id"}`.
  - `dispatch_pending_events(session, tenant_id) -> DispatchOutcome` (return type CHANGED from `list[str]`).
  - `@dataclass AgentTaskSpec(agent_id: uuid.UUID, department_id: uuid.UUID, payload: dict)`.
  - `claim_agent_task(session, tenant_id, *, event_id: str, binding_id: str) -> AgentTaskSpec` (sync).
  - `finalize_agent_event(session, tenant_id, *, event_id, binding_id, output, confidence, rationale, success, error)` (sync).
  - `run_agent_task(ctx, *, event_id: str, binding_id: str)` ARQ job.

- [ ] **Step 1: Add dataclasses + imports in service.py**

At the top of `backend/app/modules/action/service.py`, add to the stdlib imports:

```python
from dataclasses import dataclass, field
```

Add these dataclasses just after the `TERMINAL_RUN_STATUSES` constant (~line 118):

```python
@dataclass
class DispatchOutcome:
    """Result of one dispatch pass: workflow runs to enqueue + agent tasks to run."""
    run_ids: list[str] = field(default_factory=list)
    agent_tasks: list[dict[str, str]] = field(default_factory=list)  # {"event_id","binding_id"}


@dataclass
class AgentTaskSpec:
    """Everything run_agent_task needs to invoke one agent for one event."""
    agent_id: uuid.UUID
    department_id: uuid.UUID
    payload: dict[str, Any]
```

- [ ] **Step 2: Branch `dispatch_pending_events` on `target_type`**

In `dispatch_pending_events`, change the return type annotation to `-> DispatchOutcome` and initialise an outcome instead of `run_ids`. Replace the line:

```python
    run_ids: list[str] = []
```

with:

```python
    outcome = DispatchOutcome()
```

Inside the per-binding loop, replace the block that snapshots + calls `create_run` (from `binding_id = str(b.id)` down through `dispatched.append({...})`) with a target-type branch:

```python
        dispatched: list[dict[str, Any]] = []
        first_run_id: str | None = None
        for b in bindings:
            binding_id = str(b.id)
            binding_name = b.name
            recipients = list(b.notify_user_ids or []) or [b.owner_id]

            if b.target_type == "agent":
                # Agent target: no WorkflowRun. Record the dispatch, notify, and
                # hand the (event, binding) to run_agent_task via the outcome.
                outcome.agent_tasks.append({"event_id": str(event_id), "binding_id": binding_id})
                _reassert(session, tenant_id)
                notif_ids: list[str] = []
                for uid in recipients:
                    n = create_notification(
                        session, tenant_id=tenant_id, user_id=uid,
                        category="action.dispatched",
                        title=f"New submission received — {binding_name}",
                        body="A new record started background agent processing.",
                        ref={"agent_id": str(b.agent_id), "app_id": app_id,
                             "action_id": binding_id, "row_id": row_id},
                    )
                    notif_ids.append(str(n.id))
                session.commit()
                dispatched.append({"action_id": binding_id, "kind": "agent",
                                   "agent_id": str(b.agent_id), "notification_ids": notif_ids})
                continue

            # Workflow target (unchanged behaviour).
            workflow_id = b.workflow_id
            _reassert(session, tenant_id)
            run = create_run(
                session, workflow_id, role="builder",
                input={
                    "source": "action", "action_id": binding_id, "app_id": app_id,
                    "row_id": row_id, "event_type": event_type, "data": data,
                },
            )
            run_id = str(run.id)
            outcome.run_ids.append(run_id)
            if first_run_id is None:
                first_run_id = run_id

            _reassert(session, tenant_id)
            notif_ids = []
            for uid in recipients:
                n = create_notification(
                    session, tenant_id=tenant_id, user_id=uid,
                    category="action.dispatched",
                    title=f"New submission received — {binding_name}",
                    body="A new record started background workflow processing.",
                    ref={"workflow_run_id": run_id, "app_id": app_id,
                         "action_id": binding_id, "row_id": row_id},
                )
                notif_ids.append(str(n.id))
            session.commit()
            dispatched.append({"action_id": binding_id, "run_id": run_id, "notification_ids": notif_ids})
```

Then replace the `_finish_event(...)` call at the end of the loop (which used `dispatched[0]["run_id"]`) with one that uses `first_run_id` (agent-only events have no run):

```python
        _reassert(session, tenant_id)
        ev = session.get(ActionEvent, event_id)
        if ev is not None:
            _finish_event(
                session, ev, status="dispatched",
                result={"dispatched": dispatched},
                workflow_run_id=uuid.UUID(first_run_id) if first_run_id else None,
            )
```

Finally replace the function's `return run_ids` with:

```python
    return outcome
```

- [ ] **Step 3: Add `claim_agent_task` + `finalize_agent_event` to service.py**

Append at the end of `backend/app/modules/action/service.py`:

```python
def claim_agent_task(
    session: Session, tenant_id: uuid.UUID, *, event_id: str, binding_id: str
) -> AgentTaskSpec:
    """Build the AgentExecutor payload for one (event, agent-binding). Sync, no
    commit — leaves the RLS role/tenant var in place for execute_task's reads."""
    from app.modules.agent_builder.service import get_agent

    _reassert(session, tenant_id)
    ev = session.get(ActionEvent, uuid.UUID(event_id))
    b = session.get(ActionBinding, uuid.UUID(binding_id))
    if ev is None or b is None or b.agent_id is None:
        raise NotFoundError(f"agent task {event_id}/{binding_id} not resolvable")
    agent = get_agent(session, b.agent_id)
    data = (ev.payload or {}).get("data", {})
    payload = {
        "task": {"summary": f"Process {ev.event_type} on mini-app {ev.app_id}"},
        "input": {
            "source": "action", "action_id": binding_id, "app_id": str(ev.app_id),
            "row_id": str(ev.row_id) if ev.row_id else None,
            "event_type": ev.event_type, "data": data,
        },
        "expected": [],
        "criteria": {},  # no forced tool — execute_task is no-tool-safe
    }
    return AgentTaskSpec(agent_id=agent.id, department_id=agent.department_id, payload=payload)


def finalize_agent_event(
    session: Session, tenant_id: uuid.UUID, *, event_id: str, binding_id: str,
    output: dict[str, Any], confidence: float, rationale: str, success: bool, error: str,
) -> None:
    """Persist one agent result onto the event (appended under result.agent_results),
    notify recipients, and mark the event completed. Sync; commits."""
    from app.modules.notification.service import create_notification
    from sqlalchemy.orm.attributes import flag_modified

    _reassert(session, tenant_id)
    ev = session.get(ActionEvent, uuid.UUID(event_id))
    b = session.get(ActionBinding, uuid.UUID(binding_id))
    if ev is None:
        return

    entry = {
        "action_id": binding_id, "success": success, "confidence": confidence,
        "rationale": rationale, "output": output, "error": error,
    }
    result = dict(ev.result or {})
    result.setdefault("agent_results", []).append(entry)
    ev.result = result
    flag_modified(ev, "result")
    if not success:
        ev.status = "failed"
        ev.error = error or "agent task failed"
    ev.completed_notified = True
    ev.processed_at = datetime.now(UTC)
    session.commit()

    if b is not None:
        _reassert(session, tenant_id)
        recipients = list(b.notify_user_ids or []) or [b.owner_id]
        summary = (rationale or str(output))[:200]
        title = (f"Agent finished — {b.name}" if success else f"Agent failed — {b.name}")
        for uid in recipients:
            create_notification(
                session, tenant_id=tenant_id, user_id=uid,
                category="action.completed",
                title=title,
                body=summary or "Background agent processing finished.",
                ref={"agent_id": str(b.agent_id), "app_id": str(ev.app_id), "action_id": binding_id},
            )
        session.commit()
```

- [ ] **Step 4: Update the worker — enqueue branch + `run_agent_task`**

In `backend/app/modules/action/worker.py`, update the import (line 25):

```python
from app.modules.action.service import (
    claim_agent_task,
    dispatch_pending_events,
    finalize_agent_event,
    notify_completed_events,
)
```

Add `run_agent_task` to `__all__` (line 29):

```python
__all__ = [
    "dispatch_action_events_fanout",
    "process_tenant_action_events",
    "run_agent_task",
    "action_cron_jobs",
]
```

Replace the body of `process_tenant_action_events` from the `run_ids: list[str] = ...` line through the `run_workflow` enqueue loop with an outcome-based version:

```python
    # Sync DB work (create runs + notifications) on the executor thread.
    outcome = await loop.run_in_executor(
        None, dispatch_pending_events, session, tenant_id
    )

    # Enqueue each created workflow run + each agent task.
    if pool is not None:
        for run_id in outcome.run_ids:
            await enqueue_job_with_context(pool, "run_workflow", run_id=run_id)
        for task in outcome.agent_tasks:
            await enqueue_job_with_context(
                pool, "run_agent_task",
                event_id=task["event_id"], binding_id=task["binding_id"],
            )
```

Add the new job function after `process_tenant_action_events` (before `action_cron_jobs`):

```python
@tenant_aware_job
async def run_agent_task(ctx: dict[str, Any], *, event_id: str, binding_id: str) -> None:
    """Run one Specialist Agent for one dispatched action_event, then log + notify."""
    from app.modules.agent_builder.agent_executor import AgentExecutor

    session = ctx["session"]
    tenant_id = tenant_context.get()
    if tenant_id is None:
        raise RuntimeError("run_agent_task: tenant_context unset at entry")
    loop = asyncio.get_running_loop()

    spec = await loop.run_in_executor(
        None, lambda: claim_agent_task(session, tenant_id, event_id=event_id, binding_id=binding_id)
    )

    try:
        result = await AgentExecutor(session).execute_task(
            spec.agent_id, spec.payload, tenant_id=tenant_id, department_id=spec.department_id
        )
        output, confidence, rationale = result.output, result.confidence, result.rationale
        success, error = result.success, result.error
    except Exception as exc:  # noqa: BLE001 — record + notify failure, never crash the job
        logger.exception("run_agent_task failed for event %s", event_id)
        output, confidence, rationale, success, error = {}, 0.0, "", False, str(exc)

    await loop.run_in_executor(
        None,
        lambda: finalize_agent_event(
            session, tenant_id, event_id=event_id, binding_id=binding_id,
            output=output, confidence=confidence, rationale=rationale,
            success=success, error=error,
        ),
    )
```

Note: `asyncio`, `tenant_context`, `tenant_aware_job`, `enqueue_job_with_context` are already imported at the top of `worker.py`.

- [ ] **Step 5: Register `run_agent_task` on the worker process**

In `backend/scripts/run_worker.py`, update the action import (line 25):

```python
from app.modules.action.worker import (  # noqa: E402
    action_cron_jobs,
    process_tenant_action_events,
    run_agent_task,
)
```

Add it to the merged functions list (the `replace(...)` call, ~line 43):

```python
    functions=[*worker_config.functions, build_mini_app, process_tenant_action_events, run_agent_task],
```

- [ ] **Step 6: Manual verify — INSERT → agent runs end to end**

Prereqs: an Agent exists; a Mini-App bound to a Database exists; via the Actions API (or Task 5 UI) create a binding `target_type='agent'`, `event_type='row.created'`, that database, that agent. Start backend + worker (`uv run python scripts/run_worker.py`). Insert a row into a mini-app on that database (mini-app UI or `POST /mini-apps/{id}/rows`). Within ~5s: worker logs show `process_tenant_action_events` then `run_agent_task`. Verify in DB: the `action_events` row for that insert has `status='dispatched'` (or `failed`), `completed_notified=true`, and `result->'agent_results'` contains one entry with the agent's `output`/`rationale`. Two `notifications` rows exist for the owner: `action.dispatched` and `action.completed`. Confirm an existing **workflow** binding still dispatches as before (create one and insert a row → a `workflow_run` is created + `run_workflow` runs).

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/action/service.py backend/app/modules/action/worker.py backend/scripts/run_worker.py
git commit -m "feat(action): dispatch agent-target events via new run_agent_task job

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Frontend types + hooks

**Files:**
- Modify: `frontend/src/lib/actionsApi.ts` (types)
- Modify: `frontend/src/hooks/useActions.ts` (no new hook needed; `useAgents` is imported directly in Task 5)

**Interfaces:**
- Produces: `ActionBinding` + `CreateActionInput` gain `target_type: "workflow" | "agent"` and `agent_id: string | null`; `workflow_id: string | null`. Consumed by Task 5.

- [ ] **Step 1: Extend the API types**

In `frontend/src/lib/actionsApi.ts`, add a target-type union and update the two interfaces. Replace the `ActionBinding` and `CreateActionInput` interfaces with:

```ts
export type ActionTargetType = "workflow" | "agent";

export interface ActionBinding {
  id: string;
  name: string;
  database_id: string;
  event_type: ActionEventType;
  target_type: ActionTargetType;
  workflow_id: string | null;
  agent_id: string | null;
  notify_user_ids: string[];
  is_active: boolean;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface CreateActionInput {
  name: string;
  database_id: string;
  event_type: ActionEventType;
  target_type: ActionTargetType;
  workflow_id?: string | null;
  agent_id?: string | null;
  notify_user_ids?: string[];
  is_active?: boolean;
}
```

(`UpdateActionInput = Partial<CreateActionInput>` and the `listActions`/`createAction`/… functions are unchanged.)

- [ ] **Step 2: Manual verify (type-level)**

Open `actionsApi.ts` — no red squiggles. `useActions.ts` still compiles (it re-exports the types; no change needed there). No runtime step.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/actionsApi.ts
git commit -m "feat(action): frontend types for agent target on action bindings

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Actions page target selector + re-enable nav

**Files:**
- Modify: `frontend/src/routes/actions/ActionsPage.tsx` (target-type toggle + agent dropdown + table column + submit)
- Modify: `frontend/src/components/Sidebar.tsx` (uncomment the Actions nav item)

**Interfaces:**
- Consumes: `ActionTargetType`, updated `ActionBinding`/`CreateActionInput` (Task 4); `useAgents` (`../../hooks/useAgents`).
- Produces: user-facing CRUD that can create/edit an agent-target binding; Actions reachable from the sidebar.

- [ ] **Step 1: Re-enable the sidebar nav item**

In `frontend/src/components/Sidebar.tsx`, uncomment the `Zap` import (line 17) → `  Zap,`. Then replace the commented Actions nav line (lines 44–45) with the active entry:

```tsx
  { to: "/actions", label: "Actions", icon: Zap },
```

(The CommandPalette entry in `navigationCommands.ts` is already active — no change there.)

- [ ] **Step 2: Add agents + target fields to the Actions page state**

In `frontend/src/routes/actions/ActionsPage.tsx`:

Add imports (after the existing hook imports):

```tsx
import { useAgents } from "../../hooks/useAgents";
import type { ActionBinding, ActionEventType, ActionTargetType, CreateActionInput } from "../../lib/actionsApi";
```

(Replace the existing `import type { ActionBinding, ActionEventType, CreateActionInput } ...` line — do not duplicate it.)

Extend `DraftState` and `EMPTY_DRAFT`:

```tsx
interface DraftState {
  id: string | null;
  name: string;
  database_id: string;
  event_type: ActionEventType;
  target_type: ActionTargetType;
  workflow_id: string;
  agent_id: string;
  notify_user_ids: string; // comma-separated in the form
  is_active: boolean;
}

const EMPTY_DRAFT: DraftState = {
  id: null, name: "", database_id: "", event_type: "row.created",
  target_type: "workflow", workflow_id: "", agent_id: "",
  notify_user_ids: "", is_active: true,
};
```

Inside `ActionsPage`, add the agents query next to the other data hooks (after `const { data: workflowsData } = useWorkflows({});`):

```tsx
  const { data: agentsData } = useAgents({});
```

And add name resolvers next to `wfName` (after line ~51):

```tsx
  const agents = agentsData ?? [];
  const agName = (id: string) => agents.find((a) => a.id === id)?.name ?? id;
```

- [ ] **Step 3: Prefill target fields on edit**

Replace `startEdit` with a version that carries the target:

```tsx
  function startEdit(a: ActionBinding) {
    setDraft({
      id: a.id, name: a.name, database_id: a.database_id, event_type: a.event_type,
      target_type: a.target_type,
      workflow_id: a.workflow_id ?? "", agent_id: a.agent_id ?? "",
      notify_user_ids: a.notify_user_ids.join(", "), is_active: a.is_active,
    });
  }
```

- [ ] **Step 4: Validate + build the target-aware payload on submit**

Replace the target validation + `input` construction inside `handleSubmit` (the `if (!draft.workflow_id) {...}` guard and the `const input: CreateActionInput = {...}` block) with:

```tsx
    if (draft.target_type === "workflow" && !draft.workflow_id) { show("Pick a Workflow", "error"); return; }
    if (draft.target_type === "agent" && !draft.agent_id) { show("Pick an Agent", "error"); return; }
    const input: CreateActionInput = {
      name: draft.name.trim(),
      database_id: draft.database_id,
      event_type: draft.event_type,
      target_type: draft.target_type,
      workflow_id: draft.target_type === "workflow" ? draft.workflow_id : null,
      agent_id: draft.target_type === "agent" ? draft.agent_id : null,
      notify_user_ids: draft.notify_user_ids.split(",").map((s) => s.trim()).filter(Boolean),
      is_active: draft.is_active,
    };
```

- [ ] **Step 5: Show the target in the table**

Replace the `workflow` column in the `columns` array with a target column:

```tsx
    {
      key: "target", header: "Target",
      render: (a) =>
        a.target_type === "agent"
          ? `Agent: ${agName(a.agent_id ?? "")}`
          : `Workflow: ${wfName(a.workflow_id ?? "")}`,
    },
```

- [ ] **Step 6: Add the Target-type selector + agent dropdown to the form**

In the form JSX, replace the whole Workflow `<div className="vaic-form-field">…</div>` block (the one with `id="vaic-action-workflow"`) with a target-type selector plus a conditional Workflow/Agent dropdown:

```tsx
            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-action-target-type">Target type</label>
              <select
                id="vaic-action-target-type" className="vaic-form-input vaic-focusable"
                value={draft.target_type}
                onChange={(e) => setDraft({ ...draft, target_type: e.target.value as ActionTargetType })}
              >
                <option value="workflow">Workflow</option>
                <option value="agent">Agent</option>
              </select>
            </div>

            {draft.target_type === "workflow" ? (
              <div className="vaic-form-field">
                <label className="vaic-form-label" htmlFor="vaic-action-workflow">Workflow</label>
                <select
                  id="vaic-action-workflow" className="vaic-form-input vaic-focusable"
                  value={draft.workflow_id} onChange={(e) => setDraft({ ...draft, workflow_id: e.target.value })}
                >
                  <option value="">— Select a workflow —</option>
                  {workflows.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                </select>
              </div>
            ) : (
              <div className="vaic-form-field">
                <label className="vaic-form-label" htmlFor="vaic-action-agent">Agent</label>
                <select
                  id="vaic-action-agent" className="vaic-form-input vaic-focusable"
                  value={draft.agent_id} onChange={(e) => setDraft({ ...draft, agent_id: e.target.value })}
                >
                  <option value="">— Select an agent —</option>
                  {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
            )}
```

- [ ] **Step 7: Manual verify — UI**

Run the frontend the way the project normally does. Sidebar now shows **Actions** (Zap icon) → opens the page. Click **New action**: the form shows a **Target type** dropdown; switching to **Agent** swaps the Workflow select for an **Agent** select listing existing agents. Create an agent-target action → appears in the table with `Target: Agent: <name>`. Edit it → fields prefilled, target preserved. Create a workflow-target action → `Target: Workflow: <name>`. Submitting Agent with no agent picked → toast "Pick an Agent". No console errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/routes/actions/ActionsPage.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat(action): Actions UI target selector (workflow|agent) + re-enable nav

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §A data model (target_type + nullable workflow_id + agent_id + CHECK, migration) → Task 1. ✓
- §B service + API (validation, serialization, request models) → Task 2. ✓
- §C dispatch branch + `run_agent_task` (log + notify, worker registration, department from agent) → Task 3. ✓
- §D frontend (re-enable nav, api/types, form target selector, table column) → Tasks 4 + 5. ✓
- §E data flow (agent path end to end) → verified in Task 3 Step 6 + Task 5 Step 7. ✓
- Out-of-scope items (write-back, new event types, results viewer, retry) → not implemented, as specified. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:**
- `target_type`/`agent_id`/nullable `workflow_id` defined in Task 1 (ORM) + migration; consumed identically in Task 2 (service/routes), Task 4 (TS types), Task 5 (UI). ✓
- `DispatchOutcome` (Task 3 Step 1) is the return of `dispatch_pending_events` (Step 2) and consumed in the worker (Step 4) as `outcome.run_ids` / `outcome.agent_tasks`. ✓
- `AgentTaskSpec` fields (`agent_id`, `department_id`, `payload`) produced by `claim_agent_task` (Step 3), consumed in `run_agent_task` (Step 4) as `spec.agent_id`/`spec.department_id`/`spec.payload`. ✓
- `finalize_agent_event` kwargs (Step 3) match the call in `run_agent_task` (Step 4). ✓
- `execute_task` signature (`agent_id, task_payload, *, tenant_id, department_id`) matches the real `AgentExecutor.execute_task`. ✓
- `TaskExecutionResult` fields used (`output`, `confidence`, `rationale`, `success`, `error`) match the dataclass. ✓
- `ActionTargetType` (Task 4) used in Task 5 imports + casts. ✓
- `useAgents({})` returns `{ data: Agent[] }` with `id`/`name` (verified). ✓

## Notes / accepted edges

- **Multiple bindings on one event:** an event may match several bindings (e.g. one workflow + one agent). Each is dispatched; workflow runs are tracked in `result.dispatched[]` + `workflow_run_id` (first run), agent results in `result.agent_results[]`. For a mixed event, both the workflow completion sweep and `run_agent_task` may set `completed_notified` — completion notifications from both paths are expected and acceptable.
- **Crashed `run_agent_task`:** the job records failure in its own `except` and calls `finalize_agent_event` with `success=False`, so the event reaches `status='failed'` + `completed_notified=true`. A hard process kill before finalize leaves the event `dispatched`/`completed_notified=false` (never re-run — dispatch only processes `pending`); acceptable for the demo (no retry, per spec).
- **`department_id`:** taken from `agent.department_id`. If it mismatches the app's department, KB retrieval may return no passages — `execute_task` is KB-optional, so the agent still runs. No stricter requirement per spec.
```