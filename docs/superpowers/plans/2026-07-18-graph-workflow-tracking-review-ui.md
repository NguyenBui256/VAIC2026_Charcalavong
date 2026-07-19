# Graph Workflow Run Tracking + Review UI (3C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the run-facing frontend that drives the 3B engine — an interactive SVG DAG canvas that tracks a run via polling, an approver-gated review panel for Approve/Retry/Override/Reject, and the rollback confirm flow — plus one read-only backend endpoint that exposes the immutable graph topology.

**Architecture:** One new backend endpoint (`GET /workflows/runs/{run_id}/graph`) returns the immutable snapshot (edges + node positions/labels/approvers). The frontend fetches topology once and polls the existing `/nodes` endpoint (~2s, stops on terminal status), merges the two by `node_key`, and renders a hand-rolled SVG canvas. A review panel gates the four decision actions behind `useAuth().user.id ∈ node.approver_user_ids`. Entry is a new "Runs" tab on `WorkflowDetailShell` → route `/workflows/:id/runs/:runId`.

**Tech Stack:** React 18, TypeScript, TanStack Query, react-router-dom, the app's custom `ui/` primitives + design tokens (no component library), hand-rolled SVG (no graph lib). Backend: FastAPI + SQLAlchemy (existing orchestrator router).

## Global Constraints

- **No new test files** unless explicitly requested (CLAUDE.md override). Each task's verification is a lightweight smoke check, not a test suite.
- **Do not auto-run** `lint`/`build`/`format`. The one allowed per-task smoke is the TypeScript check `npx tsc --noEmit` (run from `frontend/`) — the frontend analog of an import check; the executor may skip it per project preference and do a manual browser smoke instead. Backend tasks smoke-check via the venv Python import (`backend/.venv/Scripts/python.exe`).
- **Frontend dir:** `frontend/`. **Backend dir:** `backend/`. Paths below are repo-relative.
- **API access** goes through `apiFetch<T>(path, init?)` (`frontend/src/lib/api.ts`) — it injects JWT + tenant headers and unwraps the `{data,error,meta}` envelope, throwing `ApiError` (with `.status`) on non-2xx. Never call `fetch` directly.
- **Hooks** use TanStack Query with array query keys, mirroring `useWorkflows`/`useWorkflowMutations`. Mutations invalidate the affected query keys in `onSuccess`.
- **UI primitives** come from `frontend/src/components/ui` (barrel): `Button, StatusPill, Card, Table, CodeBlock, FormField, Tooltip, EmptyState, Skeleton, ErrorState, useToast, ConfirmDialog`. Styling uses design tokens (`var(--space-*)`, `var(--color-*)`) and utility classes (`text-h1`, `text-body`, `vaic-form-input`, `vaic-focusable`) — no inline hex colors.
- **Status vocabulary (backend, verbatim):** run statuses = `pending, running, awaiting_human, completed, failed, timed_out, completed_with_failures`; node statuses = `pending, running, awaiting_approval, completed, failed, rejected, skipped, rolled_back`. The frontend never invents statuses.
- **Modularize** any file exceeding ~200 lines; kebab-case or PascalCase per the existing convention in each folder (`components/` = PascalCase files, `lib/`/`hooks/` = camelCase files).
- **Current user id** for approver gating: `useAuth().user?.id` (`frontend/src/hooks/useAuth.ts`; `AuthUser.id` is a string).

---

### Task 1: Backend — `GET /workflows/runs/{run_id}/graph`

Exposes the immutable graph topology (edges + node positions/labels/approvers) so the canvas can render structure. Read-only; reuses `get_run` (RLS + not-found) and the existing `serialize_graph_snapshot` (3A).

**Files:**
- Modify: `backend/app/modules/orchestrator/routes.py`

**Interfaces:**
- Produces HTTP: `GET /workflows/runs/{run_id}/graph` → `200 {data: {nodes:[{node_key,label,agent_id,config,position:{x,y},approver_user_ids}], edges:[{from,to}]}}`; `404` (NotFoundError envelope) if the run is missing/cross-tenant or has no `graph_snapshot`.

- [ ] **Step 1: Add the import for `serialize_graph_snapshot`**

In `backend/app/modules/orchestrator/routes.py`, the module already imports `get_run` and `NotFoundError`-raising services. Add the serializer import next to the other orchestrator imports (near line 38, after the `get_workflow as get_workflow_service` line):

```python
from app.modules.orchestrator.graph_serialization import serialize_graph_snapshot
from app.core.errors import NotFoundError
```

(If `NotFoundError` is already imported in this file, keep a single import — the smoke check in Step 3 will fail on a duplicate/unused import, fix it then.)

- [ ] **Step 2: Add the route**

Immediately after `get_run_route` (ends at line ~186), add:

```python
@router.get("/runs/{run_id}/graph")
def get_run_graph_route(
    run_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """GET /workflows/runs/{run_id}/graph — immutable graph topology (3C).

    Returns the stored `graph_snapshot` verbatim (edges + per-node position/
    label/agent_id/approvers) for the run-tracking canvas. `get_run` enforces
    RLS + not-found; a graphless run (flat path) 404s here too.
    """
    run = get_run(session, run_id)
    if run.graph_snapshot is None:
        raise NotFoundError("run has no graph")
    return JSONResponse(
        status_code=200, content=_ok(serialize_graph_snapshot(run.graph_snapshot))
    )
```

- [ ] **Step 3: Verify import + route present**

Run:
```bash
cd backend && .venv/Scripts/python.exe -c "from app.modules.orchestrator.routes import router; print(sorted(r.path for r in router.routes if 'graph' in getattr(r,'path','')))"
```
Expected:
```
['/workflows/runs/{run_id}/graph']
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/orchestrator/routes.py
git commit -m "feat(orchestrator): GET run graph topology endpoint (3C)"
```

---

### Task 2: `runsApi.ts` — API layer + types

Typed `apiFetch` wrappers + shared TypeScript interfaces for runs, graph, node executions, decisions. Mirrors `workflowsApi.ts`.

**Files:**
- Create: `frontend/src/lib/runsApi.ts`

**Interfaces:**
- Produces: types `RunStatus`, `NodeStatus`, `Run`, `GraphNode`, `GraphEdge`, `GraphSnapshot`, `RunNodeExecution`, `RollbackRequest`, `RunNodesResponse`, `DecisionAction`, `DecisionRequest`; functions `createRun`, `listRuns`, `getRun`, `getRunGraph`, `listRunNodes`, `postDecision`, `confirmRollback` (all `Promise`-returning).

- [ ] **Step 1: Write the module**

Create `frontend/src/lib/runsApi.ts`:

```typescript
/* Sub-project 3C — Run tracking + review API layer.
 *
 * Typed wrappers around apiFetch for the run-execution endpoints:
 *   - Story 3.2 run CRUD (POST/GET /workflows/{id}/runs, GET /workflows/runs/{id})
 *   - 3C topology (GET /workflows/runs/{id}/graph)
 *   - 3B review (GET /workflows/runs/{id}/nodes, POST decision, POST rollback confirm)
 * apiFetch injects JWT + tenant headers and unwraps {data,error,meta}.
 */

import { apiFetch } from "./api";

export type RunStatus =
  | "pending"
  | "running"
  | "awaiting_human"
  | "completed"
  | "failed"
  | "timed_out"
  | "completed_with_failures";

export type NodeStatus =
  | "pending"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "rejected"
  | "skipped"
  | "rolled_back";

export interface Run {
  id: string;
  tenant_id: string;
  workflow_id: string;
  status: RunStatus;
  input: Record<string, unknown>;
  result: Record<string, unknown> | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export interface GraphNode {
  node_key: string;
  label: string;
  agent_id: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
  approver_user_ids: string[];
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface RunNodeExecution {
  id: string;
  run_id: string;
  node_key: string;
  agent_id: string;
  status: NodeStatus;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  approver_user_ids: string[];
  decision: string | null;
  decided_by: string | null;
  reason: string | null;
  guidance: string | null;
  decided_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface RollbackRequest {
  id: string;
  requester_node_key: string;
  target_node_key: string;
  reason: string | null;
  status: string;
}

export interface RunNodesResponse {
  nodes: RunNodeExecution[];
  rollbacks: { pending: RollbackRequest[]; refused: RollbackRequest[] };
}

export type DecisionAction = "approve" | "retry" | "override" | "reject";

export interface DecisionRequest {
  action: DecisionAction;
  guidance?: string;
  output?: Record<string, unknown>;
  reason?: string;
  target_node_key?: string;
}

export function createRun(
  workflowId: string,
  input: Record<string, unknown>,
): Promise<Run> {
  return apiFetch<Run>(`/workflows/${workflowId}/runs`, {
    method: "POST",
    body: JSON.stringify({ input }),
  });
}

export function listRuns(workflowId: string): Promise<Run[]> {
  return apiFetch<Run[]>(`/workflows/${workflowId}/runs`);
}

export function getRun(runId: string): Promise<Run> {
  return apiFetch<Run>(`/workflows/runs/${runId}`);
}

export function getRunGraph(runId: string): Promise<GraphSnapshot> {
  return apiFetch<GraphSnapshot>(`/workflows/runs/${runId}/graph`);
}

export function listRunNodes(runId: string): Promise<RunNodesResponse> {
  return apiFetch<RunNodesResponse>(`/workflows/runs/${runId}/nodes`);
}

export function postDecision(
  runId: string,
  nodeKey: string,
  body: DecisionRequest,
): Promise<RunNodeExecution> {
  return apiFetch<RunNodeExecution>(
    `/workflows/runs/${runId}/nodes/${nodeKey}/decision`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function confirmRollback(
  runId: string,
  rollbackId: string,
  accept: boolean,
): Promise<{ id: string; status: string }> {
  return apiFetch<{ id: string; status: string }>(
    `/workflows/runs/${runId}/rollbacks/${rollbackId}/confirm`,
    { method: "POST", body: JSON.stringify({ accept }) },
  );
}
```

- [ ] **Step 2: Verify it typechecks**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing `runsApi.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/runsApi.ts
git commit -m "feat(runs): typed run tracking + review API layer (3C)"
```

---

### Task 2.5: `runStatusMeta.ts` — status → RunState/label mapping (single source)

Maps the full backend status vocabulary onto the app's 6 `RunState` values (reused by `StatusPill`) and pretty labels, and defines the terminal-run set shared by the polling hooks. DRY: no new color system.

**Files:**
- Create: `frontend/src/lib/runStatusMeta.ts`

**Interfaces:**
- Consumes: `RunState` from `lib/icons`.
- Produces: `TERMINAL_RUN_STATUSES: readonly string[]`, `isTerminalRun(status: string): boolean`, `runStateFor(status: string): RunState`, `statusLabel(status: string): string`.

- [ ] **Step 1: Write the module**

Create `frontend/src/lib/runStatusMeta.ts`:

```typescript
/* Sub-project 3C — single source mapping backend run/node statuses onto the
 * app's 6 RunStates (lib/icons stateMapping, reused by StatusPill) + pretty
 * labels. Keeps status→color/label logic in one place (spec §4.4 deliverable).
 */

import type { RunState } from "./icons";

/** Run statuses after which polling stops (no further engine progress). */
export const TERMINAL_RUN_STATUSES = [
  "completed",
  "failed",
  "timed_out",
  "completed_with_failures",
] as const;

export function isTerminalRun(status: string): boolean {
  return (TERMINAL_RUN_STATUSES as readonly string[]).includes(status);
}

/** Map any backend run/node status to one of the 6 visual RunStates. */
export function runStateFor(status: string): RunState {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
    case "timed_out":
    case "rejected":
      return "error";
    case "awaiting_human":
    case "awaiting_approval":
    case "completed_with_failures":
      return "escalated";
    case "running":
      return "running";
    case "rolled_back":
    case "skipped":
      return "draft";
    case "pending":
    default:
      return "pending";
  }
}

/** Human-readable label for a raw status (e.g. "awaiting_approval" → "Awaiting approval"). */
export function statusLabel(status: string): string {
  const words = status.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
```

- [ ] **Step 2: Verify it typechecks**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing `runStatusMeta.ts`. (If `RunState` is not exported from `lib/icons`, the error surfaces here — it is exported as `export type RunState` at `lib/icons.tsx:100`.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/runStatusMeta.ts
git commit -m "feat(runs): status meta mapping + terminal-run set (3C)"
```

---

### Task 3: Run hooks — `useRuns`, `useRun`, `useRunGraph`, `useRunNodes`, `useRunMutations`

TanStack Query hooks. `useRunNodes`/`useRun` poll while non-terminal; mutations invalidate node/run state.

**Files:**
- Create: `frontend/src/hooks/useRuns.ts`
- Create: `frontend/src/hooks/useRunTracking.ts` (holds `useRun`, `useRunGraph`, `useRunNodes`)
- Create: `frontend/src/hooks/useRunMutations.ts`

**Interfaces:**
- Consumes: `runsApi` functions + types (Task 2), `isTerminalRun` (Task 2.5).
- Produces:
  - `useRuns(workflowId: string): UseQueryResult<Run[], Error>`.
  - `useRun(runId: string): UseQueryResult<Run, Error>` (polls ~2s while non-terminal).
  - `useRunGraph(runId: string): UseQueryResult<GraphSnapshot, Error>` (static, `staleTime: Infinity`).
  - `useRunNodes(runId: string, runStatus: string | undefined): UseQueryResult<RunNodesResponse, Error>` (polls ~2s while `runStatus` non-terminal).
  - `useRunMutations(runId: string): { decide: UseMutationResult<RunNodeExecution, Error, {nodeKey: string; body: DecisionRequest}>; confirm: UseMutationResult<{id:string;status:string}, Error, {rollbackId: string; accept: boolean}> }`.

- [ ] **Step 1: Write `useRuns.ts`**

Create `frontend/src/hooks/useRuns.ts`:

```typescript
/* 3C — Runs list for a Workflow (Runs tab). */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listRuns, type Run } from "../lib/runsApi";

export function useRuns(workflowId: string): UseQueryResult<Run[], Error> {
  return useQuery<Run[], Error>({
    queryKey: ["runs", workflowId],
    queryFn: () => listRuns(workflowId),
    enabled: Boolean(workflowId),
  });
}
```

- [ ] **Step 2: Write `useRunTracking.ts`**

Create `frontend/src/hooks/useRunTracking.ts`:

```typescript
/* 3C — Run tracking reads: run status (polled), immutable graph (once),
 * node executions + rollbacks (polled). Polling stops at a terminal run status.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  getRun,
  getRunGraph,
  listRunNodes,
  type GraphSnapshot,
  type Run,
  type RunNodesResponse,
} from "../lib/runsApi";
import { isTerminalRun } from "../lib/runStatusMeta";

const POLL_MS = 2000;

export function useRun(runId: string): UseQueryResult<Run, Error> {
  return useQuery<Run, Error>({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && isTerminalRun(status) ? false : POLL_MS;
    },
  });
}

export function useRunGraph(runId: string): UseQueryResult<GraphSnapshot, Error> {
  return useQuery<GraphSnapshot, Error>({
    queryKey: ["runGraph", runId],
    queryFn: () => getRunGraph(runId),
    enabled: Boolean(runId),
    staleTime: Infinity,
  });
}

export function useRunNodes(
  runId: string,
  runStatus: string | undefined,
): UseQueryResult<RunNodesResponse, Error> {
  const terminal = runStatus ? isTerminalRun(runStatus) : false;
  return useQuery<RunNodesResponse, Error>({
    queryKey: ["runNodes", runId],
    queryFn: () => listRunNodes(runId),
    enabled: Boolean(runId),
    refetchInterval: terminal ? false : POLL_MS,
  });
}
```

- [ ] **Step 3: Write `useRunMutations.ts`**

Create `frontend/src/hooks/useRunMutations.ts`:

```typescript
/* 3C — Node decision + rollback confirm mutations. Each invalidates the
 * run + node queries so the polled canvas reflects the new engine state
 * (the backend endpoint already re-enqueues run_workflow(resume=True)).
 */
import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";
import {
  confirmRollback,
  postDecision,
  type DecisionRequest,
  type RunNodeExecution,
} from "../lib/runsApi";

export interface UseRunMutationsResult {
  decide: UseMutationResult<
    RunNodeExecution,
    Error,
    { nodeKey: string; body: DecisionRequest }
  >;
  confirm: UseMutationResult<
    { id: string; status: string },
    Error,
    { rollbackId: string; accept: boolean }
  >;
}

export function useRunMutations(runId: string): UseRunMutationsResult {
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["runNodes", runId] });
    queryClient.invalidateQueries({ queryKey: ["run", runId] });
  };

  const decide = useMutation<
    RunNodeExecution,
    Error,
    { nodeKey: string; body: DecisionRequest }
  >({
    mutationFn: ({ nodeKey, body }) => postDecision(runId, nodeKey, body),
    onSuccess: invalidate,
  });

  const confirm = useMutation<
    { id: string; status: string },
    Error,
    { rollbackId: string; accept: boolean }
  >({
    mutationFn: ({ rollbackId, accept }) =>
      confirmRollback(runId, rollbackId, accept),
    onSuccess: invalidate,
  });

  return { decide, confirm };
}
```

- [ ] **Step 4: Verify it typechecks**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing the three hook files.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useRuns.ts frontend/src/hooks/useRunTracking.ts frontend/src/hooks/useRunMutations.ts
git commit -m "feat(runs): run tracking + mutation hooks with polling (3C)"
```

---

### Task 4: `RunStatusBadge` + merge helper

A status pill for any run/node status (reuses `StatusPill` via `runStatusMeta`), and the pure helper that merges topology with runtime node state by `node_key`.

**Files:**
- Create: `frontend/src/components/workflows/runs/RunStatusBadge.tsx`
- Create: `frontend/src/components/workflows/runs/mergeNodes.ts`

**Interfaces:**
- Consumes: `StatusPill` (ui), `runStateFor`/`statusLabel` (Task 2.5), `GraphNode`/`RunNodeExecution`/`GraphEdge` (Task 2).
- Produces:
  - `RunStatusBadge({ status }: { status: string }): JSX.Element`.
  - `MergedNode = GraphNode & { exec: RunNodeExecution | null }`.
  - `mergeNodes(graphNodes: GraphNode[], execs: RunNodeExecution[]): MergedNode[]`.
  - `parentsOf(nodeKey: string, edges: GraphEdge[]): string[]`.

- [ ] **Step 1: Write `RunStatusBadge.tsx`**

Create `frontend/src/components/workflows/runs/RunStatusBadge.tsx`:

```tsx
/* 3C — Status pill for any run/node status. Reuses the app's StatusPill by
 * mapping the full backend vocabulary onto its 6 RunStates (runStatusMeta),
 * with the raw status as the visible label.
 */
import { StatusPill } from "../../ui";
import { runStateFor, statusLabel } from "../../../lib/runStatusMeta";

export default function RunStatusBadge({ status }: { status: string }) {
  return <StatusPill state={runStateFor(status)} label={statusLabel(status)} />;
}
```

- [ ] **Step 2: Write `mergeNodes.ts`**

Create `frontend/src/components/workflows/runs/mergeNodes.ts`:

```typescript
/* 3C — pure helpers: merge immutable topology with polled runtime node state
 * by node_key, and derive a node's parents from the edge list (reject picker).
 */
import type { GraphEdge, GraphNode, RunNodeExecution } from "../../../lib/runsApi";

export type MergedNode = GraphNode & { exec: RunNodeExecution | null };

export function mergeNodes(
  graphNodes: GraphNode[],
  execs: RunNodeExecution[],
): MergedNode[] {
  const byKey = new Map(execs.map((e) => [e.node_key, e]));
  return graphNodes.map((n) => ({ ...n, exec: byKey.get(n.node_key) ?? null }));
}

export function parentsOf(nodeKey: string, edges: GraphEdge[]): string[] {
  return edges.filter((e) => e.to === nodeKey).map((e) => e.from);
}
```

- [ ] **Step 3: Verify it typechecks**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing the two new files.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workflows/runs/RunStatusBadge.tsx frontend/src/components/workflows/runs/mergeNodes.ts
git commit -m "feat(runs): status badge + node merge helpers (3C)"
```

---

### Task 5: `RunGraphCanvas` + `RunNode` — the SVG DAG

Hand-rolled canvas: node boxes positioned from stored `position`, edges as SVG paths behind them. Click a node to select. Includes a fallback grid layout when positions are missing/degenerate (spec open question).

**Files:**
- Create: `frontend/src/components/workflows/runs/layout.ts`
- Create: `frontend/src/components/workflows/runs/RunNode.tsx`
- Create: `frontend/src/components/workflows/runs/RunGraphCanvas.tsx`

**Interfaces:**
- Consumes: `MergedNode` (Task 4), `GraphEdge` (Task 2), `RunStatusBadge` (Task 4).
- Produces:
  - `NODE_W = 180`, `NODE_H = 72` (constants).
  - `layoutPositions(nodes: MergedNode[], edges: GraphEdge[]): Map<string, {x:number;y:number}>` — stored positions, or a topo-column fallback if all positions collapse.
  - `RunNode({ node, selected, hasPendingRollback, onSelect })`.
  - `RunGraphCanvas({ nodes, edges, selectedKey, onSelect, pendingRollbackKeys })`.

- [ ] **Step 1: Write `layout.ts`**

Create `frontend/src/components/workflows/runs/layout.ts`:

```typescript
/* 3C — canvas geometry. Uses stored node positions; if every node sits at the
 * same spot (missing/degenerate positions in older snapshots), falls back to a
 * BFS-depth column layout so nodes don't overlap.
 */
import type { GraphEdge } from "../../../lib/runsApi";
import type { MergedNode } from "./mergeNodes";

export const NODE_W = 180;
export const NODE_H = 72;
const COL_GAP = 240;
const ROW_GAP = 120;

function positionsCollapsed(nodes: MergedNode[]): boolean {
  if (nodes.length <= 1) return false;
  const first = nodes[0].position;
  return nodes.every(
    (n) => n.position.x === first.x && n.position.y === first.y,
  );
}

/** BFS depth (column index) per node from the roots. */
function depths(nodes: MergedNode[], edges: GraphEdge[]): Map<string, number> {
  const parents = new Map<string, number>();
  nodes.forEach((n) => parents.set(n.node_key, 0));
  edges.forEach((e) => parents.set(e.to, (parents.get(e.to) ?? 0) + 1));
  const adj = new Map<string, string[]>();
  nodes.forEach((n) => adj.set(n.node_key, []));
  edges.forEach((e) => adj.get(e.from)?.push(e.to));

  const depth = new Map<string, number>();
  const queue = nodes.filter((n) => (parents.get(n.node_key) ?? 0) === 0)
    .map((n) => n.node_key);
  queue.forEach((k) => depth.set(k, 0));
  while (queue.length) {
    const k = queue.shift() as string;
    const d = depth.get(k) ?? 0;
    for (const child of adj.get(k) ?? []) {
      if (!depth.has(child) || (depth.get(child) as number) < d + 1) {
        depth.set(child, d + 1);
        queue.push(child);
      }
    }
  }
  nodes.forEach((n) => {
    if (!depth.has(n.node_key)) depth.set(n.node_key, 0);
  });
  return depth;
}

export function layoutPositions(
  nodes: MergedNode[],
  edges: GraphEdge[],
): Map<string, { x: number; y: number }> {
  const out = new Map<string, { x: number; y: number }>();
  if (!positionsCollapsed(nodes)) {
    nodes.forEach((n) => out.set(n.node_key, { x: n.position.x, y: n.position.y }));
    return out;
  }
  const depth = depths(nodes, edges);
  const rowByCol = new Map<number, number>();
  nodes.forEach((n) => {
    const col = depth.get(n.node_key) ?? 0;
    const row = rowByCol.get(col) ?? 0;
    rowByCol.set(col, row + 1);
    out.set(n.node_key, { x: 40 + col * COL_GAP, y: 40 + row * ROW_GAP });
  });
  return out;
}
```

- [ ] **Step 2: Write `RunNode.tsx`**

Create `frontend/src/components/workflows/runs/RunNode.tsx`:

```tsx
/* 3C — one node box on the canvas. Absolutely positioned; shows label, status
 * badge, a gated indicator (has approvers), and highlights selection / pending
 * rollback. Click selects.
 */
import RunStatusBadge from "./RunStatusBadge";
import { NODE_H, NODE_W } from "./layout";
import type { MergedNode } from "./mergeNodes";

export interface RunNodeProps {
  node: MergedNode;
  x: number;
  y: number;
  selected: boolean;
  hasPendingRollback: boolean;
  onSelect: (nodeKey: string) => void;
}

export default function RunNode({
  node,
  x,
  y,
  selected,
  hasPendingRollback,
  onSelect,
}: RunNodeProps) {
  const status = node.exec?.status ?? "pending";
  const gated = node.approver_user_ids.length > 0;
  const border = hasPendingRollback
    ? "var(--color-error)"
    : selected
      ? "var(--color-accent)"
      : "var(--color-border)";
  return (
    <button
      type="button"
      data-testid={`vaic-run-node-${node.node_key}`}
      onClick={() => onSelect(node.node_key)}
      className="vaic-focusable"
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: NODE_W,
        height: NODE_H,
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1)",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "var(--space-2)",
        borderRadius: "var(--radius-md, 8px)",
        border: `2px solid ${border}`,
        background: "var(--color-surface)",
        cursor: "pointer",
        textAlign: "left",
      }}
    >
      <span className="text-body" style={{ fontWeight: 600 }}>
        {node.label || node.node_key}
        {gated ? " ●" : ""}
      </span>
      <RunStatusBadge status={status} />
    </button>
  );
}
```

- [ ] **Step 3: Write `RunGraphCanvas.tsx`**

Create `frontend/src/components/workflows/runs/RunGraphCanvas.tsx`:

```tsx
/* 3C — hand-rolled SVG DAG canvas. Edges drawn as paths (parent bottom-center
 * → child top-center) on an SVG layer; nodes are absolutely-positioned boxes
 * on top. No graph library; positions come from layout.ts.
 */
import RunNode from "./RunNode";
import { NODE_H, NODE_W, layoutPositions } from "./layout";
import type { MergedNode } from "./mergeNodes";
import type { GraphEdge } from "../../../lib/runsApi";

export interface RunGraphCanvasProps {
  nodes: MergedNode[];
  edges: GraphEdge[];
  selectedKey: string | null;
  onSelect: (nodeKey: string) => void;
  pendingRollbackKeys: Set<string>;
}

export default function RunGraphCanvas({
  nodes,
  edges,
  selectedKey,
  onSelect,
  pendingRollbackKeys,
}: RunGraphCanvasProps) {
  const pos = layoutPositions(nodes, edges);
  let maxX = 0;
  let maxY = 0;
  pos.forEach((p) => {
    maxX = Math.max(maxX, p.x + NODE_W);
    maxY = Math.max(maxY, p.y + NODE_H);
  });
  const width = maxX + 40;
  const height = maxY + 40;

  return (
    <div
      data-testid="vaic-run-graph-canvas"
      style={{
        position: "relative",
        width,
        height,
        minWidth: "100%",
        overflow: "auto",
      }}
    >
      <svg
        width={width}
        height={height}
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      >
        <defs>
          <marker
            id="vaic-arrow"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L6,3 L0,6 Z" fill="var(--color-border-strong, #888)" />
          </marker>
        </defs>
        {edges.map((e) => {
          const a = pos.get(e.from);
          const b = pos.get(e.to);
          if (!a || !b) return null;
          const x1 = a.x + NODE_W / 2;
          const y1 = a.y + NODE_H;
          const x2 = b.x + NODE_W / 2;
          const y2 = b.y;
          const midY = (y1 + y2) / 2;
          return (
            <path
              key={`${e.from}->${e.to}`}
              d={`M${x1},${y1} C${x1},${midY} ${x2},${midY} ${x2},${y2}`}
              fill="none"
              stroke="var(--color-border-strong, #888)"
              strokeWidth={1.5}
              markerEnd="url(#vaic-arrow)"
            />
          );
        })}
      </svg>
      {nodes.map((n) => {
        const p = pos.get(n.node_key) ?? { x: 0, y: 0 };
        return (
          <RunNode
            key={n.node_key}
            node={n}
            x={p.x}
            y={p.y}
            selected={selectedKey === n.node_key}
            hasPendingRollback={pendingRollbackKeys.has(n.node_key)}
            onSelect={onSelect}
          />
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Verify it typechecks**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing the three new files.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workflows/runs/layout.ts frontend/src/components/workflows/runs/RunNode.tsx frontend/src/components/workflows/runs/RunGraphCanvas.tsx
git commit -m "feat(runs): SVG DAG canvas + node + layout fallback (3C)"
```

---

### Task 6: `RunReviewPanel` + `NodeIoViewer` + `RollbackConfirmCard`

The right-side review panel: node I/O + decision history, approver-gated actions (approve/retry/override/reject with parent picker), and the rollback confirm card.

**Files:**
- Create: `frontend/src/components/workflows/runs/NodeIoViewer.tsx`
- Create: `frontend/src/components/workflows/runs/RollbackConfirmCard.tsx`
- Create: `frontend/src/components/workflows/runs/RunReviewPanel.tsx`

**Interfaces:**
- Consumes: `MergedNode`/`parentsOf` (Task 4), `RunStatusBadge` (Task 4), `useRunMutations` (Task 3), `RollbackRequest`/`DecisionRequest` (Task 2), `Button`/`FormField`/`Card`/`useToast` (ui), `useAuth`.
- Produces:
  - `NodeIoViewer({ label, value }: { label: string; value: unknown })`.
  - `RollbackConfirmCard({ rollback, onConfirm, pending }: { rollback: RollbackRequest; onConfirm: (accept: boolean) => void; pending: boolean })`.
  - `RunReviewPanel({ node, edges, rollbacks, currentUserId, mutations })`.

- [ ] **Step 1: Write `NodeIoViewer.tsx`**

Create `frontend/src/components/workflows/runs/NodeIoViewer.tsx`:

```tsx
/* 3C — read-only JSON view of a node's input/output. */
export interface NodeIoViewerProps {
  label: string;
  value: unknown;
}

export default function NodeIoViewer({ label, value }: NodeIoViewerProps) {
  const text =
    value == null ? "—" : JSON.stringify(value, null, 2);
  return (
    <div style={{ marginBottom: "var(--space-3)" }}>
      <div
        className="text-body"
        style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-1)" }}
      >
        {label}
      </div>
      <pre
        style={{
          margin: 0,
          padding: "var(--space-2)",
          background: "var(--color-surface-sunken, var(--color-surface))",
          borderRadius: "var(--radius-sm, 6px)",
          overflow: "auto",
          maxHeight: 200,
          fontSize: "0.85em",
        }}
      >
        {text}
      </pre>
    </div>
  );
}
```

- [ ] **Step 2: Write `RollbackConfirmCard.tsx`**

Create `frontend/src/components/workflows/runs/RollbackConfirmCard.tsx`:

```tsx
/* 3C — shown to a target node's approver when a rollback to that node is
 * pending: Accept (re-run subtree) / Refuse (rejecting node must Approve/
 * Retry/Override instead).
 */
import { Button, Card } from "../../ui";
import type { RollbackRequest } from "../../../lib/runsApi";

export interface RollbackConfirmCardProps {
  rollback: RollbackRequest;
  onConfirm: (accept: boolean) => void;
  pending: boolean;
}

export default function RollbackConfirmCard({
  rollback,
  onConfirm,
  pending,
}: RollbackConfirmCardProps) {
  return (
    <Card>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        <strong className="text-body">
          Rollback requested to this node
        </strong>
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          From node “{rollback.requester_node_key}”. Reason:{" "}
          {rollback.reason || "—"}
        </span>
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button
            variant="primary"
            disabled={pending}
            onClick={() => onConfirm(true)}
          >
            Accept
          </Button>
          <Button
            variant="secondary"
            disabled={pending}
            onClick={() => onConfirm(false)}
          >
            Refuse
          </Button>
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: Write `RunReviewPanel.tsx`**

Create `frontend/src/components/workflows/runs/RunReviewPanel.tsx`:

```tsx
/* 3C — review panel for the selected node. Read-only I/O + history for all;
 * decision actions only when the current user is an approver AND the node is
 * awaiting_approval. Reject offers a parent picker (parents disabled if the
 * rollback to them was already refused).
 */
import { useState } from "react";
import { Button, Card, useToast } from "../../ui";
import NodeIoViewer from "./NodeIoViewer";
import RollbackConfirmCard from "./RollbackConfirmCard";
import RunStatusBadge from "./RunStatusBadge";
import { parentsOf, type MergedNode } from "./mergeNodes";
import type {
  DecisionRequest,
  GraphEdge,
  RollbackRequest,
} from "../../../lib/runsApi";
import type { UseRunMutationsResult } from "../../../hooks/useRunMutations";

export interface RunReviewPanelProps {
  node: MergedNode | null;
  edges: GraphEdge[];
  rollbacks: { pending: RollbackRequest[]; refused: RollbackRequest[] };
  currentUserId: string | undefined;
  mutations: UseRunMutationsResult;
}

export default function RunReviewPanel({
  node,
  edges,
  rollbacks,
  currentUserId,
  mutations,
}: RunReviewPanelProps) {
  const toast = useToast();
  const [guidance, setGuidance] = useState("");
  const [overrideText, setOverrideText] = useState("{}");
  const [reason, setReason] = useState("");
  const [target, setTarget] = useState("");

  if (!node) {
    return (
      <Card>
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Select a node to review it.
        </span>
      </Card>
    );
  }

  const exec = node.exec;
  const status = exec?.status ?? "pending";
  const isApprover = Boolean(
    currentUserId && node.approver_user_ids.includes(currentUserId),
  );
  const canDecide = isApprover && status === "awaiting_approval";
  const parents = parentsOf(node.node_key, edges);
  const refusedParents = new Set(
    rollbacks.refused
      .filter((r) => r.requester_node_key === node.node_key)
      .map((r) => r.target_node_key),
  );

  // Pending rollback whose TARGET is this node → this approver confirms it.
  const pendingForThisTarget = rollbacks.pending.find(
    (r) => r.target_node_key === node.node_key,
  );

  function submit(body: DecisionRequest) {
    mutations.decide.mutate(
      { nodeKey: node!.node_key, body },
      {
        onError: (err) => toast.show?.({ variant: "error", message: err.message }),
      },
    );
  }

  function onOverride() {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(overrideText);
    } catch {
      toast.show?.({ variant: "error", message: "Override must be valid JSON" });
      return;
    }
    submit({ action: "override", output: parsed });
  }

  function onReject() {
    if (!target) {
      toast.show?.({ variant: "error", message: "Pick a parent to roll back to" });
      return;
    }
    submit({ action: "reject", reason, target_node_key: target });
  }

  const pending = mutations.decide.isPending;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Card>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <strong className="text-h3">{node.label || node.node_key}</strong>
            <RunStatusBadge status={status} />
          </div>
          <NodeIoViewer label="Input" value={exec?.input} />
          <NodeIoViewer label="Output" value={exec?.output} />
          {exec?.decision && (
            <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
              Last decision: {exec.decision}
              {exec.reason ? ` — ${exec.reason}` : ""}
            </span>
          )}
        </div>
      </Card>

      {pendingForThisTarget && isApprover && (
        <RollbackConfirmCard
          rollback={pendingForThisTarget}
          pending={mutations.confirm.isPending}
          onConfirm={(accept) =>
            mutations.confirm.mutate(
              { rollbackId: pendingForThisTarget.id, accept },
              {
                onError: (err) =>
                  toast.show?.({ variant: "error", message: err.message }),
              },
            )
          }
        />
      )}

      {canDecide && (
        <Card>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              <Button variant="primary" disabled={pending} onClick={() => submit({ action: "approve" })}>
                Approve
              </Button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <label className="text-body">Retry guidance</label>
              <textarea
                className="vaic-form-input vaic-focusable"
                value={guidance}
                onChange={(e) => setGuidance(e.target.value)}
                rows={2}
              />
              <Button
                variant="secondary"
                disabled={pending}
                onClick={() => submit({ action: "retry", guidance })}
              >
                Retry
              </Button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <label className="text-body">Override output (JSON)</label>
              <textarea
                className="vaic-form-input vaic-focusable"
                value={overrideText}
                onChange={(e) => setOverrideText(e.target.value)}
                rows={3}
              />
              <Button variant="secondary" disabled={pending} onClick={onOverride}>
                Override
              </Button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <label className="text-body">Reject → roll back to parent</label>
              <select
                className="vaic-form-input vaic-focusable"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              >
                <option value="">Select a parent…</option>
                {parents.map((p) => (
                  <option key={p} value={p} disabled={refusedParents.has(p)}>
                    {p}
                    {refusedParents.has(p) ? " (refused)" : ""}
                  </option>
                ))}
              </select>
              <textarea
                className="vaic-form-input vaic-focusable"
                placeholder="Reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
              />
              <Button variant="danger" disabled={pending} onClick={onReject}>
                Reject
              </Button>
            </div>
          </div>
        </Card>
      )}

      {!canDecide && status === "awaiting_approval" && !isApprover && (
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Awaiting another approver's decision.
        </span>
      )}
    </div>
  );
}
```

Notes for the implementer:
- `useToast()` returns the app's toast API. The exact method name may differ (`show`/`push`/`addToast`); the optional-chaining `toast.show?.(...)` is defensive — check `frontend/src/components/ui/Toast.tsx` for the real method and replace `show` throughout this file with it (drop the `?.` once confirmed). The typecheck in Step 4 will flag a wrong name.
- If the `Button` variant `"danger"` does not exist, check `frontend/src/components/ui/Button.tsx` `ButtonVariant` and use the closest destructive variant (e.g. `"secondary"`); the typecheck flags an invalid variant.
- `text-h3` class: if not present, use `text-h2` or `text-body` with `fontWeight:600` (check `frontend/src/styles`).

- [ ] **Step 4: Verify it typechecks (resolve toast/variant/class names)**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors. If errors reference the toast method, `ButtonVariant`, or a class, apply the note above and re-run until clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workflows/runs/NodeIoViewer.tsx frontend/src/components/workflows/runs/RollbackConfirmCard.tsx frontend/src/components/workflows/runs/RunReviewPanel.tsx
git commit -m "feat(runs): approver-gated review panel + rollback confirm (3C)"
```

---

### Task 7: `RunTrackingView` + `RunTrackingPage` + route

Compose canvas + review panel, wire data hooks, and register the route `/workflows/:id/runs/:runId`.

**Files:**
- Create: `frontend/src/components/workflows/runs/RunTrackingView.tsx`
- Create: `frontend/src/routes/orchestrator/RunTrackingPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `useRun`/`useRunGraph`/`useRunNodes` (Task 3), `useRunMutations` (Task 3), `mergeNodes` (Task 4), `RunGraphCanvas` (Task 5), `RunReviewPanel` (Task 6), `RunStatusBadge` (Task 4), `useAuth`, `ErrorState`/`Skeleton` (ui), `useParams` (react-router-dom).
- Produces: `RunTrackingView({ runId })`, `RunTrackingPage()` (default export, reads `:id`/`:runId` from route).

- [ ] **Step 1: Write `RunTrackingView.tsx`**

Create `frontend/src/components/workflows/runs/RunTrackingView.tsx`:

```tsx
/* 3C — run tracking: loads topology once + polls node state, merges by
 * node_key, renders the SVG canvas beside the review panel. Selecting a node
 * opens its review. Auto-selects the node awaiting approval.
 */
import { useEffect, useMemo, useState } from "react";
import { ErrorState, Skeleton } from "../../ui";
import RunGraphCanvas from "./RunGraphCanvas";
import RunReviewPanel from "./RunReviewPanel";
import RunStatusBadge from "./RunStatusBadge";
import { mergeNodes } from "./mergeNodes";
import { useRun, useRunGraph, useRunNodes } from "../../../hooks/useRunTracking";
import { useRunMutations } from "../../../hooks/useRunMutations";
import { useAuth } from "../../../hooks/useAuth";

export interface RunTrackingViewProps {
  runId: string;
}

export default function RunTrackingView({ runId }: RunTrackingViewProps) {
  const { user } = useAuth();
  const run = useRun(runId);
  const graph = useRunGraph(runId);
  const nodes = useRunNodes(runId, run.data?.status);
  const mutations = useRunMutations(runId);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const merged = useMemo(() => {
    if (!graph.data || !nodes.data) return [];
    return mergeNodes(graph.data.nodes, nodes.data.nodes);
  }, [graph.data, nodes.data]);

  // Auto-select the first node awaiting approval when nothing is selected.
  useEffect(() => {
    if (selectedKey) return;
    const awaiting = merged.find((n) => n.exec?.status === "awaiting_approval");
    if (awaiting) setSelectedKey(awaiting.node_key);
  }, [merged, selectedKey]);

  if (run.isError || graph.isError) {
    return (
      <ErrorState
        message={
          run.error?.message ?? graph.error?.message ?? "Failed to load run"
        }
      />
    );
  }
  if (run.isLoading || graph.isLoading) {
    return <Skeleton lines={6} height="24px" />;
  }

  const pendingRollbackKeys = new Set(
    (nodes.data?.rollbacks.pending ?? []).map((r) => r.target_node_key),
  );
  const selected = merged.find((n) => n.node_key === selectedKey) ?? null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <strong className="text-h2">Run</strong>
        {run.data && <RunStatusBadge status={run.data.status} />}
      </div>
      <div style={{ display: "flex", gap: "var(--space-4)", alignItems: "flex-start" }}>
        <div style={{ flex: 1, overflow: "auto", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md, 8px)" }}>
          <RunGraphCanvas
            nodes={merged}
            edges={graph.data?.edges ?? []}
            selectedKey={selectedKey}
            onSelect={setSelectedKey}
            pendingRollbackKeys={pendingRollbackKeys}
          />
        </div>
        <div style={{ width: 360, flexShrink: 0 }}>
          <RunReviewPanel
            node={selected}
            edges={graph.data?.edges ?? []}
            rollbacks={nodes.data?.rollbacks ?? { pending: [], refused: [] }}
            currentUserId={user?.id}
            mutations={mutations}
          />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `RunTrackingPage.tsx`**

Create `frontend/src/routes/orchestrator/RunTrackingPage.tsx`:

```tsx
/* 3C — route page for /workflows/:id/runs/:runId. */
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "../../components/ui";
import RunTrackingView from "../../components/workflows/runs/RunTrackingView";

export default function RunTrackingPage() {
  const { id, runId } = useParams();
  const navigate = useNavigate();
  if (!runId) return null;
  return (
    <div data-testid="vaic-run-tracking-page">
      <Button variant="ghost" onClick={() => navigate(`/workflows/${id}`)}>
        Back to Workflow
      </Button>
      <RunTrackingView runId={runId} />
    </div>
  );
}
```

- [ ] **Step 3: Register the route in `App.tsx`**

In `frontend/src/App.tsx`, add the import next to the other workflow route imports (near line 14, `import WorkflowsPage from "./routes/workflows";`):

```tsx
import RunTrackingPage from "./routes/orchestrator/RunTrackingPage";
```

And add the route next to the existing workflow routes (near line 68, after `<Route path="/workflows/:id" element={<WorkflowDetailPage />} />`):

```tsx
<Route path="/workflows/:id/runs/:runId" element={<RunTrackingPage />} />
```

- [ ] **Step 4: Verify it typechecks**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing the new files or `App.tsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workflows/runs/RunTrackingView.tsx frontend/src/routes/orchestrator/RunTrackingPage.tsx frontend/src/App.tsx
git commit -m "feat(runs): run tracking view + page + route (3C)"
```

---

### Task 8: `RunsTab` + `WorkflowDetailShell` tab bar (trigger + list)

Add a Runs tab to the workflow detail: a "New run" panel (JSON input → `createRun` → navigate to the run) and a runs table.

**Files:**
- Create: `frontend/src/components/workflows/RunsTab.tsx`
- Modify: `frontend/src/components/workflows/WorkflowDetailShell.tsx`

**Interfaces:**
- Consumes: `useRuns` (Task 3), `createRun` (Task 2), `RunStatusBadge` (Task 4), `Button`/`Table`/`EmptyState`/`ErrorState`/`Skeleton`/`useToast` (ui), `useNavigate`, `useQueryClient`.
- Produces: `RunsTab({ workflowId })`.

- [ ] **Step 1: Write `RunsTab.tsx`**

Create `frontend/src/components/workflows/RunsTab.tsx`:

```tsx
/* 3C — Runs tab: trigger a run (JSON input → POST /workflows/{id}/runs) and
 * list existing runs (row → the tracking page).
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Table, EmptyState, ErrorState, Skeleton, useToast } from "../ui";
import type { TableColumn } from "../ui";
import RunStatusBadge from "./runs/RunStatusBadge";
import { useRuns } from "../../hooks/useRuns";
import { createRun, type Run } from "../../lib/runsApi";

export interface RunsTabProps {
  workflowId: string;
}

export default function RunsTab({ workflowId }: RunsTabProps) {
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data: runs, isLoading, isError, error, refetch } = useRuns(workflowId);
  const [inputText, setInputText] = useState("{}");
  const [creating, setCreating] = useState(false);

  async function onCreate() {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(inputText);
    } catch {
      toast.show?.({ variant: "error", message: "Input must be valid JSON" });
      return;
    }
    setCreating(true);
    try {
      const run = await createRun(workflowId, parsed);
      queryClient.invalidateQueries({ queryKey: ["runs", workflowId] });
      navigate(`/workflows/${workflowId}/runs/${run.id}`);
    } catch (e) {
      toast.show?.({ variant: "error", message: (e as Error).message });
    } finally {
      setCreating(false);
    }
  }

  const columns: TableColumn<Run>[] = [
    {
      key: "status",
      header: "Status",
      render: (row) => <RunStatusBadge status={row.status} />,
    },
    {
      key: "created_at",
      header: "Created",
      render: (row) => new Date(row.created_at).toLocaleString(),
    },
    {
      key: "ended_at",
      header: "Ended",
      render: (row) => (row.ended_at ? new Date(row.ended_at).toLocaleString() : "—"),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label className="text-body">New run input (JSON)</label>
        <textarea
          className="vaic-form-input vaic-focusable"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          rows={3}
        />
        <div>
          <Button variant="primary" disabled={creating} onClick={onCreate}>
            Run
          </Button>
        </div>
      </div>

      {isError ? (
        <ErrorState
          message={error?.message ?? "Failed to load runs"}
          retry={
            <Button variant="secondary" onClick={() => refetch()}>
              Retry
            </Button>
          }
        />
      ) : isLoading ? (
        <Skeleton height="40px" />
      ) : (
        <Table
          columns={columns}
          rows={runs ?? []}
          rowId={(row) => row.id}
          onRowClick={(row) => navigate(`/workflows/${workflowId}/runs/${row.id}`)}
          emptyState={<EmptyState title="No runs yet." description="Trigger a run above." />}
        />
      )}
    </div>
  );
}
```

(Same toast-method caveat as Task 6: confirm the real method name in `Toast.tsx` and replace `show`.)

- [ ] **Step 2: Add the tab bar to `WorkflowDetailShell.tsx`**

In `frontend/src/components/workflows/WorkflowDetailShell.tsx`, import `RunsTab` and add tab state. Add near the other imports:

```tsx
import RunsTab from "./RunsTab";
```

Add tab state after the existing `const [isDirty, setIsDirty] = useState(false);`:

```tsx
const [tab, setTab] = useState<"definition" | "runs">("definition");
```

Replace the block that renders `<DefinitionTab ... />` (the `{(isNew || (!isError && !isLoading)) && (...)}` region) with a tab bar + conditional body. The `Runs` tab is disabled for an unsaved new workflow (no id yet):

```tsx
{(isNew || (!isError && !isLoading)) && (
  <>
    <div
      role="tablist"
      style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}
    >
      <Button
        variant={tab === "definition" ? "primary" : "ghost"}
        onClick={() => setTab("definition")}
      >
        Definition
      </Button>
      <Button
        variant={tab === "runs" ? "primary" : "ghost"}
        disabled={isNew}
        onClick={() => setTab("runs")}
      >
        Runs
      </Button>
    </div>

    {tab === "definition" ? (
      <DefinitionTab
        workflowId={workflowId}
        isNew={isNew}
        workflow={workflow}
        onDirtyChange={setIsDirty}
        onSaved={handleSaved}
      />
    ) : (
      <RunsTab workflowId={workflowId} />
    )}
  </>
)}
```

(`Button` is already imported in this file — confirm; it is imported from `../ui` at the top.)

- [ ] **Step 3: Verify it typechecks**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing `RunsTab.tsx` or `WorkflowDetailShell.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workflows/RunsTab.tsx frontend/src/components/workflows/WorkflowDetailShell.tsx
git commit -m "feat(runs): Runs tab with trigger + list on workflow detail (3C)"
```

---

### Task 9: End-to-end manual verification (acceptance gate)

Drive the full flow in a browser. Not auto-run (needs the stack up: Postgres + Redis + backend + arq worker + frontend, and `alembic upgrade head` applied — the 3B/3A migrations must be current, head `d5e6f7a8b9c0`).

**Files:** none (verification only).

- [ ] **Step 1: Bring up the stack**

Start Postgres + Redis, apply migrations, start backend, arq worker, and the frontend dev server per the repo's usual dev commands (see `docs/deployment-guide.md` / `backend` README). Confirm `alembic current` shows `d5e6f7a8b9c0`.

- [ ] **Step 2: Exercise the flow**

In the browser:
1. Open a workflow that has a graph definition (nodes + edges + at least one gated node with your user as approver). Go to the **Runs** tab.
2. Enter `{}` (or valid input JSON) and click **Run** → you land on `/workflows/:id/runs/:runId`.
3. Watch the canvas: nodes advance `pending → running → completed`; the gated node reaches **Awaiting approval** and auto-selects in the review panel.
4. **Approve** → the run continues; polling reflects the next node.
5. Trigger another run; at the gated node choose **Reject → parent**, give a reason. Confirm a pending-rollback indicator appears on the target node; as that parent's approver, **Accept** → the subtree resets to `pending` and re-runs.
6. Confirm the run reaches a terminal status and polling stops (network tab: `/nodes` requests cease).

Expected: each step behaves as described; no console errors; 403/409 on a non-approver or already-decided node surface as an inline error and the canvas refetches.

- [ ] **Step 3: Commit (docs note, if any tweaks were needed)**

If Step 2 surfaced small fixes, they were committed under their task. No commit if clean.

---

## Notes for the executor

- **Typecheck as smoke:** `npx tsc --noEmit` from `frontend/` is the per-task check (the frontend analog of 3B's Python import smoke). Per project preference, no lint/build/format is auto-run; skip typecheck only if doing an equivalent manual check.
- **Toast API name (Tasks 6 & 8):** `useToast()`'s method is referenced as `toast.show?.(...)`. Open `frontend/src/components/ui/Toast.tsx`, find the real method, replace `show` with it, and drop the optional-chaining once confirmed. This is the one known name to verify against the codebase.
- **Button variants / text classes:** `variant="danger"` and `text-h2`/`text-h3` are assumed; if the typecheck or styles disagree, use the nearest existing variant/class (see `Button.tsx` `ButtonVariant` and `styles/`).
- **Migration:** `alembic upgrade head` is NOT a task step (project preference: no auto build steps). Apply it manually before Task 9.

## Open questions

- **Run input dialog:** the plan uses a plain JSON textarea (matches the lenient backend). If the demo needs a friendlier typed form, that's a follow-up.
- **Missing/degenerate node positions:** handled by `layout.ts`'s BFS-column fallback (spec open question resolved: fallback included, not deferred).
- **Concurrent approvers:** first-wins is server-side; the UI just refetches on 409. No client coordination added (confirmed acceptable in the spec).
