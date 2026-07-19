# Design: Bind a Database Event to an Agent (Events → Agent target)

**Date:** 2026-07-19
**Status:** Approved (design), pending implementation plan
**Scope:** Extend the existing Action/Event system so a Mini-App Database row event can trigger **either a Workflow (existing) or a single Agent (new)**, reusing the existing outbox → cron → dispatch pipeline. Make the Actions UI visible and let users pick the target.

---

## Background — what already exists

The "Events" concept is already ~90% built in `backend/app/modules/action/` (singular). The full pipeline works today for the **workflow** target:

```
mini_app.service.create_row()
  → emit_action_event()                      # inserts a `pending` ActionEvent (outbox)
  → cron action_events_fanout (every 5s)     # BYPASSRLS: tenants with pending/uncompleted work
  → process_tenant_action_events (per tenant, @tenant_aware_job)
      → dispatch_pending_events()            # resolve ActionBinding(s), create_run(), return run_ids
      → enqueue run_workflow(run_id)         # per created run
      → notify_completed_events()            # completion sweep on terminal WorkflowRun status
```

- `emit_action_event` sites exist for `row.created`, `row.updated`, `row.deleted` (`mini_app/service.py:49,211,219`).
- Frontend **Actions** page (`frontend/src/routes/actions/ActionsPage.tsx`) has full CRUD to bind `(database, event_type) → workflow` + notify-users.
- Route `/actions` is wired (`App.tsx:83`) but the **sidebar nav item is commented out** (`Sidebar.tsx:17,45`), so the page is currently unreachable.

**The single gap** this design closes: `ActionBinding.workflow_id` is `NOT NULL` — a binding can target only a workflow, never a single agent.

## Decisions (from brainstorming)

- **Scope:** add agent as a bindable target; reuse the existing pipeline. Do NOT rebuild events.
- **Agent output handling:** **Log + notify** — store the full agent result in `ActionEvent.result`, send a completion notification with a short summary/rationale. No write-back to the row (out of scope).
- **UI:** Actions must be visible + operable — re-enable nav, add a target-type selector.
- **Project overrides (CLAUDE.md):** no automated tests unless asked; do not auto-run typecheck/lint/build/format. Verification is manual (in the running app).

---

## A. Data model

Extend `action_bindings` (ORM `backend/app/modules/action/models.py`, migration in `backend/alembic/versions/`). **Option A — discriminator + two nullable FKs** (chosen):

| Column | Change |
|---|---|
| `target_type` | **NEW** `VARCHAR(16) NOT NULL DEFAULT 'workflow'` ∈ `{'workflow','agent'}` |
| `workflow_id` | **now NULLABLE** (was `NOT NULL`), FK `workflows.id` unchanged |
| `agent_id` | **NEW** `UUID NULL`, FK `agents.id ON DELETE CASCADE` |

**CHECK constraint** `ck_action_bindings_target` — exactly one target set, matching the discriminator:

```
(target_type = 'workflow' AND workflow_id IS NOT NULL AND agent_id IS NULL)
OR
(target_type = 'agent'    AND agent_id    IS NOT NULL AND workflow_id IS NULL)
```

**Migration** (`down_revision = ac20actions01` or current head): add columns → backfill existing rows `target_type='workflow'` → drop old `NOT NULL` on `workflow_id` → add `agent_id` FK + the CHECK. Reuse the `_enable_rls` idiom only if needed (columns on an existing RLS table need no new policy). Register nothing new on the worker beyond what's already imported (the `action` models are already loaded).

*Rejected alternatives:* (B) generic `target_type`+`target_id` with no FK — loses referential integrity, breaks the dispatch join; (C) two nullable FKs without a discriminator — works but the explicit `target_type` reads cleaner in UI/serialization/dispatch.

## B. Backend — service + API

`backend/app/modules/action/service.py`:
- `create_binding` / `update_binding`: accept `target_type`, `agent_id` (both), make `workflow_id` optional. Add `_validate_target(target_type, workflow_id, agent_id)` enforcing exactly-one (mirrors the DB CHECK; raises `ConflictError` on violation).
- `serialize_binding`: add `"target_type"` and `"agent_id"` (nullable → `str | None`); `workflow_id` may now be `None`.

`backend/app/modules/action/routes.py`:
- `CreateActionRequest` / `UpdateActionRequest`: add `target_type: str` (default `"workflow"`) and `agent_id: UUID | None`; make `workflow_id: UUID | None`.

## C. Backend — dispatch + agent execution

`dispatch_pending_events` (`service.py:128`) branches per matched binding on `b.target_type`:

- **`workflow`** — unchanged: `create_run(...)` + append run_id; dispatched notification as today.
- **`agent`** — do NOT create a WorkflowRun. Record the agent dispatch in `ActionEvent.result.dispatched[]` (`{action_id, agent_id, kind:"agent"}`), send the same "dispatched" notification, and collect an **agent-task descriptor** `{event_id, binding_id}` to enqueue.

Return signature changes from `list[str]` (run_ids) to a small struct carrying **both** workflow run_ids and agent-task descriptors, e.g. `DispatchOutcome(run_ids: list[str], agent_tasks: list[AgentTaskRef])`. The worker enqueues each accordingly.

`backend/app/modules/action/worker.py` — `process_tenant_action_events`:
- for each `run_id` → `enqueue_job_with_context(pool, "run_workflow", run_id=...)` (unchanged);
- for each agent task → `enqueue_job_with_context(pool, "run_agent_task", event_id=...)`.

**New job `run_agent_task(ctx, *, event_id)`** (`@tenant_aware_job`, in `action/worker.py`), the single owner of the agent event's finalization:
1. Load the `ActionEvent` + its matched `ActionBinding` (`agent_id`).
2. Load the `Agent`; take `department_id = agent.department_id` (fallback: the app's `department_id`).
3. Build `task_payload`:
   ```python
   {
     "task": {"summary": f"Process {event_type} on mini-app {app_id}"},
     "input": {"source": "action", "action_id", "app_id", "row_id", "event_type", "data": row_data},
     "expected": [],
     "criteria": {},           # no forced tool — execute_task is no-tool-safe
   }
   ```
4. `result = await AgentExecutor(session).execute_task(agent_id, task_payload, tenant_id=..., department_id=...)`.
5. Persist: `ActionEvent.result` ← serialized `TaskExecutionResult` (output, confidence, rationale, tool_calls, kb_citations, success, error); set `processed_at`; keep `status='dispatched'` on success (or `'failed'` on `result.success is False` / exception).
6. **Completion notification** (Log + notify): `create_notification(category="action.completed", title=f"Agent finished — {binding.name}", body=<short summary: rationale or truncated output>, ref={action_id, app_id, row_id})` to recipients (`notify_user_ids` or owner). Set `completed_notified=True` so the fan-out drops it.
7. On exception: `status='failed'`, `error=str(e)`, `completed_notified=True`, error notification.

**Why this is safe against the existing sweep:** agent events have `workflow_run_id = NULL`; `notify_completed_events` filters `workflow_run_id.isnot(None)`, so it never touches them. `dispatch_pending_events` only processes `status='pending'`, so a dispatched agent event is never re-run.

Register `run_agent_task` in `backend/scripts/run_worker.py` (`functions=[*..., run_agent_task]`).

## D. Frontend — visibility + agent target

1. **Re-enable nav** (`frontend/src/components/Sidebar.tsx`): uncomment the `Zap` import (line 17) and the `{ to: "/actions", label: "Actions", icon: Zap }` item (line 45). Re-enable the CommandPalette navigation entry if it is similarly gated (`components/CommandPalette/navigationCommands.ts`).
2. **API/types** (`frontend/src/lib/actionsApi.ts`): add `target_type: "workflow" | "agent"` and `agent_id: string | null` to `ActionBinding` + `CreateActionInput`; `workflow_id` becomes `string | null`.
3. **Hook** (`frontend/src/hooks/useActions.ts`): reuse `useAgents` for the agent dropdown source (import existing hook).
4. **Actions form** (`frontend/src/routes/actions/ActionsPage.tsx`):
   - `DraftState` gains `target_type` + `agent_id`.
   - Add a **Target type** toggle (Workflow | Agent).
   - When `workflow`: show the existing Workflow `<select>`; when `agent`: show an **Agent** `<select>` (from `useAgents`). Validate the matching id on submit.
   - Table: replace the "Workflow" column with a **"Target"** column rendering `target_type` + resolved name (workflow or agent).

## E. Data flow (agent path, end to end)

```
create_row (INSERT user profile)
  → emit_action_event(row.created)                       # pending ActionEvent
  → cron (5s) → process_tenant_action_events
      → dispatch_pending_events
          match binding (target_type='agent')
          → notification "dispatched", event.status='dispatched'
          → agent_tasks += {event_id}
      → enqueue run_agent_task(event_id)
  → run_agent_task
      → AgentExecutor.execute_task(agent_id, payload)
      → event.result = TaskExecutionResult; completed_notified=true
      → notification "action.completed" (summary/rationale)
```

## Components & boundaries

| Unit | Responsibility | Depends on |
|---|---|---|
| `action_bindings` schema + migration | Persist target_type/agent_id + integrity | Alembic, existing RLS table |
| `action/service.py` | Binding CRUD + exactly-one validation + dispatch branch | models, orchestrator.create_run, AgentExecutor (indirect) |
| `action/worker.py` `run_agent_task` | Own the agent event lifecycle (run, persist, notify) | AgentExecutor, notification.service |
| `action/routes.py` | Transport for the new fields | service |
| `ActionsPage.tsx` + `actionsApi.ts` | Pick target, show it, list it | useAgents, useWorkflows |
| `Sidebar.tsx` | Make Actions reachable | — |

## Out of scope (YAGNI)

- Write-back of agent output into the mini-app row.
- New event types beyond `row.*` (the CHECK on `event_type` stays as-is).
- An events/results log viewer UI (notifications + `ActionEvent.result` suffice).
- Retry/backoff for a crashed `run_agent_task` (event stays `dispatched`; not re-run — acceptable for the demo).

## Open questions

- Confirm the current Alembic head for `down_revision` (spec assumes `ac20actions01`; verify at plan time).
- `department_id` fallback: if an agent's `department_id` ever mismatches the app's department for KB scoping, KB retrieval may return nothing — acceptable for the demo (execute_task is no-KB-safe). Confirm no stricter requirement.
