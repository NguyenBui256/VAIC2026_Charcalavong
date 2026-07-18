# Workflow Graph Builder — Visual DAG Authoring UI (Sub-project 3D)

**Date:** 2026-07-18
**Status:** Design approved, pending spec review
**Depends on:** 3A (data model: `workflow_nodes` / `workflow_edges` / `workflow_node_approvers`, `graph_validation`, `graph_snapshot`), 3C (run-tracking canvas + `RunGraphCanvas` render conventions).
**Scope:** The authoring surface that lets a user **build** a workflow's DAG — add nodes (each bound to a Specialist Agent), connect parent→child edges, assign per-node human approvers, and persist. Realizes the "3D graph authoring" repeatedly deferred by 3A/3B/3C. Excludes the Chat orchestration UI (separate follow-up project — see §9).

## 1. Context & Problem

The graph-workflow backend is built end-to-end: 3A defined the tables + `assert_valid_graph` + `build_graph_snapshot`; 3B built the execution engine + review/rollback; 3C built the run-tracking canvas (`RunTrackingView`, `RunGraphCanvas`, `RunReviewPanel`) that renders a run's immutable `graph_snapshot`.

**But there is no way to author a graph.** `orchestrator/routes.py` exposes workflow CRUD (name/description/constraints), runs, and the run-graph read — **no create/update endpoint for `workflow_nodes` / `workflow_edges`**. The frontend `DefinitionTab` is a plain form (name/description/constraints). Consequence: no workflow can have a graph unless rows are inserted directly into the DB, so every run falls back to the legacy flat decompose path (`graph_snapshot = NULL`) and `GET /runs/{id}/graph` 404s.

User-visible symptom that opened this work: *"workflow không xem được ở dạng graph"* — the Definition screen only shows name/description/constraints, with no graph configuration. This project supplies the missing authoring API + editor.

**Downstream motivation:** the planned Chat orchestration feature (§9) wants to embed the 3C run-tracking canvas (graph + progress + human approval) inside chat. That experience only has graph data when workflows actually have graphs — which requires this builder first.

## 2. Design Decisions (locked)

| Decision | Choice |
|---|---|
| Editor tech | **React Flow (`@xyflow/react`)** — standard DAG editor: drag nodes, connect handles, pan/zoom out of the box. Accepts one new dependency (the read-only 3C `RunGraphCanvas` stays hand-rolled SVG; the interactive editor is where a library pays off). |
| Persistence model | **Whole-graph replace** via a single `PUT` — send the full node+edge+approver set; backend validates the DAG then rewrites in one transaction. Simpler and atomic vs. per-entity CRUD. |
| Entry point | New **"Graph" tab** on `WorkflowDetailShell` (alongside Definition / Runs). Disabled for the unsaved "new" workflow (needs a persisted `workflow_id`). |
| Node identity | `node_key` — short stable string, unique per workflow. Auto-generated on node add (e.g. `n1`, `n2`…), editable while unique. Edges reference `node_key`, not DB id. |
| Node → Agent | Each node binds exactly one Agent (`agent_id`), chosen via `useAgents` (existing). |
| Approvers | **In scope.** Per-node multi-select of tenant users. Zero approvers = auto (non-gated) node; ≥1 = human-gated (matches 3A semantics). Requires a new tenant users-list endpoint (§3.3). |
| Validation | Reuse `assert_valid_graph` on the backend (single gate). Frontend mirrors it for live feedback: reject cycles, self-loops, duplicate edges, duplicate `node_key`, and nodes with no bound agent, before enabling Save. |
| Data flow | No field-mapping on edges (3A convention: a child's input = merge of every parent's output keyed by parent `node_key`). Edges carry only `from`/`to`. |
| Positions | `position_x` / `position_y` persisted from the editor so the 3C run canvas renders the same layout (its `layout.ts` uses stored positions, BFS fallback only when collapsed). |

## 3. Backend

New module `orchestrator/graph_authoring.py` + routes on the existing `/workflows` router. All Builder-role, RLS-scoped.

### 3.1 `GET /workflows/{workflow_id}/graph-definition`
Load the authored graph for the editor. **Distinct path** from 3C's `GET /workflows/runs/{run_id}/graph` (that reads a run's frozen snapshot; this reads the live definition). Returns the editable shape:

```json
{"nodes": [{"node_key": "n1", "label": "Extract", "agent_id": "…",
            "config": {}, "position": {"x": 40, "y": 80},
            "approver_user_ids": ["…"]}],
 "edges": [{"from": "n1", "to": "n2"}]}
```

- Empty graph (no nodes) returns `{"nodes": [], "edges": []}` (200, not 404) — an unbuilt-but-valid state the editor opens on.
- `serialize_workflow_graph(session, workflow_id)` in `graph_authoring.py`, reusing the read pattern of `build_graph_snapshot` (minus the run-snapshot framing).

### 3.2 `PUT /workflows/{workflow_id}/graph-definition`
Replace the whole graph. Body = the same `{nodes, edges}` shape (approvers embedded per node as `approver_user_ids`). Behavior of `replace_workflow_graph`:
1. Validate request shape (Pydantic): unique `node_key`s, each node has `agent_id`, edges reference existing `node_key`s.
2. Run `assert_valid_graph(node_keys, edge_key_pairs)` → 422 `GraphValidationError.message` on failure (cycle/self-loop/dup).
3. In one transaction (RLS-scoped): delete existing `workflow_edges`, `workflow_node_approvers`, `workflow_nodes` for the workflow; insert the new set; upsert approvers.
4. Bump `workflow.version`.
5. Audit `workflow.graph_updated` (node/edge counts).
6. Return the re-serialized graph (200).

Referential guard: agent_ids and approver user_ids must belong to the tenant (RLS + explicit existence check → 422 on unknown id) so a bad reference fails at authoring time, not at run creation.

### 3.3 Users list for the approver picker — reuse existing `GET /auth/users`
No new endpoint. The tenant module already exposes `GET /auth/users` (`list_tenant_users`, RLS-scoped), returning `{id, email, tenant_id, department_id, role}` per user. The approver picker consumes it directly; the frontend only needs a thin `usersApi.ts` wrapper. Picker shows `email` as the label (no `name` field on the User record). Approver assignment stays Builder-gated via the `PUT`.

## 4. Frontend

### 4.1 API + hooks
- `lib/workflowGraphApi.ts` — `getWorkflowGraph(id)`, `putWorkflowGraph(id, {nodes, edges})`; types `GraphDefinitionNode` / `GraphDefinitionEdge` mirroring §3.1.
- `lib/usersApi.ts` — `listUsers()` → `TenantUser[]`.
- `hooks/useWorkflowGraph.ts` (query, `staleTime` moderate), `hooks/useUsers.ts` (query, long `staleTime`).
- `hooks/useWorkflowGraphMutation.ts` — `PUT` wrapper, invalidates the graph query + the workflow query (version bumped).

### 4.2 Components (each < 200 lines; kebab-case, self-documenting)
- `components/workflows/graph/GraphTab.tsx` — tab container: load graph, own the working RF state, Save/Reset, dirty guard (reuse `useUnsavedChangesGuard`), inline validation banner.
- `components/workflows/graph/GraphEditor.tsx` — the React Flow canvas: nodes, edges, connect handler, selection, position tracking. Registers one custom node type.
- `components/workflows/graph/AgentNode.tsx` — custom RF node: label + bound-agent name + gated (approver) badge + source/target handles. Reuses `ui/` tokens.
- `components/workflows/graph/NodeInspector.tsx` — right panel for the selected node: label input, `node_key` (edit + uniqueness check), Agent picker (`useAgents`), approver multi-select (`useUsers`), Delete node.
- `components/workflows/graph/GraphToolbar.tsx` — Add node, Delete selected, Save, Reset.
- `lib/graphEditorState.ts` — pure mappers RF ⇄ API shape (`toReactFlow(def)`, `toDefinition(rfNodes, rfEdges)`), `nextNodeKey(existing)`, and a client-side `validateGraph(def)` wrapping the same rules as `assert_valid_graph` for pre-Save feedback.

### 4.3 Shell wiring
`WorkflowDetailShell`: add a third tab `"graph"`. Tab disabled when `isNew`. Graph tab participates in the same unsaved-changes guard as Definition. Header/back unchanged.

## 5. Data Flow

```
Editor load:   GraphTab → useWorkflowGraph(id) → GET /graph-definition
                        → toReactFlow(def) → GraphEditor state
Edit:          drag/connect/inspector mutate RF state (local); validateGraph()
               gates the Save button and shows inline errors.
Save:          toDefinition(rf) → useWorkflowGraphMutation → PUT /graph-definition
               → backend assert_valid_graph → transactional rewrite → version++
               → re-serialized graph → query invalidation → editor resyncs baseline.
Run (later):   creating a run snapshots this graph (build_graph_snapshot) → 3C
               RunGraphCanvas renders it with the stored positions.
```

## 6. Error Handling
- Backend validation failure → 422 with the specific `GraphValidationError` message; the Save mutation surfaces it in the GraphTab banner (no optimistic overwrite of server state).
- Unknown agent/user reference → 422; banner names the offending id.
- Concurrent edit: `PUT` is last-writer-wins on the whole graph (acceptable for single-builder authoring; version bump makes stale reads visible). No optimistic locking in v1.
- Empty graph is valid (Save allowed) — lets a user clear a graph back to the flat path.

## 7. Testing
Per project working-preference (no tests unless requested), tests are **out of scope for v1** unless the user asks. If requested, priority order: `assert_valid_graph` is already covered (3A); add (a) `replace_workflow_graph` transactional rewrite + version bump, (b) `graphEditorState` mappers/`validateGraph` round-trip, (c) a GraphTab load→edit→save happy path.

## 8. Out of Scope (v1)
- Realtime/multi-user co-editing, optimistic locking.
- Edge field-mapping / conditional edges (3A locked whole-output merge).
- Node `config` editing UI beyond agent binding (schema field kept, no form yet).
- Auto-layout button (positions are user-driven; 3C BFS fallback covers seeded graphs).
- Chat orchestration (§9).

## 9. Follow-up Project — Chat Orchestration (separate spec)
Not built here; captured so this design stays aligned with it. Chat will be a thin conversational shell over the existing run pipeline: a target picker (a saved **Workflow** or a single **Agent**), each user message creating a run whose progress is shown by **embedding the 3C `RunTrackingView`** (graph + polling + `RunReviewPanel` approve/reject) inside the chat bubble — the "real experience" (notify + human approval + in-chat graph). It depends on this Graph Builder so that selected workflows have real graphs to render. New pieces there: `chat_sessions` / `chat_messages` tables, chat routes (session, post-message→create-run, list), and a Chat page. Reuses: orchestrator pipeline, run-tracking components, decision/approval endpoints, audit.

## 10. Open Questions
- Approver picker source: reuses `GET /auth/users` (all tenant users). If a role model later restricts who may approve, filter there or client-side; v1 lists all.
- `node_key` UX: auto-only vs. user-editable. v1 allows editing with a uniqueness guard; may lock to auto if it causes edge-integrity confusion in testing.
