---
baseline_note: "down_revision chains off Story 3.1's workflows migration — re-verify `alembic heads` at execution time, not from this doc"
---

# Story 3.2: Workflow Run Lifecycle & State Machine

Status: ready-for-dev

## Story

As a **backend developer building the Orchestrator**,
I want **persisted state machines for `workflow_runs` and `tasks` with compare-and-set transitions**,
so that **Runs are resumable after restart and concurrent workers never double-pick the same Run or Task**.

This is Epic 3's second foundation story. It creates `workflow_runs` + `tasks` tables (RLS-protected), the arq job wiring that survives the tenant-context boundary (AD-10), and the compare-and-set pattern (AD-6) that Stories 3.3–3.6 all build their transitions on. **This story does NOT implement decomposition (3.3), dispatch/claim (3.4 — though it creates the `tasks` table `tasks` schema is finalized in 3.2, the claim loop is 3.4), or escalation (3.6).** It proves the state machine skeleton end-to-end with a no-op "Run runs, transitions to completed" happy path plus the concurrency guarantees.

## Acceptance Criteria

1. **AC1 — Tables exist with `status` enum columns**: `workflow_runs` and `tasks` tables exist, each with a `status` column constrained to its enum. (epics.md L878)
2. **AC2 — POST /workflows/{id}/runs creates a pending Run**: A User posts `POST /workflows/{id}/runs` with optional input payload → new `workflow_runs` row with `status: 'pending'`, `tenant_id`, `workflow_id`, `input`, `created_at`. Response `201` with the Run's `id`. (epics.md L879–880)
3. **AC3 — arq job enqueued with materialized tenant_id**: On Run creation, an arq job (`run_workflow`) is enqueued with `run_id` AND materialized `tenant_id` in the job kwargs (AD-10 — never rely on inherited context). (epics.md L881)
4. **AC4 — Worker CAS `pending→running`**: The arq worker dequeuing `run_workflow` issues `UPDATE workflow_runs SET status='running' WHERE id=? AND status='pending'` and checks `rowcount == 1`. (epics.md L882–883)
5. **AC5 — Zero-rowcount abandon**: If `rowcount == 0`, the worker abandons cleanly (another worker won the race) — no side effects, no exception storm, just a clean return + debug log. (epics.md L884, AD-6, Divergence 8)
6. **AC6 — Every transition is CAS**: Every `workflow_runs.status` transition uses the single `UPDATE ... WHERE id=? AND status=?` + `rowcount==1` check pattern — no SELECT-then-UPDATE anywhere in the module. (epics.md L885–886, AD-6)
7. **AC7 — Enum values exact**: `workflow_runs.status` ∈ `{pending, running, awaiting_human, completed, failed, timed_out}`; `tasks.status` ∈ `{pending, claimed, completed, failed}`. (epics.md L887–888)
8. **AC8 — Startup resume**: On worker startup, a poller queries `workflow_runs WHERE status='running'` (Runs orphaned by a crashed process) and safely resumes them — tenant context/RLS session var set from the row's own materialized `tenant_id` before any domain call. (epics.md L889–890, Divergence 1)
9. **AC9 — Audit on every transition**: Every state transition emits `audit.log(type="workflow_run.transition", input={from, to}, output={rowcount})`, using the REAL `run_id` (not the `crud_audit_ids` CRUD stopgap — this is a genuine Run step). (epics.md L891, AD-4)
10. **AC10 — Concurrency test proves no double-transition**: A test spins up two concurrent DB sessions/threads attempting `pending→running` on the SAME Run; asserts exactly one succeeds (`rowcount==1`) and the other observes `rowcount==0`. (epics.md L892, Divergence 8)

## Tasks / Subtasks

- [ ] **T1 — `workflow_runs` + `tasks` models** (AC: #1, #7)
  - [ ] T1.1 Add to `backend/app/modules/orchestrator/models.py`: `WorkflowRun(Base)`, `Task(Base)` — SQLAlchemy 2.x `Mapped[...]`
  - [ ] T1.2 `WorkflowRun` columns: `id` (UUID v7 PK), `tenant_id UUID NOT NULL` (FK `tenants.id`, CASCADE), `workflow_id UUID NOT NULL` (FK `workflows.id`, RESTRICT), `status String(32) NOT NULL default "pending"` (CHECK constraint or Postgres ENUM — prefer `CHECK (status IN (...))` for easier future value additions without an ALTER TYPE dance, consistent with `agents.status` String pattern in Epic 2), `input JSONB NOT NULL server_default="{}"`, `result JSONB NULLABLE`, `started_at`/`ended_at DateTime(timezone=True) NULLABLE`, `created_at DateTime(timezone=True) server_default=func.now()`
  - [ ] T1.3 `Task` columns: `id` (UUID v7 PK), `tenant_id UUID NOT NULL` (FK `tenants.id`, CASCADE — RLS needs it directly, don't rely on a join), `run_id UUID NOT NULL` (FK `workflow_runs.id`, CASCADE), `target_agent_id UUID NOT NULL` (FK `agents.id`, RESTRICT — cross-module FK to Epic-2's `agents` table is fine at the DB level, AD-1 only forbids importing internal Python models across modules, not FK references), `status String(32) NOT NULL default "pending"`, `schema_payload JSONB NOT NULL` (the full Task Schema object: task/input/output/expected/criteria per PRD §A1), `result JSONB NULLABLE` (populated by Story 3.4/3.5 — includes the feedback object), `claimed_at`/`completed_at DateTime(timezone=True) NULLABLE`, `created_at DateTime(timezone=True) server_default=func.now()`
  - [ ] T1.4 Indexes: `ix_workflow_runs_tenant_id`, `ix_workflow_runs_status` (for the startup poller's `WHERE status='running'` scan), `ix_tasks_tenant_id`, `ix_tasks_run_id`, `ix_tasks_status_target_agent` (composite, for Story 3.4's claim-poll query — add now since the shape is known, avoids a follow-up migration for an obvious index)
- [ ] **T2 — Alembic migration: create `workflow_runs` + `tasks` + RLS** (AC: #1, #7)
  - [ ] T2.1 **FIRST: `cd backend && uv run alembic heads`** — `down_revision` = Story 3.1's `create_workflows_rls` migration (verify by name/hash, do not assume)
  - [ ] T2.2 `upgrade()`: `op.create_table("workflow_runs", ...)`, `op.create_table("tasks", ...)`, all indexes from T1.4
  - [ ] T2.3 RLS DDL on BOTH tables — same pattern as Story 3.1 T2.3 (ENABLE + FORCE + tenant_isolation_policy)
  - [ ] T2.4 Grants: `GRANT SELECT, INSERT, UPDATE ON workflow_runs, tasks TO vaic_app;` — UPDATE is required for CAS transitions (unlike Epic-2's soft-delete-only tables, no DELETE revoke needed since there's no delete AC, but don't grant DELETE either — principle of least privilege)
  - [ ] T2.5 `downgrade()`: drop policies, disable RLS, drop tables (tasks before workflow_runs, FK order)
  - [ ] T2.6 Idempotency: `upgrade head` twice — no-op
- [ ] **T3 — CAS state-machine helper** (AC: #4, #5, #6, #10)
  - [ ] T3.1 In `backend/app/modules/orchestrator/service.py`, add `transition_run_status(session, run_id, *, from_status, to_status) -> bool`:
    ```python
    def transition_run_status(session, run_id, *, from_status, to_status) -> bool:
        result = session.execute(
            text(
                "UPDATE workflow_runs SET status=:to, "
                "started_at = CASE WHEN :to='running' THEN now() ELSE started_at END, "
                "ended_at = CASE WHEN :to IN ('completed','failed','timed_out') THEN now() ELSE ended_at END "
                "WHERE id=:id AND status=:from"
            ),
            {"to": to_status, "from": from_status, "id": str(run_id)},
        )
        session.commit()
        return result.rowcount == 1
    ```
    Caller MUST check the bool return and abandon on `False` — never assume success (AC5, AC10).
  - [ ] T3.2 Mirror for `tasks`: `transition_task_status(session, task_id, *, from_status, to_status, extra_cols: dict | None = None) -> bool` — same shape, `claimed_at`/`completed_at` set via the CASE pattern. This is what Story 3.4 will call for claim/complete — build it here so 3.4 doesn't re-derive the CAS pattern (single source of truth for the SQL string).
  - [ ] T3.3 Every call site of these two helpers MUST immediately emit the AC9 audit entry with `{from, to}` and `rowcount` — wrap in a small `_transition_and_audit(...)` helper to avoid duplicating the audit call at every transition site (Rule of Three already met: create/running, running/completed, running/failed).
- [ ] **T4 — Run creation endpoint + arq enqueue** (AC: #2, #3)
  - [ ] T4.1 `backend/app/modules/orchestrator/service.py`: `create_run(session, workflow_id, *, input=None) -> WorkflowRun` — INSERT `status='pending'`, `tenant_id` from context, `workflow_id` FK-validated (404 if not found/cross-tenant, RLS-backed)
  - [ ] T4.2 `backend/app/modules/orchestrator/routes.py`: `POST /workflows/{id}/runs` — creates the Run, THEN enqueues `arq_pool.enqueue_job("run_workflow", run_id=str(run.id), tenant_id=str(tenant_context.get()))` (AD-10 — materialize tenant_id explicitly, do not rely on the worker inheriting it)
  - [ ] T4.3 arq pool access: check if `app/core/arq.py` or similar exists from Epic 1 setup (grep for existing `arq` wiring before creating new plumbing — Rule of Three / reuse check)
- [ ] **T5 — arq worker function with tenant bootstrap** (AC: #4, #5, #8)
  - [ ] T5.1 New `backend/app/workers/orchestrator_worker.py` (or extend an existing `app/workers/` module if Epic 1 established one — check first): `async def run_workflow(ctx, *, run_id: str, tenant_id: str) -> None`
  - [ ] T5.2 FIRST STATEMENT: `tenant_context.set(uuid.UUID(tenant_id))` — per AD-10/Divergence-1, this is the ONE sanctioned place tenant_id is read from a job payload rather than middleware
  - [ ] T5.3 Open a DB session, `assume_app_role`, `set_tenant_session_var` (mirror `get_tenant_session` in `core/deps.py` — may need a non-generator worker variant, e.g. `get_worker_session(tenant_id)` context manager; add to `core/deps.py` if Rule of Three isn't met yet, else inline)
  - [ ] T5.4 Call `transition_run_status(session, run_id, from_status="pending", to_status="running")`; if `False`, log-and-return (AC5) — do NOT raise, this is an expected race outcome, not an error
  - [ ] T5.5 If `True`: for this story ONLY, transition straight to `completed` with an empty `result` (no decomposition yet — that's Story 3.3). This proves the skeleton end-to-end without scope-creeping into 3.3's territory. Emit the AC9 audit entries for both transitions.
  - [ ] T5.6 Register `run_workflow` in the arq `WorkerSettings.functions` list
- [ ] **T6 — Startup resume poller** (AC: #8)
  - [ ] T6.1 arq `WorkerSettings.on_startup` (or equivalent) hook: `SELECT id, tenant_id FROM workflow_runs WHERE status='running'` under `BYPASSRLS` (admin session — this is a cross-tenant sweep by design, mirrors AD-10's Schedule Trigger pattern)
  - [ ] T6.2 For each orphaned Run, re-enqueue `run_workflow(run_id, tenant_id)` — do NOT execute inline in the startup hook; re-use the same worker path so behavior is identical to a fresh dispatch
- [ ] **T7 — Tests** (AC: all)
  - [ ] T7.1 `backend/tests/integration/test_workflow_runs_rls.py` — RLS on both tables, raw SQL cross-tenant empty
  - [ ] T7.2 `backend/tests/integration/test_workflow_runs_api.py` — POST /runs 201 shape + `status='pending'` (AC2), arq enqueue call asserted (mock/spy the enqueue call, assert `tenant_id` kwarg present — AC3)
  - [ ] T7.3 `backend/tests/integration/test_workflow_run_state_machine.py` — CAS `pending→running` success (AC4); **concurrency test (AC10, load-bearing)**: use two separate DB sessions/threads (or `ThreadPoolExecutor`) both calling `transition_run_status(..., from_status="pending", to_status="running")` on the same `run_id`, assert exactly one returns `True` and the other `False`
  - [ ] T7.4 `test_workflow_run_resume.py` — seed a `status='running'` Run (simulating a crash), invoke the startup poller function directly, assert it re-enqueues (mock the arq pool)
  - [ ] T7.5 `test_workflow_run_audit.py` — assert `audit_trail` rows with `type="workflow_run.transition"` and correct `{from,to}` for each transition in the happy path
- [ ] **T8 — Green run + DoD evidence** (AC: all)
  - [ ] T8.1 `uv run alembic upgrade head`; `uv run pytest`; `uv run ruff check app tests alembic`
  - [ ] T8.2 Record test evidence + production code reference per AR-14 DoD, with EXPLICIT emphasis on the concurrency test (`file:line`) since it's the load-bearing proof for AD-6/Divergence-8/Divergence-4

## Dev Notes

### Scope Boundaries — CRITICAL

**Story 3.2 proves the state-machine skeleton only. Do NOT implement:**
- Orchestrator decomposition (reading the Workflow description, calling `LlmPort`, producing real Tasks) — **Story 3.3**. T5.5's "transition straight to completed" is an intentional stub for THIS story.
- Task claim/dispatch/execution loop — **Story 3.4**. The `tasks` table schema is finalized here (so 3.4 doesn't need its own migration), but no Task rows are created or claimed in this story.
- Escalation (`awaiting_human`) — **Story 3.6**. The enum value exists (AC7) but no code path produces it yet.
- Per-step feedback shape inside `tasks.result` — **Story 3.5**.

### Architecture Compliance

**AD-6 — compare-and-set (load-bearing, this story's core deliverable)**: every transition through `transition_run_status`/`transition_task_status` (T3.1/T3.2). NEVER a bare `session.query(...).update(...)` without the `WHERE status=?` guard and `rowcount` check. This is Divergence 4 and Divergence 8's fix, made concrete.

**AD-10 — tenant context across arq (load-bearing, T4.2/T5.2)**: `run_workflow`'s FIRST statement sets `tenant_context`. The FastAPI route enqueues with `tenant_id` explicitly materialized from `tenant_context.get()` at enqueue time — never assume the worker inherits anything. This is Divergence 1's fix.

**AD-4 — audit**: this is the FIRST story where Run-scoped work has a REAL `run_id`/`step_id` (not the `crud_audit_ids` CRUD stopgap from Epic 2/Story 3.1). Use `run_id = str(run.id)`, `step_id = str(uuid7())` per transition, `agent_id = "orchestrator"` (or a sentinel — no Agent is involved in a bare transition).

**AD-1 — Hexagonal**: `Task.target_agent_id` is a DB-level FK into Epic-2's `agents` table — this is fine (referential integrity is a DB concern, not a Python import). Do NOT import `app.modules.agent_builder.models.Agent` into `orchestrator/service.py` in this story (no Agent lookups happen yet — that starts in 3.3, and even then it should go through `agent_builder`'s public service function, not its model).

### Isolation-Level Note (Divergence 8)

Postgres default `READ COMMITTED`: a concurrent `UPDATE ... WHERE status='pending'` on the same row will BLOCK on the row lock until the first transaction commits, then see `rowcount=0` because the status changed. This means the CAS pattern is correct WITHOUT needing `SELECT ... FOR UPDATE` — the `UPDATE`'s own row lock provides the serialization. The concurrency test (T7.3) should assert this holds, not just trust the theory.

### File Structure Changes

```
backend/
├── alembic/
│   └── versions/
│       └── <rev>_create_workflow_runs_tasks_rls.py   # NEW — down_revision = Story 3.1's migration
├── app/
│   ├── core/
│   │   └── deps.py                                    # POSSIBLY UPDATED — worker session helper if needed
│   ├── modules/
│   │   └── orchestrator/
│   │       ├── models.py                              # UPDATED — WorkflowRun, Task
│   │       ├── service.py                              # UPDATED — CAS helpers, create_run
│   │       └── routes.py                                # UPDATED — POST /workflows/{id}/runs
│   └── workers/
│       └── orchestrator_worker.py                      # NEW (or extend existing) — run_workflow arq fn
└── tests/
    └── integration/
        ├── test_workflow_runs_rls.py                   # NEW
        ├── test_workflow_runs_api.py                   # NEW
        ├── test_workflow_run_state_machine.py           # NEW — includes AC10 concurrency test
        ├── test_workflow_run_resume.py                  # NEW
        └── test_workflow_run_audit.py                    # NEW
```

### Anti-Patterns to Avoid

1. **Never** `SELECT` then `UPDATE` for a state transition — always the single CAS `UPDATE ... WHERE id=? AND status=?`.
2. **Never** proceed past a transition call without checking its `rowcount`/bool return.
3. **Never** assume the arq worker has `tenant_context` set — always bootstrap from the job payload first.
4. **Never** run the startup-resume sweep under a tenant-scoped session — it MUST enumerate across tenants (`BYPASSRLS`), then per-Run set context before touching Run-specific data.
5. Do NOT implement decomposition logic here even partially — resist the urge to "just wire up LlmPort while I'm in here." That's Story 3.3's job; keep this story's diff focused on the state machine.
6. Do NOT skip `FORCE ROW LEVEL SECURITY` on either new table.

### Open Questions (carried to plan.md Open Questions)

- Confirm whether an existing `app/workers/` or `app/core/arq.py` module already exists from Epic 1 (Story 1.x may have set up the arq pool/WorkerSettings skeleton) — T4.3/T5.1 should reuse it, not duplicate. **Grep before creating.**

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.2 L870-892] ACs verbatim
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-6, AD-10, AD-4, AD-1]
- [Source: ARCHITECTURE-SPINE/divergence-1-...md] tenant contextvar arq boundary fix
- [Source: ARCHITECTURE-SPINE/divergence-4-...md] task-claim race fix (pattern reused here for Runs)
- [Source: ARCHITECTURE-SPINE/divergence-8-...md] orchestrator double-pick fix (this story's direct target)
- [Source: docs/prd.md#FR-9 retry/timeout assumptions, §A1 Task Schema, §A2 table sketch]
- [Source: backend/app/core/deps.py] session/RLS role helpers to reuse/extend

## Change Log

- 2026-07-18: Story 3.2 spec authored by planner agent. Status: ready-for-dev.
