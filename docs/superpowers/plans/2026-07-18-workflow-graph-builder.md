# Workflow Graph Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give workflows a visual DAG authoring surface — a React Flow "Graph" tab that adds agent-bound nodes, connects parent→child edges, assigns per-node human approvers, and persists via a whole-graph replace endpoint.

**Architecture:** Backend adds `graph_authoring.py` (serialize + transactional replace, gated by the existing `assert_valid_graph`) and two routes on the existing `/workflows` router. Frontend adds a React Flow editor as a third tab on `WorkflowDetailShell`, backed by thin API wrappers + TanStack Query hooks, with pure RF⇄API mappers isolated for testability. The approver picker reuses the existing `GET /auth/users`.

**Tech Stack:** FastAPI + SQLAlchemy (Python 3.13) backend; React 19 + TypeScript + Vite + TanStack Query frontend; new dependency `@xyflow/react` (React Flow) for the editor canvas.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-18-workflow-graph-builder-design.md` (Sub-project 3D).
- **Testing:** Per project working-preference in `CLAUDE.md`, do NOT write automated tests or auto-run typecheck/lint/build unless the user asks. Each task's verification is a concrete manual/behavioral check. Automated-test stubs are listed as OPTIONAL and only added on request.
- Backend envelope: success `{data, error: null, meta: {}}` via `_ok(...)`; errors flow through `core/errors.py` handlers (raise `AuthorizationError` / `NotFoundError` / new `GraphValidationError` mapping).
- Role gate: graph mutation requires `role == "builder"` (mirror `create_workflow`: `raise AuthorizationError("...", code="FORBIDDEN")`).
- Tenant: domain functions read `tenant_context.get()` — never accept `tenant_id` as an argument. RLS enforces isolation on the session.
- DAG rules are owned by `app/modules/orchestrator/graph_validation.assert_valid_graph` — the single backend gate. Never reimplement the rules server-side.
- Edges carry only `from`/`to` (`node_key`s). No field-mapping (3A whole-output-merge convention).
- Node `node_key`: unique per workflow, referenced by edges. Auto-generated (`n1`, `n2`…), user-editable with a uniqueness guard.
- Frontend files stay < 200 lines; kebab-case, self-documenting names; reuse existing `ui/` tokens and patterns.

---

## File Structure

**Backend (create):**
- `backend/app/modules/orchestrator/graph_authoring.py` — `serialize_workflow_graph`, `replace_workflow_graph`.

**Backend (modify):**
- `backend/app/modules/orchestrator/routes.py` — add `GET`/`PUT /workflows/{id}/graph-definition` + request schemas.

**Frontend (create):**
- `frontend/src/lib/workflowGraphApi.ts` — types + `getWorkflowGraph` / `putWorkflowGraph`.
- `frontend/src/lib/usersApi.ts` — `TenantUser` + `listUsers` (→ `GET /auth/users`).
- `frontend/src/hooks/useUsers.ts` — users query.
- `frontend/src/hooks/useWorkflowGraph.ts` — graph query.
- `frontend/src/hooks/useWorkflowGraphMutation.ts` — `PUT` mutation.
- `frontend/src/lib/graphEditorState.ts` — pure mappers + client validation.
- `frontend/src/components/workflows/graph/AgentNode.tsx` — custom RF node.
- `frontend/src/components/workflows/graph/GraphEditor.tsx` — RF canvas.
- `frontend/src/components/workflows/graph/NodeInspector.tsx` — selected-node panel.
- `frontend/src/components/workflows/graph/GraphToolbar.tsx` — add/delete/save/reset.
- `frontend/src/components/workflows/graph/GraphTab.tsx` — tab container + state owner.

**Frontend (modify):**
- `frontend/src/components/workflows/WorkflowDetailShell.tsx` — add third tab `"graph"`.
- `frontend/package.json` — add `@xyflow/react`.

---

## Task 1: Backend graph-authoring service

**Files:**
- Create: `backend/app/modules/orchestrator/graph_authoring.py`

**Interfaces:**
- Consumes: `assert_valid_graph`, `GraphValidationError` (`graph_validation`); models `Workflow`, `WorkflowNode`, `WorkflowEdge`, `WorkflowNodeApprover` (`orchestrator.models`); `tenant_context` (`core.tenant_context`); `NotFoundError`, `AuthorizationError` (`core.errors`).
- Produces:
  - `serialize_workflow_graph(session: Session, workflow_id: uuid.UUID) -> dict` → `{"nodes": [...], "edges": [...]}` (same node shape as `build_graph_snapshot`, plus empty-graph = `{"nodes": [], "edges": []}`).
  - `replace_workflow_graph(session, workflow_id, *, role, nodes, edges) -> dict` where `nodes: list[dict]` each `{node_key,label,agent_id,config,position:{x,y},approver_user_ids}` and `edges: list[dict]` each `{from,to}`; returns the re-serialized graph.

- [ ] **Step 1: Create the module with the read serializer**

```python
"""Author (create/replace) a workflow's DAG definition (Sub-project 3D).

Distinct from `graph_snapshot.py` (which freezes the live graph INTO a run):
this reads/writes the live `workflow_nodes`/`workflow_edges`/`_approvers`
authoring tables. `assert_valid_graph` is the single DAG gate for every write.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import AuthorizationError, NotFoundError
from app.core.tenant_context import tenant_context
from app.modules.orchestrator.graph_validation import (
    GraphValidationError,
    assert_valid_graph,
)
from app.modules.orchestrator.models import (
    Workflow,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeApprover,
)

__all__ = ["serialize_workflow_graph", "replace_workflow_graph"]


def _load_workflow(session: Session, workflow_id: uuid.UUID) -> Workflow:
    workflow = session.get(Workflow, workflow_id)
    if workflow is None:
        raise NotFoundError("Workflow not found")
    return workflow


def serialize_workflow_graph(session: Session, workflow_id: uuid.UUID) -> dict[str, Any]:
    """Read the live authored graph for the editor. Empty graph -> empty lists."""
    _load_workflow(session, workflow_id)  # RLS 404s cross-tenant
    nodes = list(
        session.execute(
            select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
        ).scalars().all()
    )
    edges = list(
        session.execute(
            select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        ).scalars().all()
    )
    node_by_id = {n.id: n for n in nodes}
    approvers = list(
        session.execute(
            select(WorkflowNodeApprover).where(
                WorkflowNodeApprover.node_id.in_([n.id for n in nodes] or [uuid.uuid4()])
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
        "edges": [
            {
                "from": node_by_id[e.from_node_id].node_key,
                "to": node_by_id[e.to_node_id].node_key,
            }
            for e in edges
            if e.from_node_id in node_by_id and e.to_node_id in node_by_id
        ],
    }
```

- [ ] **Step 2: Add the transactional replace**

```python
def replace_workflow_graph(
    session: Session,
    workflow_id: uuid.UUID,
    *,
    role: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate + rewrite the whole graph in one transaction; bump version.

    Requires builder role. Raises GraphValidationError (mapped to 422 by the
    route) on a malformed DAG. Edges reference node_key; stored as node ids.
    """
    if role != "builder":
        raise AuthorizationError(
            "builder role required to edit a Workflow graph", code="FORBIDDEN"
        )
    workflow = _load_workflow(session, workflow_id)
    tenant_id = tenant_context.get()

    node_keys = [n["node_key"] for n in nodes]
    edge_pairs = [(e["from"], e["to"]) for e in edges]
    assert_valid_graph(node_keys, edge_pairs)  # cycle/self-loop/dup/unknown-key
    for n in nodes:
        if not n.get("agent_id"):
            raise GraphValidationError(f"node {n['node_key']!r} has no agent")

    # Wipe existing graph for this workflow (approvers first via node ids).
    existing_ids = list(
        session.execute(
            select(WorkflowNode.id).where(WorkflowNode.workflow_id == workflow_id)
        ).scalars().all()
    )
    if existing_ids:
        session.execute(
            delete(WorkflowNodeApprover).where(
                WorkflowNodeApprover.node_id.in_(existing_ids)
            )
        )
    session.execute(delete(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id))
    session.execute(delete(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id))

    key_to_id: dict[str, uuid.UUID] = {}
    for n in nodes:
        pos = n.get("position") or {}
        row = WorkflowNode(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            node_key=n["node_key"],
            label=n["label"],
            agent_id=uuid.UUID(str(n["agent_id"])),
            config=n.get("config") or {},
            position_x=float(pos.get("x", 0)),
            position_y=float(pos.get("y", 0)),
        )
        session.add(row)
        session.flush()  # assign row.id
        key_to_id[n["node_key"]] = row.id
        for uid in n.get("approver_user_ids") or []:
            session.add(
                WorkflowNodeApprover(
                    node_id=row.id, user_id=uuid.UUID(str(uid)), tenant_id=tenant_id
                )
            )
    for src, dst in edge_pairs:
        session.add(
            WorkflowEdge(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                from_node_id=key_to_id[src],
                to_node_id=key_to_id[dst],
            )
        )

    workflow.version += 1
    session.commit()
    return serialize_workflow_graph(session, workflow_id)
```

- [ ] **Step 3: Verify import + syntax**

Run: `cd backend && uv run python -c "import app.modules.orchestrator.graph_authoring as m; print(sorted(m.__all__))"`
Expected: `['replace_workflow_graph', 'serialize_workflow_graph']` with no import error.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/orchestrator/graph_authoring.py
git commit -m "feat(orchestrator): graph-authoring service (serialize + transactional replace)"
```

- [ ] **Step 5 (OPTIONAL, on request): Add pytest** covering `replace_workflow_graph` version-bump + round-trip and a cycle raising `GraphValidationError`, in `backend/tests/modules/orchestrator/test_graph_authoring.py`.

---

## Task 2: Backend graph-definition routes

**Files:**
- Modify: `backend/app/modules/orchestrator/routes.py`

**Interfaces:**
- Consumes: `serialize_workflow_graph`, `replace_workflow_graph` (Task 1); `GraphValidationError` (`graph_validation`); existing `_ok`, `_principal`, `router`, `get_tenant_session`.
- Produces: `GET /workflows/{workflow_id}/graph-definition` (200, `{nodes,edges}`); `PUT /workflows/{workflow_id}/graph-definition` (200, `{nodes,edges}`; 422 on invalid DAG; 403 non-builder).

- [ ] **Step 1: Add imports + request schemas**

At the top import block, add:

```python
from app.modules.orchestrator.graph_authoring import (
    replace_workflow_graph,
    serialize_workflow_graph,
)
from app.modules.orchestrator.graph_validation import GraphValidationError
```

Below `CreateRunRequest`, add:

```python
class GraphNodeIn(BaseModel):
    node_key: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=255)
    agent_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] = Field(default_factory=dict)
    approver_user_ids: list[str] = Field(default_factory=list)


class GraphEdgeIn(BaseModel):
    from_: str = Field(..., alias="from")
    to: str

    model_config = {"populate_by_name": True}


class GraphDefinitionRequest(BaseModel):
    nodes: list[GraphNodeIn] = Field(default_factory=list)
    edges: list[GraphEdgeIn] = Field(default_factory=list)
```

- [ ] **Step 2: Add the two routes**

Add after the run-graph route (`get_run_graph_route`):

```python
@router.get("/{workflow_id}/graph-definition")
def get_graph_definition_route(
    workflow_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """GET /workflows/{id}/graph-definition — the authored DAG for the editor."""
    return JSONResponse(
        status_code=200, content=_ok(serialize_workflow_graph(session, workflow_id))
    )


@router.put("/{workflow_id}/graph-definition")
def put_graph_definition_route(
    workflow_id: uuid.UUID,
    body: GraphDefinitionRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """PUT /workflows/{id}/graph-definition — replace the whole DAG (builder only)."""
    principal = _principal(request)
    try:
        data = replace_workflow_graph(
            session,
            workflow_id,
            role=principal.role,
            nodes=[n.model_dump() for n in body.nodes],
            edges=[{"from": e.from_, "to": e.to} for e in body.edges],
        )
    except GraphValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={"data": None, "error": {"message": str(exc)}, "meta": {}},
        )
    return JSONResponse(status_code=200, content=_ok(data))
```

- [ ] **Step 3: Verify the routes register**

Run: `cd backend && uv run python -c "from app.main import app; print([r.path for r in app.routes if 'graph-definition' in getattr(r,'path','')])"`
Expected: both `/workflows/{workflow_id}/graph-definition` paths listed.

- [ ] **Step 4: Manual smoke (with the stack running per README)**

With backend up and a Builder JWT (`$TOKEN`) + a workflow id (`$WF`):
```bash
curl -s -X PUT localhost:8000/workflows/$WF/graph-definition \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"nodes":[{"node_key":"n1","label":"Extract","agent_id":"'$AGENT'","position":{"x":40,"y":80}}],"edges":[]}'
curl -s localhost:8000/workflows/$WF/graph-definition -H "Authorization: Bearer $TOKEN"
```
Expected: PUT returns the node echoed with `version` bumped on the workflow; GET returns the same `{nodes,edges}`. A self-loop edge (`{"from":"n1","to":"n1"}`) returns HTTP 422 with a `self-loop` message.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/orchestrator/routes.py
git commit -m "feat(orchestrator): GET/PUT /workflows/{id}/graph-definition"
```

---

## Task 3: Install React Flow + graph API layer

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/lib/workflowGraphApi.ts`

**Interfaces:**
- Consumes: `apiFetch` (`lib/api`).
- Produces: types `GraphDefinitionNode`, `GraphDefinitionEdge`, `GraphDefinition`; `getWorkflowGraph(id)`, `putWorkflowGraph(id, def)`.

- [ ] **Step 1: Install the dependency**

Run: `cd frontend && npm install @xyflow/react`
Expected: `@xyflow/react` appears under `dependencies` in `package.json`.

- [ ] **Step 2: Create the API wrapper**

```typescript
/* 3D — Workflow graph authoring API (GET/PUT /workflows/{id}/graph-definition).
 * Distinct from runsApi's run-graph read; this is the editable definition. */

import { apiFetch } from "./api";

export interface GraphDefinitionNode {
  node_key: string;
  label: string;
  agent_id: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
  approver_user_ids: string[];
}

export interface GraphDefinitionEdge {
  from: string;
  to: string;
}

export interface GraphDefinition {
  nodes: GraphDefinitionNode[];
  edges: GraphDefinitionEdge[];
}

export function getWorkflowGraph(workflowId: string): Promise<GraphDefinition> {
  return apiFetch<GraphDefinition>(`/workflows/${workflowId}/graph-definition`);
}

export function putWorkflowGraph(
  workflowId: string,
  def: GraphDefinition,
): Promise<GraphDefinition> {
  return apiFetch<GraphDefinition>(`/workflows/${workflowId}/graph-definition`, {
    method: "PUT",
    body: JSON.stringify(def),
  });
}
```

- [ ] **Step 3: Verify typecheck of the new file (optional per prefs)**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors referencing `workflowGraphApi.ts`.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/workflowGraphApi.ts
git commit -m "feat(workflows): install React Flow + graph-definition API wrapper"
```

---

## Task 4: Users API + hook (approver picker source)

**Files:**
- Create: `frontend/src/lib/usersApi.ts`
- Create: `frontend/src/hooks/useUsers.ts`

**Interfaces:**
- Consumes: `apiFetch`; `useQuery` (TanStack).
- Produces: type `TenantUser`; `listUsers()`; `useUsers(): UseQueryResult<TenantUser[], Error>`.

- [ ] **Step 1: Create `usersApi.ts`**

```typescript
/* 3D — tenant users list for the node approver picker.
 * Reuses the existing GET /auth/users (list_tenant_users, RLS-scoped). */

import { apiFetch } from "./api";

export interface TenantUser {
  id: string;
  email: string;
  department_id: string | null;
  role: string;
}

export function listUsers(): Promise<TenantUser[]> {
  return apiFetch<TenantUser[]>("/auth/users");
}
```

- [ ] **Step 2: Create `useUsers.ts`**

```typescript
/* 3D — tenant users query (long staleTime; the roster changes rarely). */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listUsers, type TenantUser } from "../lib/usersApi";

export function useUsers(): UseQueryResult<TenantUser[], Error> {
  return useQuery<TenantUser[], Error>({
    queryKey: ["users"],
    queryFn: listUsers,
    staleTime: 5 * 60 * 1000,
  });
}
```

- [ ] **Step 3: Verify** the app's login flow already grants access — `GET /auth/users` is a protected route (any tenant member). No new backend work.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/usersApi.ts frontend/src/hooks/useUsers.ts
git commit -m "feat(workflows): tenant users API + hook for approver picker"
```

---

## Task 5: Graph query + mutation hooks

**Files:**
- Create: `frontend/src/hooks/useWorkflowGraph.ts`
- Create: `frontend/src/hooks/useWorkflowGraphMutation.ts`

**Interfaces:**
- Consumes: `getWorkflowGraph`, `putWorkflowGraph`, `GraphDefinition` (Task 3); TanStack `useQuery` / `useMutation` / `useQueryClient`.
- Produces: `useWorkflowGraph(workflowId): UseQueryResult<GraphDefinition, Error>`; `useWorkflowGraphMutation(workflowId)` → object with `mutateAsync(def)` and `isPending`.

- [ ] **Step 1: Create `useWorkflowGraph.ts`**

```typescript
/* 3D — load the authored graph for the editor. */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getWorkflowGraph, type GraphDefinition } from "../lib/workflowGraphApi";

export function useWorkflowGraph(
  workflowId: string | undefined,
): UseQueryResult<GraphDefinition, Error> {
  return useQuery<GraphDefinition, Error>({
    queryKey: ["workflowGraph", workflowId],
    queryFn: () => getWorkflowGraph(workflowId as string),
    enabled: Boolean(workflowId),
    staleTime: 30 * 1000,
  });
}
```

- [ ] **Step 2: Create `useWorkflowGraphMutation.ts`**

```typescript
/* 3D — persist the whole graph (PUT); invalidate graph + workflow (version++). */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { putWorkflowGraph, type GraphDefinition } from "../lib/workflowGraphApi";

export function useWorkflowGraphMutation(workflowId: string) {
  const queryClient = useQueryClient();
  const mutation = useMutation<GraphDefinition, Error, GraphDefinition>({
    mutationFn: (def) => putWorkflowGraph(workflowId, def),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflowGraph", workflowId] });
      queryClient.invalidateQueries({ queryKey: ["workflow", workflowId] });
    },
  });
  return { mutateAsync: mutation.mutateAsync, isPending: mutation.isPending };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useWorkflowGraph.ts frontend/src/hooks/useWorkflowGraphMutation.ts
git commit -m "feat(workflows): graph query + replace mutation hooks"
```

---

## Task 6: Pure editor-state mappers + client validation

**Files:**
- Create: `frontend/src/lib/graphEditorState.ts`

**Interfaces:**
- Consumes: `GraphDefinition`, `GraphDefinitionNode` (Task 3); React Flow types `Node`, `Edge` (`@xyflow/react`).
- Produces:
  - `RFNodeData` interface (`{ label, agentId, nodeKey, approverUserIds }`).
  - `toReactFlow(def): { nodes: Node<RFNodeData>[]; edges: Edge[] }`.
  - `toDefinition(nodes, edges): GraphDefinition`.
  - `nextNodeKey(existingKeys: string[]): string`.
  - `validateGraph(def): string | null` (null = valid; else first error message).

- [ ] **Step 1: Create the mappers + validation**

```typescript
/* 3D — pure transforms between React Flow state and the API GraphDefinition,
 * plus a client-side mirror of assert_valid_graph for pre-Save feedback.
 * No React here so it is trivially unit-testable. */

import type { Node, Edge } from "@xyflow/react";
import type { GraphDefinition } from "./workflowGraphApi";

export interface RFNodeData extends Record<string, unknown> {
  label: string;
  agentId: string;
  nodeKey: string;
  approverUserIds: string[];
}

export function toReactFlow(def: GraphDefinition): {
  nodes: Node<RFNodeData>[];
  edges: Edge[];
} {
  const nodes = def.nodes.map((n) => ({
    id: n.node_key,
    type: "agent",
    position: { x: n.position.x, y: n.position.y },
    data: {
      label: n.label,
      agentId: n.agent_id,
      nodeKey: n.node_key,
      approverUserIds: n.approver_user_ids,
    },
  }));
  const edges = def.edges.map((e) => ({
    id: `${e.from}->${e.to}`,
    source: e.from,
    target: e.to,
  }));
  return { nodes, edges };
}

export function toDefinition(
  nodes: Node<RFNodeData>[],
  edges: Edge[],
): GraphDefinition {
  return {
    nodes: nodes.map((n) => ({
      node_key: n.data.nodeKey,
      label: n.data.label,
      agent_id: n.data.agentId,
      config: {},
      position: { x: n.position.x, y: n.position.y },
      approver_user_ids: n.data.approverUserIds,
    })),
    edges: edges.map((e) => ({ from: e.source, to: e.target })),
  };
}

export function nextNodeKey(existingKeys: string[]): string {
  let i = existingKeys.length + 1;
  const set = new Set(existingKeys);
  while (set.has(`n${i}`)) i += 1;
  return `n${i}`;
}

/** Mirror of assert_valid_graph: returns the first error message, or null. */
export function validateGraph(def: GraphDefinition): string | null {
  const keys = def.nodes.map((n) => n.node_key);
  const seen = new Set<string>();
  for (const k of keys) {
    if (!k) return "a node has an empty key";
    if (seen.has(k)) return `duplicate node key: ${k}`;
    seen.add(k);
  }
  for (const n of def.nodes) {
    if (!n.agent_id) return `node "${n.node_key}" has no agent`;
  }
  const edgeSeen = new Set<string>();
  for (const e of def.edges) {
    if (!seen.has(e.from)) return `edge from unknown node: ${e.from}`;
    if (!seen.has(e.to)) return `edge to unknown node: ${e.to}`;
    if (e.from === e.to) return `self-loop on node: ${e.from}`;
    const id = `${e.from}->${e.to}`;
    if (edgeSeen.has(id)) return `duplicate edge: ${e.from} -> ${e.to}`;
    edgeSeen.add(id);
  }
  // Kahn cycle check.
  const indeg = new Map(keys.map((k) => [k, 0]));
  const adj = new Map<string, string[]>(keys.map((k) => [k, []]));
  for (const e of def.edges) {
    indeg.set(e.to, (indeg.get(e.to) ?? 0) + 1);
    adj.get(e.from)?.push(e.to);
  }
  const queue = keys.filter((k) => (indeg.get(k) ?? 0) === 0);
  let consumed = 0;
  while (queue.length) {
    const k = queue.shift() as string;
    consumed += 1;
    for (const c of adj.get(k) ?? []) {
      indeg.set(c, (indeg.get(c) ?? 0) - 1);
      if ((indeg.get(c) ?? 0) === 0) queue.push(c);
    }
  }
  if (consumed !== keys.length) return "graph contains a cycle";
  return null;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/graphEditorState.ts
git commit -m "feat(workflows): pure RF<->API graph mappers + client DAG validation"
```

- [ ] **Step 3 (OPTIONAL, on request): Add vitest** round-tripping `toReactFlow`/`toDefinition` and asserting `validateGraph` catches a cycle/self-loop, in `frontend/src/lib/graphEditorState.test.ts`.

---

## Task 7: Custom node + React Flow canvas

**Files:**
- Create: `frontend/src/components/workflows/graph/AgentNode.tsx`
- Create: `frontend/src/components/workflows/graph/GraphEditor.tsx`

**Interfaces:**
- Consumes: `RFNodeData` (Task 6); `@xyflow/react` (`ReactFlow`, `Background`, `Controls`, `Handle`, `Position`, change/connect helpers, types); `useAgents` (`hooks/useAgents`).
- Produces:
  - `AgentNode` (registered as node type `"agent"`).
  - `GraphEditor` props `{ nodes, edges, onNodesChange, onEdgesChange, onConnect, onSelectNode, selectedNodeId }` — a controlled RF canvas.

- [ ] **Step 1: Create `AgentNode.tsx`**

```tsx
/* 3D — custom React Flow node: label + bound-agent name + gated badge. */
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { RFNodeData } from "../../../lib/graphEditorState";

export default function AgentNode({ data, selected }: NodeProps<RFNodeData>) {
  const gated = (data.approverUserIds?.length ?? 0) > 0;
  return (
    <div
      style={{
        width: 180,
        padding: "8px 10px",
        borderRadius: 8,
        border: `1px solid var(--color-border${selected ? "-strong" : ""}, #888)`,
        background: "var(--color-surface, #fff)",
        fontSize: 13,
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ fontWeight: 600 }}>{data.label || data.nodeKey}</div>
      <div style={{ opacity: 0.7, fontSize: 11 }}>{data.nodeKey}</div>
      {gated && (
        <div style={{ marginTop: 4, fontSize: 11, color: "var(--color-warning, #b45309)" }}>
          ● human-gated
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

- [ ] **Step 2: Create `GraphEditor.tsx`**

```tsx
/* 3D — controlled React Flow canvas. Parent (GraphTab) owns node/edge state;
 * this renders it, wires change/connect handlers, and reports selection. */
import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import AgentNode from "./AgentNode";
import type { RFNodeData } from "../../../lib/graphEditorState";

export interface GraphEditorProps {
  nodes: Node<RFNodeData>[];
  edges: Edge[];
  onNodesChange: OnNodesChange<Node<RFNodeData>>;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  onSelectNode: (id: string | null) => void;
}

export default function GraphEditor({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onSelectNode,
}: GraphEditorProps) {
  const nodeTypes = useMemo(() => ({ agent: AgentNode }), []);
  return (
    <div style={{ height: 520, border: "1px solid var(--color-border)", borderRadius: 8 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, n) => onSelectNode(n.id)}
        onPaneClick={() => onSelectNode(null)}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workflows/graph/AgentNode.tsx frontend/src/components/workflows/graph/GraphEditor.tsx
git commit -m "feat(workflows): React Flow canvas + custom agent node"
```

---

## Task 8: Node inspector + toolbar

**Files:**
- Create: `frontend/src/components/workflows/graph/NodeInspector.tsx`
- Create: `frontend/src/components/workflows/graph/GraphToolbar.tsx`

**Interfaces:**
- Consumes: `RFNodeData` (Task 6); `Node` (`@xyflow/react`); `useAgents`; `useUsers` (Task 4); `Button` (`components/ui`).
- Produces:
  - `NodeInspector` props `{ node, onChange(patch: Partial<RFNodeData>), onDelete() }`.
  - `GraphToolbar` props `{ onAddNode, onDeleteSelected, onSave, onReset, saving, dirty, error }`.

- [ ] **Step 1: Create `NodeInspector.tsx`**

```tsx
/* 3D — right panel: edit the selected node (label, key, agent, approvers). */
import { useAgents } from "../../../hooks/useAgents";
import { useUsers } from "../../../hooks/useUsers";
import { Button } from "../../ui";
import type { Node } from "@xyflow/react";
import type { RFNodeData } from "../../../lib/graphEditorState";

export interface NodeInspectorProps {
  node: Node<RFNodeData> | null;
  onChange: (patch: Partial<RFNodeData>) => void;
  onDelete: () => void;
}

export default function NodeInspector({ node, onChange, onDelete }: NodeInspectorProps) {
  const agents = useAgents({});
  const users = useUsers();
  if (!node) {
    return <div style={{ opacity: 0.6 }}>Select a node to edit, or add one.</div>;
  }
  const d = node.data;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <label className="vaic-form-label">Label</label>
      <input
        className="vaic-form-input vaic-focusable"
        value={d.label}
        onChange={(e) => onChange({ label: e.target.value })}
      />
      <label className="vaic-form-label">Node key</label>
      <input
        className="vaic-form-input vaic-focusable"
        value={d.nodeKey}
        onChange={(e) => onChange({ nodeKey: e.target.value })}
      />
      <label className="vaic-form-label">Agent</label>
      <select
        className="vaic-form-input vaic-focusable"
        value={d.agentId}
        onChange={(e) => onChange({ agentId: e.target.value })}
      >
        <option value="">— choose agent —</option>
        {(agents.data ?? []).map((a) => (
          <option key={a.id} value={a.id}>{a.name}</option>
        ))}
      </select>
      <label className="vaic-form-label">Approvers (none = auto)</label>
      <select
        multiple
        className="vaic-form-input vaic-focusable"
        value={d.approverUserIds}
        onChange={(e) =>
          onChange({
            approverUserIds: Array.from(e.target.selectedOptions, (o) => o.value),
          })
        }
      >
        {(users.data ?? []).map((u) => (
          <option key={u.id} value={u.id}>{u.email}</option>
        ))}
      </select>
      <Button variant="ghost" onClick={onDelete}>Delete node</Button>
    </div>
  );
}
```

- [ ] **Step 2: Create `GraphToolbar.tsx`**

```tsx
/* 3D — editor toolbar: add/delete/save/reset + inline validation error. */
import { Button } from "../../ui";

export interface GraphToolbarProps {
  onAddNode: () => void;
  onDeleteSelected: () => void;
  onSave: () => void;
  onReset: () => void;
  saving: boolean;
  dirty: boolean;
  error: string | null;
}

export default function GraphToolbar({
  onAddNode,
  onDeleteSelected,
  onSave,
  onReset,
  saving,
  dirty,
  error,
}: GraphToolbarProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <Button variant="secondary" onClick={onAddNode}>Add node</Button>
        <Button variant="ghost" onClick={onDeleteSelected}>Delete selected</Button>
        <Button variant="ghost" onClick={onReset} disabled={!dirty || saving}>Reset</Button>
        <Button variant="primary" onClick={onSave} disabled={!dirty || saving || Boolean(error)}>
          {saving ? "Saving…" : "Save graph"}
        </Button>
      </div>
      {error && (
        <div className="vaic-inline-alert" role="alert">{error}</div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workflows/graph/NodeInspector.tsx frontend/src/components/workflows/graph/GraphToolbar.tsx
git commit -m "feat(workflows): node inspector + graph editor toolbar"
```

---

## Task 9: GraphTab container + shell wiring

**Files:**
- Create: `frontend/src/components/workflows/graph/GraphTab.tsx`
- Modify: `frontend/src/components/workflows/WorkflowDetailShell.tsx`

**Interfaces:**
- Consumes: `useWorkflowGraph` (Task 5), `useWorkflowGraphMutation` (Task 5), mappers + `validateGraph` + `nextNodeKey` (Task 6), `GraphEditor` (Task 7), `NodeInspector` + `GraphToolbar` (Task 8); `@xyflow/react` change helpers (`applyNodeChanges`, `applyEdgeChanges`, `addEdge`); `Skeleton`, `ErrorState`, `useToast` (`components/ui`).
- Produces: `GraphTab` props `{ workflowId }`; a `"graph"` tab in `WorkflowDetailShell`.

- [ ] **Step 1: Create `GraphTab.tsx`**

```tsx
/* 3D — Graph tab: owns editor state, loads/saves the DAG, validates pre-Save. */
import { useEffect, useMemo, useState } from "react";
import {
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  type Node,
  type Edge,
  type Connection,
} from "@xyflow/react";
import { Skeleton, ErrorState, useToast } from "../../ui";
import GraphEditor from "./GraphEditor";
import NodeInspector from "./NodeInspector";
import GraphToolbar from "./GraphToolbar";
import { useWorkflowGraph } from "../../../hooks/useWorkflowGraph";
import { useWorkflowGraphMutation } from "../../../hooks/useWorkflowGraphMutation";
import {
  toReactFlow,
  toDefinition,
  nextNodeKey,
  validateGraph,
  type RFNodeData,
} from "../../../lib/graphEditorState";

export interface GraphTabProps {
  workflowId: string;
}

export default function GraphTab({ workflowId }: GraphTabProps) {
  const graph = useWorkflowGraph(workflowId);
  const { mutateAsync, isPending } = useWorkflowGraphMutation(workflowId);
  const { show } = useToast();

  const [nodes, setNodes] = useState<Node<RFNodeData>[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  // Resync baseline from server on load / after save.
  useEffect(() => {
    if (!graph.data) return;
    const rf = toReactFlow(graph.data);
    setNodes(rf.nodes);
    setEdges(rf.edges);
    setDirty(false);
  }, [graph.data]);

  const def = useMemo(() => toDefinition(nodes, edges), [nodes, edges]);
  const error = useMemo(() => validateGraph(def), [def]);
  const selected = nodes.find((n) => n.id === selectedId) ?? null;

  function addNode() {
    const key = nextNodeKey(nodes.map((n) => n.data.nodeKey));
    setNodes((ns) => [
      ...ns,
      {
        id: key,
        type: "agent",
        position: { x: 80 + ns.length * 40, y: 80 + ns.length * 40 },
        data: { label: key, agentId: "", nodeKey: key, approverUserIds: [] },
      },
    ]);
    setSelectedId(key);
    setDirty(true);
  }

  function patchSelected(patch: Partial<RFNodeData>) {
    setNodes((ns) =>
      ns.map((n) => (n.id === selectedId ? { ...n, data: { ...n.data, ...patch } } : n)),
    );
    setDirty(true);
  }

  function deleteNode(id: string) {
    setNodes((ns) => ns.filter((n) => n.id !== id));
    setEdges((es) => es.filter((e) => e.source !== id && e.target !== id));
    if (selectedId === id) setSelectedId(null);
    setDirty(true);
  }

  async function save() {
    if (error) {
      show(error, "error");
      return;
    }
    try {
      await mutateAsync(def);
      show("Graph saved");
      setDirty(false);
    } catch (e) {
      show((e as Error).message, "error");
    }
  }

  if (graph.isLoading) return <Skeleton lines={6} height="24px" />;
  if (graph.isError) return <ErrorState message={graph.error?.message ?? "Failed to load graph"} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <GraphToolbar
        onAddNode={addNode}
        onDeleteSelected={() => selectedId && deleteNode(selectedId)}
        onSave={save}
        onReset={() => graph.data && (setNodes(toReactFlow(graph.data).nodes),
          setEdges(toReactFlow(graph.data).edges), setDirty(false))}
        saving={isPending}
        dirty={dirty}
        error={error}
      />
      <div style={{ display: "flex", gap: "var(--space-4)", alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <GraphEditor
            nodes={nodes}
            edges={edges}
            onNodesChange={(c) => { setNodes((ns) => applyNodeChanges(c, ns)); setDirty(true); }}
            onEdgesChange={(c) => { setEdges((es) => applyEdgeChanges(c, es)); setDirty(true); }}
            onConnect={(conn: Connection) => { setEdges((es) => addEdge(conn, es)); setDirty(true); }}
            onSelectNode={setSelectedId}
          />
        </div>
        <div style={{ width: 300, flexShrink: 0 }}>
          <NodeInspector
            node={selected}
            onChange={patchSelected}
            onDelete={() => selectedId && deleteNode(selectedId)}
          />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire the third tab into `WorkflowDetailShell.tsx`**

Add the import near the other tab imports:
```tsx
import GraphTab from "./graph/GraphTab";
```

Widen the tab state type (line ~27):
```tsx
const [tab, setTab] = useState<"definition" | "graph" | "runs">("definition");
```

Add a Graph tab button between the Definition and Runs buttons in the `role="tablist"` block:
```tsx
<Button
  variant={tab === "graph" ? "primary" : "ghost"}
  disabled={isNew}
  onClick={() => guardedNavigate(() => { setIsDirty(false); setTab("graph"); })}
>
  Graph
</Button>
```

Replace the tab-body conditional (the `tab === "definition" ? (...) : (<RunsTab .../>)`) with an explicit three-way:
```tsx
{tab === "definition" ? (
  <DefinitionTab
    workflowId={workflowId}
    isNew={isNew}
    workflow={workflow}
    onDirtyChange={setIsDirty}
    onSaved={handleSaved}
  />
) : tab === "graph" ? (
  <GraphTab workflowId={workflowId} />
) : (
  <RunsTab workflowId={workflowId} />
)}
```

- [ ] **Step 3: Manual end-to-end verification (primary success criterion)**

Run the stack (README), log in as a Builder, open an existing workflow → **Graph** tab:
1. Add node → node appears; inspector opens; pick an Agent; set a label.
2. Add a second node; drag from the first node's bottom handle to the second's top handle → edge appears.
3. Assign an approver to node 2 → "● human-gated" badge shows.
4. Save graph → toast "Graph saved"; reload the page → the graph (nodes, edge, positions, agent, approver) persists.
5. Create an edge back the other way to form a cycle → Save is blocked and the toolbar shows "graph contains a cycle".
6. Trigger a run of this workflow (Runs tab) → open the run → the 3C tracking canvas renders the same nodes/edges (confirms the snapshot path now has graph data).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workflows/graph/GraphTab.tsx frontend/src/components/workflows/WorkflowDetailShell.tsx
git commit -m "feat(workflows): Graph authoring tab wired into workflow detail shell"
```

---

## Self-Review Notes (author)

- **Spec coverage:** §3.1 GET → Task 2; §3.2 PUT/replace → Tasks 1–2; §3.3 users reuse → Task 4; §4.1 api/hooks → Tasks 3–5; §4.2 components → Tasks 6–9; §4.3 shell tab → Task 9; validation mirror → Task 6; positions persisted → Tasks 1/6/9. Approvers → Tasks 1/8/9.
- **Deviation from spec:** §3.3 originally proposed a new `GET /users`; the existing `GET /auth/users` covers it (spec updated). No new backend users endpoint.
- **Deferred (spec §8/§9):** node `config` form, auto-layout, optimistic locking, Chat orchestration — not in this plan.
- **Type consistency:** `RFNodeData` fields (`label`, `agentId`, `nodeKey`, `approverUserIds`) are identical across Tasks 6/7/8/9; `GraphDefinition`/`GraphDefinitionNode` field names (`node_key`, `agent_id`, `approver_user_ids`, `position`) match the backend serializer in Task 1 and the routes in Task 2.
