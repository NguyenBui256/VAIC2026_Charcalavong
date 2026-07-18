# Graph Workflow — Execution Engine + Human Review + Rollback (Sub-project 3B)

**Date:** 2026-07-18
**Status:** Design approved, pending spec review
**Depends on:** 3A (data model — `graph_snapshot`, `run_node_executions`, `graph_validation`, `graph_snapshot.py`).
**Scope:** The run-time engine that executes a builder-authored DAG, pauses at human-gated nodes, applies the four review decisions, and runs the rollback protocol. Excludes the Tracking UI (3C) and AI-chat authoring (3D).

## 1. Context & Problem

3A added the persistence layer: a run created from a graph workflow carries an immutable `graph_snapshot` and one `pending` `run_node_executions` row per node. Nothing executes them yet — the arq worker still routes every run through the flat `orchestrate_run` (LLM decompose → sequential independent tasks).

3B adds the **graph execution path**: a resumable, state-driven engine that walks the DAG in topological order, resolves each node's input from its parents' outputs, dispatches the node's Specialist Agent, and — at human-gated nodes — pauses the whole run for a human decision (Approve / Retry / Override / Reject). Reject opens a **rollback** to a chosen parent, whose approver confirms or refuses; an accepted rollback invalidates the parent's entire descendant subtree and re-runs it after the parent regenerates output.

The flat path stays intact for graphless runs. The known limitation from Part 1 (synchronous `invoke_agent_model` inside the async worker blocks the loop until the provider timeout) is accepted for the demo and unchanged here.

## 2. Design Decisions (locked)

| Decision | Choice |
|---|---|
| Execution order | Sequential, topological — one node at a time. |
| Pause granularity | Pause the whole run at a human-gated node (run → `awaiting_human`, job ends). |
| Resume | Human records a decision via a 3B API → re-enqueue `run_workflow(resume=True)` → engine re-enters and continues from persisted state. |
| Engine state | Fully state-driven from `run_node_executions` + `graph_snapshot`; no in-memory run state survives a pause. |
| Node decisions | Approve, Retry (guidance → re-run agent), Override (human types output), Reject (→ rollback to a chosen parent). |
| Multi-approver | First-wins — the first approver's decision resolves the node (locks the rest). |
| Retry count | Unlimited (human-driven). |
| Rollback confirm | The target parent's approver confirms/refuses. Auto parent (no approver) → auto-accept. |
| Rollback regen | Accepted rollback re-runs the parent's agent with the reject reason appended as guidance; a human-gated parent re-enters its own review. |
| Rollback invalidation | Accepted rollback marks the parent's ENTIRE descendant subtree `rolled_back → pending` for re-run in topo order. |
| Rollback target (multi-parent) | The rejecting node's approver picks which parent to roll back to. |
| Rollback refused | The rejecting node returns to review; the rollback-to-that-parent option is disabled; it must Approve/Retry/Override. |
| Completed nodes | Stay completed across a pause; never re-run unless invalidated by a rollback. |

## 3. Architecture

### 3.1 Worker routing

`app/workers/orchestrator_worker.py::run_workflow` currently: CAS `pending→running` (fresh) then `orchestrate_run`. Change: after the run is `running`, branch on the run's `graph_snapshot`:

- `graph_snapshot` present → `graph_orchestrate(session, run_id)` (new, 3B).
- else → `orchestrate_run` (unchanged flat path).

On the `resume=True` path (a paused graph run being resumed), the run is `awaiting_human`, not `pending`. `run_workflow` must, for graph runs, CAS `awaiting_human→running` before calling `graph_orchestrate` (mirrors the existing `pending→running` CAS, using the same `transition_and_audit`). The fresh-dispatch path keeps `pending→running`.

### 3.2 The engine loop — `graph_orchestrate(session, run_id)`

Lives in a new module `app/modules/orchestrator/graph_engine.py`. Each invocation runs on the event loop (like `orchestrate_run`) so `tenant_context` stays visible; re-asserts RLS after every CAS commit (reuse `_reassert_rls`). Pseudocode:

```
reassert_rls()
snapshot = run.graph_snapshot
nodes = run_node_executions for run (by node_key)
edges = snapshot edges ; parents = parents_by_key ; order = topological_order

loop:
    # 1. a pending rollback blocks everything -> pause
    if any run_rollback_requests(run) with status == 'pending':
        set run 'awaiting_human'; return   # waiting on a parent's confirm

    # 2. a node awaiting a human decision -> pause
    if any node.status == 'awaiting_approval':
        set run 'awaiting_human'; return

    # 3. next runnable node in topo order: status in (pending) with all parents completed
    node = first in `order` where node.status == 'pending' and all(parent.status == 'completed')
    if node is None:
        # nothing left to run and nothing pending -> finalize
        finalize_run(); return

    run_node(node)   # resolve input, run agent, set output
    if node is human-gated (approver_user_ids non-empty):
        node.status = 'awaiting_approval'; set run 'awaiting_human'; return   # pause
    else:
        node.status = 'completed'
    # continue loop
```

`run_node(node)`:
- `input` = `run.input` if node is a root (no parents), else `{ parent_key: parent.output for each parent }`.
- CAS `pending→running`, stamp `started_at`, persist `input`.
- Call `AgentExecutor.execute_task(agent_id, task_payload, tenant_id, department_id)` where `task_payload` is built from the node (summary/label + resolved input + node.config; reuse the existing `TaskExecutionResult` shape). Store `output` = result output; on infra error set `failed` (the run finalizes as failed).

`finalize_run()`: aggregate node outputs into `run.result`; run → `completed` if no node is `failed`, else `failed` (CAS `running→…`, AD-6).

### 3.3 Resume entry

`graph_orchestrate` is safe to re-enter: it recomputes everything from `run_node_executions`. A resumed run (`awaiting_human→running`) simply continues the loop — the decision that triggered the resume has already mutated node/rollback state, so the loop's guards pick up the next action.

## 4. Human review decisions

### 4.1 Endpoint

`POST /workflows/runs/{run_id}/nodes/{node_key}/decision` (new router in `orchestrator/graph_routes.py`, mounted under the existing `/workflows` prefix family). Body:

```json
{"action": "approve|retry|override|reject",
 "guidance": "…(retry)…", "output": {…override…},
 "reason": "…(reject)…", "target_node_key": "A (reject, required)"}
```

Authorization: the caller must be in the node's `approver_user_ids` (first-wins — reject if the node is not `awaiting_approval`, i.e. already decided). Decision is recorded on the `run_node_executions` row (`decision`, `decided_by`, `reason`/`guidance`, `decided_at`).

### 4.2 Semantics (service layer, `graph_review.py`)

- **approve** → node `completed`; enqueue resume.
- **retry** → node `pending` again with `guidance` stored; the engine re-runs the agent and appends `guidance` to the prompt; enqueue resume. (Unlimited retries.)
- **override** → node `completed` with `output` = the human-supplied object; enqueue resume.
- **reject** → require `target_node_key` ∈ the node's parents; create a `run_rollback_requests` row (`pending`); the rejecting node stays `awaiting_approval` but is marked blocked-by-rollback (see §5); if the target parent is auto (no approver) → immediately auto-accept (apply §5 accept inline); enqueue resume.

All four end by enqueuing `run_workflow(resume=True)` for the run (the endpoint has the arq pool, mirroring `create_run_route`).

## 5. Rollback protocol

### 5.1 Data — `run_rollback_requests`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | uuid7 |
| `tenant_id` | UUID FK tenants CASCADE | RLS |
| `run_id` | UUID FK workflow_runs CASCADE | |
| `requester_node_key` | String(64) | the rejecting node |
| `target_node_key` | String(64) | the parent to roll back to |
| `reason` | Text | reject reason (becomes the parent's retry guidance) |
| `status` | String(16) | `pending` / `accepted` / `refused` (CHECK) |
| `decided_by` | UUID FK users RESTRICT, nullable | parent approver who confirmed |
| `decided_at` | timestamptz, nullable | |
| `created_at` | timestamptz | |

Tenant-scoped RLS (ENABLE+FORCE+policy+GRANT SELECT/INSERT/UPDATE), same pattern as 3A tables. One Alembic migration (down_revision = 3A's `c3d4e5f6a7b8`) also adds a `rollback_requested` value to the `run_node_executions.status` CHECK (drop+recreate the CHECK constraint) if needed to mark a node whose rollback is in flight — see §5.3.

### 5.2 Confirm endpoint

`POST /workflows/runs/{run_id}/rollbacks/{rollback_id}/confirm` body `{"accept": true|false}`. Authorization: caller must be an approver of the **target** node. Auto target parents never reach this endpoint (auto-accepted at reject time).

### 5.3 Accept

1. Mark the request `accepted` (`decided_by`, `decided_at`).
2. Compute `descendants(target)` from the snapshot edges (all nodes reachable from the target, target excluded).
3. Set every descendant's `run_node_executions` row → `rolled_back` then immediately → `pending` (clear `output`/`decision`/`decided_by`/`reason`/`guidance`/timestamps), so the engine re-runs them. The rejecting node is a descendant, so it is reset too.
4. Reset the **target** node → `pending`, store `guidance` = the request `reason` (so `run_node` appends it to the target agent's prompt on re-run). The target re-runs; if human-gated it re-enters `awaiting_approval` on its new output.
5. Enqueue resume. The engine re-runs the target, then its descendants in topo order.

### 5.4 Refuse

1. Mark the request `refused`.
2. The rejecting node returns to a normal `awaiting_approval` decision state; the frontend disables "reject → this parent" (3B exposes the refused set via the nodes endpoint). The node must be resolved via Approve / Retry / Override.
3. Enqueue resume (the engine re-pauses on the still-`awaiting_approval` node — no-op progress, but keeps state consistent).

### 5.5 Node-status handling for an in-flight rollback

While a rollback request is `pending`, the run is `awaiting_human` and the engine's guard #1 (§3.2) blocks all node execution until the target's approver (or auto-accept) resolves it. The rejecting node stays `awaiting_approval` (its own decision is recorded as `reject` but not finalized). No node runs while a rollback is pending — this keeps the sequential model simple and avoids racing a rollback against forward progress.

## 6. APIs summary (all backend; UI is 3C)

| Method + path | Purpose |
|---|---|
| `GET /workflows/runs/{run_id}/nodes` | list `run_node_executions` (serialized via 3A `serialize_run_node_execution`) + pending/refused rollback info, for the Tracking view |
| `POST /workflows/runs/{run_id}/nodes/{node_key}/decision` | approve / retry / override / reject |
| `POST /workflows/runs/{run_id}/rollbacks/{rollback_id}/confirm` | accept / refuse a rollback |

Every state-changing endpoint emits audit entries through `AuditPort` (consistency with the rest of orchestrator) and enqueues `run_workflow(resume=True)`.

## 7. Out of scope (explicit)

- Tracking UI (graph render + review sidebar + realtime) — **3C**.
- AI-chat authoring of graphs — **3D**.
- Parallel node execution — sequential only.
- Removing / changing the flat `orchestrate_run` path — graphless runs unchanged.
- Offloading the synchronous LLM call off the event loop — accepted limitation (Part 1 provider timeout is the guard).
- Realtime push (WebSocket/SSE) — the nodes endpoint is polled by 3C for the demo.

## 8. Deliverables

1. `graph_engine.py` — `graph_orchestrate` + `run_node` + `finalize_run` + input resolution.
2. `graph_review.py` — decision service (approve/retry/override/reject) + rollback accept/refuse + descendant computation.
3. `graph_routes.py` — the three endpoints, mounted in `main.py`.
4. Worker change — `run_workflow` routes graph runs to `graph_orchestrate`; adds `awaiting_human→running` resume CAS for graph runs.
5. `RunRollbackRequest` model + one Alembic migration (table + RLS; extend node status CHECK with `rollback_requested` if used).
6. Node-status additions if needed (`rollback_requested`) wired through models + migration.
7. Audit + resume-enqueue on every decision/confirm.

## 9. Open questions

- Whether the rejecting node needs a distinct `rollback_requested` status or can stay `awaiting_approval` with the pending `run_rollback_requests` row as the sole signal. Leaning: keep it `awaiting_approval` + rely on the request row (avoids a status/migration change); the engine's guard #1 already gates on the pending request. Decide at plan time.
- `task_payload` shape passed to `AgentExecutor.execute_task` for a node: reuse the flat path's `{task:{summary}, input, expected, criteria}` shape built from the node label + resolved input, or a leaner node-specific shape. Leaning: reuse the existing shape so `AgentExecutor` is untouched.
- Whether Override output should still be schema-checked against the node/agent's expected output. Leaning: no validation for the demo (store verbatim), consistent with 3A's lenient stance.
