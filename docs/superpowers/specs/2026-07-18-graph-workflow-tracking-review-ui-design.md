# Graph Workflow — Run Tracking + Human Review UI (Sub-project 3C)

**Date:** 2026-07-18
**Status:** Design approved, pending spec review
**Depends on:** 3A (data model + serializers), 3B (execution engine + review/rollback endpoints).
**Scope:** The frontend that drives the 3B engine — an interactive DAG canvas that tracks a run in real time (via polling), a node review panel for the four human decisions (Approve / Retry / Override / Reject), and the rollback confirm flow — plus one small backend addition to expose the immutable graph topology to the client. Excludes AI-chat authoring (3D) and realtime push.

## 1. Context & Problem

3B shipped the backend: the engine walks the DAG, pauses at human-gated nodes, and exposes three endpoints (`GET /workflows/runs/{run_id}/nodes`, `POST …/nodes/{node_key}/decision`, `POST …/rollbacks/{rollback_id}/confirm`). Nothing in the frontend calls them. The frontend today is Story-3.1 level only: workflow-definition CRUD (`lib/workflowsApi.ts`, `components/workflows/{DefinitionTab,ConstraintsEditor,WorkflowDetailShell}`). The `routes/orchestrator/`, `routes/trace.$runId/`, `routes/actions/` folders are empty placeholders.

3C adds the **run-facing UI**: trigger a run, watch its DAG execute, and — when a node pauses for review — approve/retry/override/reject it, including the reject→rollback confirm handshake. This is the demo-visible surface for the entire graph-workflow feature.

## 2. Design Decisions (locked)

| Decision | Choice |
|---|---|
| Graph render | Interactive DAG **canvas** (not a list). |
| Canvas tech | **Hand-rolled SVG** (A1) — zero new deps, positions pre-stored, matches the app's custom `ui/` token system. Pan/zoom is an optional stretch. |
| Run trigger | In scope — a **Runs tab** with a "Run" button (`POST /workflows/{id}/runs`) + runs list. |
| Entry point | **Runs tab** on `WorkflowDetailShell` → navigate to a new route `/workflows/:id/runs/:runId` for the tracking canvas. |
| Approver gating | Decision + rollback-confirm actions are shown/enabled only when `useAuth().user.id ∈ node.approver_user_ids`; the backend already 403s, the UI mirrors it. |
| Live updates | **Polling** (TanStack Query `refetchInterval` ~2s) while the run is non-terminal; stop when terminal. No WebSocket/SSE (spec §7 of 3B). |
| Topology source | New backend read endpoint `GET /workflows/runs/{run_id}/graph` (immutable snapshot: edges + per-node position/label/agent_id/approvers). Fetched once; kept out of the polled `/nodes` payload. |
| Override validation | None (backend stores verbatim; consistent with 3A/3B). |

## 3. Backend addition (one endpoint)

The only backend change. Everything else in 3C is frontend.

`GET /workflows/runs/{run_id}/graph` — returns `serialize_graph_snapshot(run.graph_snapshot)`:

```json
{"nodes": [{"node_key": "A", "label": "Extract", "agent_id": "…",
            "config": {}, "position": {"x": 40, "y": 80},
            "approver_user_ids": ["…"]}],
 "edges": [{"from": "A", "to": "B"}]}
```

- New route in `orchestrator/routes.py` (existing `/workflows` router), mirroring `get_run_route`'s RLS-scoped `get_run` load; 404 if the run has no `graph_snapshot` (graphless run) or is cross-tenant.
- `serialize_graph_snapshot` already exists (3A) and returns the snapshot verbatim — no new serializer.
- **Rationale:** topology is immutable per run, so it is fetched once; the polled `/nodes` endpoint stays lean (changing runtime state only). Adding the snapshot to the shared `serialize_run` would bloat the runs-list payload, so a dedicated endpoint is cleaner and isolated.

## 4. Frontend architecture

### 4.1 API layer — `lib/runsApi.ts`

Typed `apiFetch` wrappers (mirrors `workflowsApi.ts`; `apiFetch` injects JWT + tenant and unwraps `{data,error,meta}`):

| Function | Endpoint |
|---|---|
| `createRun(workflowId, input)` | `POST /workflows/{id}/runs` |
| `listRuns(workflowId)` | `GET /workflows/{id}/runs` |
| `getRun(runId)` | `GET /workflows/runs/{run_id}` |
| `getRunGraph(runId)` | `GET /workflows/runs/{run_id}/graph` (new, §3) |
| `listRunNodes(runId)` | `GET /workflows/runs/{run_id}/nodes` |
| `postDecision(runId, nodeKey, body)` | `POST …/nodes/{node_key}/decision` |
| `confirmRollback(runId, rollbackId, accept)` | `POST …/rollbacks/{rollback_id}/confirm` |

TypeScript interfaces: `Run`, `RunNodeExecution`, `GraphSnapshot`/`GraphNode`/`GraphEdge`, `RunNodesResponse` (`{nodes, rollbacks:{pending,refused}}`), `DecisionRequest` (`action, guidance?, output?, reason?, target_node_key?`).

### 4.2 Hooks (TanStack Query)

- `useRuns(workflowId)` — list, for the Runs tab.
- `useRun(runId)` — run status/result; polled while non-terminal (drives terminal detection).
- `useRunGraph(runId)` — topology; `staleTime: Infinity` (immutable), fetched once.
- `useRunNodes(runId)` — runtime node state + rollbacks; `refetchInterval` ~2s while the run is non-terminal, `false` once terminal (`completed`/`failed`/`timed_out`/`completed_with_failures`).
- `useRunMutations(runId)` — `decide` + `confirmRollback`; each `onSuccess` invalidates `runNodes` (+ `run`) so the canvas reflects new state on the next poll (the backend endpoint already re-enqueues the engine resume).

Terminal-run status set is shared with the badge component to avoid drift.

### 4.3 Routing / entry point

- `WorkflowDetailShell` gains a **tab bar**: `Definition` (existing) + `Runs` (new). This is the first multi-tab use of the shell; the tab state is local (the shell comment already anticipates "Run history … arrive in later stories").
- **Runs tab** (`components/workflows/RunsTab.tsx`): a "Run" trigger button (opens a minimal input dialog → `createRun` → navigate to the new run) + a runs table (status badge, started/ended, row → run page). Mirrors `routes/workflows.tsx` table conventions.
- New route `/workflows/:id/runs/:runId` (`routes/orchestrator/RunTrackingPage.tsx`, filling the placeholder) → renders the canvas + review panel.

### 4.4 Components — `components/workflows/runs/`

Each is single-purpose (design-for-isolation) and ≤~200 lines:

- `RunTrackingView` — orchestrates: loads graph + nodes, merges by `node_key`, holds selected-node state, lays out canvas + `RunReviewPanel`.
- `RunGraphCanvas` — SVG. Edges as `<path>` from parent→child using stored `position`; nodes rendered via `RunNode`. Viewport sized from node bounds. (Optional stretch: CSS-transform pan/zoom wrapper.)
- `RunNode` — one node: label, `RunStatusBadge`, gated indicator; click selects; highlights the selected node and a node with a pending rollback.
- `RunReviewPanel` — side panel for the selected node: I/O, status, decision history, and the decision actions (§4.5).
- `NodeIoViewer` — read-only JSON view of `input`/`output` (reuse existing JSON/pre styling if present; else a simple `<pre>`).
- `RollbackConfirmCard` — shown when a `rollbacks.pending` targets a node the current user approves: Accept / Refuse.
- `RunStatusBadge` — run + node status → token-colored pill (single source of status→color/label mapping).

### 4.5 Review panel — decisions, approver-gated

Guard: actions render only when node.status === `awaiting_approval` **and** `useAuth().user.id ∈ node.approver_user_ids`.

- **Approve** — `postDecision({action:'approve'})`.
- **Retry** — guidance `<textarea>` → `{action:'retry', guidance}`.
- **Override** — JSON editor (textarea + parse/validate-JSON-only) → `{action:'override', output}`.
- **Reject** — reason input + **parent picker** (the node's parents, derived from `edges` where `to === node_key`); a parent whose key appears in `rollbacks.refused` for this requester is disabled → `{action:'reject', reason, target_node_key}`.
- **Rollback confirm** — when `rollbacks.pending` targets a node the user approves, `RollbackConfirmCard` offers Accept / Refuse → `confirmRollback`.

Non-approvers and non-`awaiting_approval` nodes get the read-only panel (I/O + history, no actions). Optimistic UX: after a POST, invalidate and let the poll settle (no local optimistic state — keeps the canvas the single source of truth).

## 5. Data flow

1. Runs tab → "Run" → `createRun` → navigate to `/workflows/:id/runs/:runId`.
2. Run page loads `useRunGraph` (once) + starts `useRunNodes`/`useRun` polling.
3. Merge topology (positions/edges/labels/approvers) with runtime state (status/decision/io) by `node_key` → canvas.
4. As the engine progresses, polling reflects status changes; a node hitting `awaiting_approval` gets the gated indicator.
5. Approver selects it → review panel → decision POST → invalidate → next poll shows the result (engine already resumed server-side).
6. Reject → pending rollback appears; the target's approver sees `RollbackConfirmCard`; Accept resets the subtree → canvas shows nodes back to `pending`/re-running.
7. Polling stops when the run reaches a terminal status.

## 6. Error handling

- API errors surface via the existing `apiFetch` envelope + `ErrorState`/toast conventions already in the app.
- A decision POST returning 409 (already decided / first-wins lost) or 403 (not an approver) shows an inline panel error and refetches nodes (state moved under us).
- `getRunGraph` 404 (graphless run) → the run page falls back to a "This run has no graph" message (defensive; the Runs tab only links graph runs in practice).

## 7. Testing

Per project preference (CLAUDE.md): **no new test files unless explicitly requested.** Each task's verification is a typecheck/build-free smoke check — component renders in isolation with mocked hook data, and the app boots with the new route. (The repo has vitest + testing-library already; tests may be added later on request.)

## 8. Out of scope (explicit)

- Realtime push (WebSocket/SSE) — polling only.
- Editing graph structure from the run view — authoring is the builder / 3D.
- Override output schema validation — stored verbatim.
- Pan/zoom/minimap beyond the optional CSS-transform stretch.
- Backend engine changes — 3B is complete; 3C adds only the read-only `/graph` endpoint.

## 9. Deliverables

1. Backend: `GET /workflows/runs/{run_id}/graph` in `orchestrator/routes.py` (+ smoke: route present, returns snapshot).
2. `lib/runsApi.ts` — typed wrappers + interfaces.
3. Hooks: `useRuns`, `useRun`, `useRunGraph`, `useRunNodes`, `useRunMutations`.
4. `WorkflowDetailShell` tab bar + `RunsTab` (list + Run trigger).
5. Route `/workflows/:id/runs/:runId` + `RunTrackingPage`/`RunTrackingView`.
6. Canvas + node components: `RunGraphCanvas`, `RunNode`, `RunStatusBadge`.
7. Review: `RunReviewPanel`, `NodeIoViewer`, `RollbackConfirmCard` (approver-gated actions).
8. Status→color/label mapping single source; terminal-status set shared with polling hooks.

## 10. Open questions

- **Run input dialog shape:** `createRun` takes free-form `input` (JSON). For the demo, a single JSON textarea vs. a typed form? Leaning: JSON textarea (matches the lenient backend), revisit if the demo needs a friendlier form.
- **Node positions absent/degenerate:** if a snapshot has all-zero or missing `position` (older graphs), the canvas overlaps nodes. Leaning: a simple fallback auto-layout (topological columns) when positions are missing/degenerate — decide at plan time whether to include or defer.
- **Multiple concurrent approvers polling:** first-wins is enforced server-side; the UI just refetches on 409. No client coordination needed — confirm acceptable.
