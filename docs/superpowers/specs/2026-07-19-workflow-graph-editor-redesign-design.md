# Workflow Graph Editor — Redesign (frontend-only)

Date: 2026-07-19
Status: Approved (design)
Scope: Frontend only. No backend/API/model/migration changes.

## Motivation

Current graph tab (`frontend/src/components/workflows/graph/`) renders a React
Flow DAG but has gaps against user needs:

1. Nodes float freely; no vertical top→bottom flow along the panel length.
2. Approver assignment invisible — node shows only a `● human-gated` badge, not
   *who* reviews. `approverUserIds` already exists in node data.
3. No visual for rollback (a rejected gated node rolls the run back to a parent).
4. No left palette; node creation is a generic "Add node" button, no drag-drop.

## Constraints / data-model facts (must respect)

- Authoring graph is a **strict DAG**; `assert_valid_graph` rejects cycles.
  `WorkflowEdge` has only `from`/`to` — **no rollback edge type**, no IO mapping.
- **Rollback is runtime, not authoring**: on reject of a gated node,
  `RunRollbackRequest` rolls back to an existing **parent** node (reverse of a
  forward edge). It is NOT a stored authoring edge.
- Inter-node data flow is **whole-output merge** keyed by parent `node_key` —
  there is no field-level input/output mapping, and none is added here.

Therefore rollback edges and "input/output wiring" are **display-only,
derived** representations — never persisted, never sent to the API.

## Non-goals (explicitly out of scope)

- No new edge type / IO field-mapping in the DB or `GraphDefinition`.
- No persistence of rollback edges.
- No change to `graphEditorState.toDefinition` output shape or the save payload.
- No automated tests (per project CLAUDE.md override) unless later requested.

## Components

All under `frontend/src/components/workflows/graph/` unless noted.

### 1. Vertical layout — `frontend/src/lib/graphLayout.ts` (new, pure)

- `layoutVertical(nodes, edges): Node<RFNodeData>[]` — pure, no React.
- Longest-path layering: roots (indegree 0) at layer 0; a node's layer =
  `max(parent layer) + 1`. Assign `position.y = layer * ROW_GAP`; within a
  layer, spread siblings across X (`col * COL_GAP`, centered).
- Dependency-free (no dagre/elk — not installed). Deterministic, unit-testable.
- Handles already Top(target)/Bottom(source) in `AgentNode`, so no handle
  changes are needed.

Applied by: the "Sắp xếp dọc" palette button; and auto-run once on load when
every loaded node position is `(0,0)` (fresh graph) so the default view reads
top→bottom without overwriting user-arranged positions.

### 2. Approver display — `AgentNode.tsx` (changed) + users context

- Render 1–2 circular avatars (initials derived from user email) plus a `+N`
  overflow chip; tooltip on hover lists all approver emails. Keep the gated
  badge.
- Provide a `usersById` lookup via a small React context provider wrapping the
  React Flow canvas (built from `useUsers`), so `AgentNode` resolves emails
  without embedding stale user data into node state.

### 3. Rollback edges — `frontend/src/lib/rollbackEdges.ts` (new, pure)

- `deriveRollbackEdges(nodes, edges): Edge[]` — for each node whose
  `approverUserIds.length > 0`, emit a **dashed, warning-colored** edge going
  in reverse (child → each direct parent), matching the `RunRollbackRequest`
  "roll back to parent" behavior.
- Id namespace `rb:<child>-><parent>`; `selectable:false`, `deletable:false`,
  `style` dashed + warning color, no arrow ambiguity (mark as reverse).
- **Display-only**: concatenated into the rendered edge array via `useMemo`;
  never enters the `edges` state, so `toDefinition`/save are unaffected. As a
  guard, any edge whose id starts with `rb:` is ignored if it ever reaches
  serialization.

### 4. Palette sidebar — `PaletteSidebar.tsx` (new)

Left column. Contains:

- **Agent list** (from `useAgents`): each row draggable (HTML5 drag; dnd payload
  = `{ kind: 'agent', agentId, name }`). Drop on canvas → create node bound to
  that agent.
- **"Blank node"** draggable (payload `{ kind: 'blank' }`) → create an
  unbound node (same as today's Add node, but drag-drop).
- **Edge-mode toggle**: `transition` (default — draw forward edges as today)
  vs `rollback` (emphasize the dashed rollback overlay, dim forward edges for
  readability). View-only emphasis; does not change what is saved.
- **"Sắp xếp dọc"** button → apply `layoutVertical`.

### 5. Canvas — `GraphEditor.tsx` (changed)

- Wrap in `ReactFlowProvider`; use `useReactFlow().screenToFlowPosition` for
  drop placement.
- Add `onDrop` / `onDragOver` handlers; read dnd payload, call up to
  `GraphTab` to create the node at the flow coordinate.
- Render `edges` concatenated with derived rollback edges; accept a
  `rollbackEmphasis` prop from the edge-mode toggle to style forward vs
  rollback layers.

### 6. Tab shell — `GraphTab.tsx` (changed)

- Layout: three columns **PaletteSidebar | GraphEditor | NodeInspector**.
- New `addNodeFromDrop(payload, position)`; keep existing `addNode`, `patchSelected`,
  `deleteNode`, `save`, `reset`, dirty tracking.
- Wire auto-layout action (setNodes + mark dirty since positions change).
- Rollback edges computed here (or in GraphEditor) via `useMemo` and passed
  down for render only.

## Data flow

- `GraphTab` owns `nodes` and `edges` (forward only). Rollback edges are a pure
  derivation, merged only at render time → never saved.
- Drag agent/blank → `onDrop` → create node at `screenToFlowPosition` → dirty.
- Auto-layout → `setNodes(layoutVertical(nodes, edges))` → dirty.
- Save path unchanged: `toDefinition(nodes, edges)` → `putWorkflowGraph`.

## Testing

Per project CLAUDE.md working-preferences override, no tests are written unless
requested. Pure modules (`graphLayout`, `rollbackEdges`) are isolated so tests
can be added later without refactoring.

## Open questions

- None outstanding. (Auto-layout default behavior chosen: run once on load only
  when all positions are `(0,0)`, plus manual button — confirmed acceptable.)
