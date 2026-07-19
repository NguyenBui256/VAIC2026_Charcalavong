# Graph Workflow — Data Model (Sub-project 3A)

**Date:** 2026-07-18
**Status:** Design approved, pending spec review
**Scope:** Data model ONLY. Foundation for 3B (DAG execution engine + human review),
3C (Tracking UI), 3D (AI-chat authoring), 3E (rollback protocol).

## 1. Context & Problem

Today the orchestrator runs a **flat** model: `decompose_run` asks an LLM to split a
Workflow's `description` into ≤5 independent `tasks`, which run sequentially with no
dependencies and no data passed between them (`orchestrator/service.py`). Each task's
input is built by the decomposition LLM from the run input; task B never consumes task
A's output.

The target model is a **builder-authored directed acyclic graph (DAG)**:

- Nodes are Specialist Agents. Edges express dependency + data flow (A → B, C means B
  and C consume A's output).
- Some nodes are **human-gated**: assigned to one or more approvers who review the
  node's input/output and Approve / Retry / Reject before the run proceeds.
- A rejected node can trigger a rollback upstream (3E).
- A "Tracking" UI renders the live graph of a run and offers a review sidebar (3C).

The graph is produced at **design time** (builder chats with an AI that proposes a
graph; builder edits and saves — 3D) and executed **deterministically at run time** from
the saved definition. There is no run-time LLM decomposition in the new model.

This sub-project (3A) delivers the **persistence layer** that every later sub-project
builds on: the graph definition tables, the per-run runtime-state tables, RLS, and the
snapshot-on-run-create mechanism. It does NOT implement execution, review APIs, the UI,
or rollback logic.

## 2. Design Decisions (locked)

| Decision | Choice |
|---|---|
| Node ↔ agent | Every node binds to exactly one Agent. No standalone "input" nodes. |
| Root input | Nodes with no incoming edge (roots) receive `run.input` as their input. |
| Data flow on edges | Whole-output merge: a node's input = `{ <parent_node_key>: <parent output>, ... }` over all parents. No per-field mapping. |
| Graph shape | DAG — cycles rejected at save time. |
| Human gating | A node with ≥1 approver is human-gated; a node with 0 approvers runs automatically. |
| Multi-approver quorum | First-wins — the first approver's decision resolves the node and locks out the rest. |
| Run versioning | Snapshot-on-create — the run copies the whole graph at creation; later workflow edits never affect an in-flight or past run. |

## 3. Schema

All tables are tenant-scoped with the standard RLS policy
(`tenant_id = current_setting('app.tenant_id')::uuid`, ENABLE + FORCE), mirroring
`agents` / `workflows` / `tasks`. All ids are `uuid7`. All FKs carry an explicit
`ondelete`. New tables live in `app/modules/orchestrator/models.py` (graph is an
orchestrator concern).

### 3.1 Definition tables (part of the Workflow, edited at design time)

**`workflow_nodes`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | uuid7 |
| `tenant_id` | UUID FK tenants CASCADE | RLS |
| `workflow_id` | UUID FK workflows CASCADE | owning workflow |
| `node_key` | String(64) | stable, human-readable key unique **within a workflow** (e.g. `"credit_check"`); used as the join key in runtime input/output maps |
| `label` | String(255) | display label |
| `agent_id` | UUID FK agents RESTRICT | the bound Specialist Agent |
| `config` | JSONB, default `{}` | optional per-node instruction/override, opaque here |
| `position_x` | Float, default 0 | UI canvas coordinate |
| `position_y` | Float, default 0 | UI canvas coordinate |
| `created_at` / `updated_at` | timestamptz | |

Constraint: `UNIQUE(workflow_id, node_key)`.

**`workflow_edges`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | uuid7 |
| `tenant_id` | UUID FK tenants CASCADE | RLS |
| `workflow_id` | UUID FK workflows CASCADE | owning workflow |
| `from_node_id` | UUID FK workflow_nodes CASCADE | parent |
| `to_node_id` | UUID FK workflow_nodes CASCADE | child |
| `created_at` | timestamptz | |

Constraint: `UNIQUE(from_node_id, to_node_id)`. No field-mapping column — data flow is
whole-output merge. Acyclicity is enforced in the service layer at save time (see §5),
not by a DB constraint.

**`workflow_node_approvers`** (M2M node ↔ users)

| Column | Type | Notes |
|---|---|---|
| `node_id` | UUID FK workflow_nodes CASCADE | PK part |
| `user_id` | UUID FK users RESTRICT | PK part |
| `tenant_id` | UUID FK tenants CASCADE | RLS |
| `created_at` | timestamptz | |

PK `(node_id, user_id)`. Zero rows for a node ⇒ auto (non-gated). ≥1 row ⇒ human-gated.

### 3.2 Runtime tables (per Run)

**`workflow_runs`** — add one column:

| Column | Type | Notes |
|---|---|---|
| `graph_snapshot` | JSONB, nullable | immutable copy of the graph (nodes+edges+approvers) taken at run creation; source of truth for topology + rendering + rollback. Nullable so legacy flat runs (no graph) keep working. |

Snapshot JSON shape:

```json
{
  "nodes": [
    {"node_key": "intake", "label": "Intake",
     "agent_id": "…", "config": {}, "position": {"x": 0, "y": 0},
     "approver_user_ids": ["…"]}
  ],
  "edges": [{"from": "intake", "to": "credit_check"}]
}
```

**`run_node_executions`** — mutable per-node runtime state (one row per node per run)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | uuid7 |
| `tenant_id` | UUID FK tenants CASCADE | RLS |
| `run_id` | UUID FK workflow_runs CASCADE | owning run |
| `node_key` | String(64) | matches the snapshot key |
| `agent_id` | UUID FK agents RESTRICT | copied from the node |
| `status` | String(32), default `pending` | see enum below |
| `input` | JSONB, nullable | resolved input (merge of parent outputs / run input); populated by the engine (3B) |
| `output` | JSONB, nullable | agent output; populated by 3B |
| `approver_user_ids` | JSONB (array), default `[]` | snapshot of assigned approvers |
| `decision` | String(16), nullable | `approve` / `retry` / `reject` (set by 3C) |
| `decided_by` | UUID FK users RESTRICT, nullable | which approver resolved it (first-wins) |
| `reason` | Text, nullable | reject reason |
| `guidance` | Text, nullable | extra instruction for a retry |
| `decided_at` | timestamptz, nullable | |
| `started_at` / `completed_at` | timestamptz, nullable | |
| `created_at` | timestamptz | |

Constraint: `UNIQUE(run_id, node_key)`.

**Status enum (defined now, populated across 3B/3C/3E — pre-provisioned like the
existing `awaiting_human`):**

```
pending          -- created, not yet started
running          -- agent executing
awaiting_approval -- agent done; human-gated node waiting for a decision
completed        -- done (auto node finished, or approver Approved)
failed           -- infra/agent error
rejected         -- approver Rejected (may drive rollback in 3E)
skipped          -- not reached (e.g. an upstream reject cut this branch)
rolled_back      -- invalidated by a confirmed rollback; will be re-run (3E)
```

Enforced by a CHECK constraint, matching the `RUN_STATUSES` / `TASK_STATUSES` pattern
in `orchestrator/models.py`.

## 4. Snapshot-on-create

`create_run` (`orchestrator/service.py`) gains graph handling **when the workflow has a
graph** (≥1 `workflow_nodes` row):

1. Read the live `workflow_nodes` + `workflow_edges` + `workflow_node_approvers` for the
   workflow (RLS-scoped).
2. Serialize into `graph_snapshot` (§3.2 shape) on the new `WorkflowRun`.
3. Insert one `run_node_executions` row per node: `status='pending'`,
   `agent_id`/`node_key`/`approver_user_ids` copied from the snapshot; `input`/`output`
   left null (the engine fills them in 3B).

A workflow with **no** nodes falls back to today's flat path unchanged (backward
compatible; `graph_snapshot` stays null and no `run_node_executions` rows are created).
The choice of which path a run takes is a 3B concern; 3A only guarantees the snapshot is
written when a graph exists.

## 5. Validation (service layer, at save time)

Graph-definition writes (created in 3D, but the invariants belong to the data layer)
must reject:

- an edge referencing a node not in the same workflow;
- a duplicate edge (also a DB unique constraint);
- a duplicate `node_key` within a workflow (also a DB unique constraint);
- a **cycle** — the edge set must form a DAG (topological-sort check; reject on
  back-edge);
- an approver `user_id` that is not a member of the tenant.

3A ships the validation helpers (pure functions over node/edge lists) so 3D and any
seed script reuse them. Wiring them into authoring endpoints is 3D.

## 6. Out of scope (explicit)

- DAG execution / topological dispatch / data-flow resolution — **3B**.
- Pause/resume at human-gated nodes, review endpoints, first-wins locking — **3B/3C**.
- Tracking UI + realtime updates — **3C**.
- AI-chat authoring + authoring endpoints — **3D**.
- Rollback request/confirm/cascade — **3E** (statuses `rejected`/`rolled_back` and the
  `graph_snapshot` topology are pre-provisioned here to support it).
- `risk_level` / sensitive-tool auto-gating — deferred; human gating is approver-driven.
- Removing the flat `decompose_run` / `tasks` flow — untouched by 3A.

## 7. Deliverables

1. New models in `app/modules/orchestrator/models.py`: `WorkflowNode`, `WorkflowEdge`,
   `WorkflowNodeApprover`, `RunNodeExecution`; `graph_snapshot` column on `WorkflowRun`.
2. One Alembic migration: tables + indexes + CHECK + unique constraints + RLS policies
   (ENABLE + FORCE, mirroring existing orchestrator migrations).
3. Snapshot logic in `create_run` (guarded by "workflow has a graph").
4. Graph-validation helper module (DAG check + reference checks) with the pure functions.
5. Serialization helpers for the snapshot + `run_node_executions` (response shapes, ISO
   ms timestamps per AR-14) — needed by 3C later, defined here for the new entities.

## 8. Open questions

- `node_key` source: builder-provided vs auto-generated from label. Assumed
  builder/authoring-provided and unique-validated; revisit in 3D if the chat flow should
  auto-slug labels.
- Whether `config` per node needs a defined schema now or stays opaque until 3B uses it.
  Assumed opaque for 3A.
