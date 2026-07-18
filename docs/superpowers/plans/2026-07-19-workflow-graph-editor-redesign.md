# Workflow Graph Editor Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the workflow graph authoring tab with a vertical top→bottom layout, on-node approver display, a derived dashed rollback overlay, and a left drag-drop palette — all frontend-only.

**Architecture:** Keep all state in `GraphTab` (forward `nodes`/`edges` only). Two new pure library modules — `graphLayout.ts` (vertical layering) and `rollbackEdges.ts` (derived dashed overlay edges) — carry the non-trivial logic and are dependency-free. Rollback edges and the vertical layout are pure derivations that never enter saved state, so the API payload (`toDefinition` → `putWorkflowGraph`) is unchanged. A left `PaletteSidebar` provides HTML5 drag-drop node creation; the canvas gains `ReactFlowProvider` + drop handling.

**Tech Stack:** React 18 + TypeScript, `@xyflow/react` ^12.11.2, TanStack Query, existing `ui` primitives (`Button`, `Tooltip`). No new dependencies.

## Global Constraints

- Frontend only — NO backend, API, model, or migration changes.
- Do NOT change `GraphDefinition` shape or the save payload produced by `toDefinition`.
- Rollback edges and vertical layout are display-only derivations; rollback edges are NEVER persisted and NEVER enter `edges` state.
- Authoring graph stays a strict DAG; do not introduce a stored rollback edge type or IO field-mapping.
- No automated tests unless explicitly requested (project CLAUDE.md working-preferences override). Steps below build pure modules first via a manual node-script verification, not a test framework.
- Do NOT auto-run `typecheck`/`lint`/`build`/`format` unless the user asks (CLAUDE.md override). Verification steps use targeted `node` runs only.
- File naming: kebab-case, descriptive; keep files focused (<200 LOC where practical).
- Existing style conventions: inline `style={{...}}` with `var(--space-*)`, `var(--color-*)` tokens; `vaic-*` CSS classes; components default-export.

## Reference facts (verified in codebase)

- `RFNodeData` (`frontend/src/lib/graphEditorState.ts`): `{ label: string; agentId: string; nodeKey: string; approverUserIds: string[] }`.
- `useAgents(params)` returns `{ data: Agent[] | undefined, isLoading, isError, query }`; `Agent` has `{ id: string; name: string; ... }`.
- `useUsers()` returns `UseQueryResult<TenantUser[]>`; `TenantUser` = `{ id: string; email: string; department_id: string | null; role: string }`.
- `Tooltip` (`ui`): props `{ label: string; children: ReactNode; side?: "top"|"bottom" }`.
- `AgentNode` handles: `Handle type="target" position={Position.Top}` and `type="source" position={Position.Bottom}` (already vertical-oriented).
- React Flow node/edge change plumbing lives in `GraphTab` (`applyNodeChanges`/`applyEdgeChanges`/`addEdge`).

---

### Task 1: Vertical layout pure module

**Files:**
- Create: `frontend/src/lib/graphLayout.ts`

**Interfaces:**
- Consumes: `Node`, `Edge` from `@xyflow/react`; `RFNodeData` from `./graphEditorState`.
- Produces: `layoutVertical(nodes: Node<RFNodeData>[], edges: Edge[]): Node<RFNodeData>[]` — returns a NEW array with updated `position` for every node (top→bottom by layer). Also `allPositionsZero(nodes: Node<RFNodeData>[]): boolean`.

- [ ] **Step 1: Write the module**

```typescript
/* Frontend-only vertical auto-layout for the workflow graph.
 * Pure (no React): longest-path layering places roots at layer 0 and each
 * node at max(parent layer)+1, laid out top->bottom. Siblings in a layer are
 * spread across X and centered. Dependency-free (no dagre/elk installed). */

import type { Node, Edge } from "@xyflow/react";
import type { RFNodeData } from "./graphEditorState";

const ROW_GAP = 160; // vertical distance between layers (y)
const COL_GAP = 240; // horizontal distance between siblings (x)

/** True when every node sits at the default (0,0) — i.e. never arranged. */
export function allPositionsZero(nodes: Node<RFNodeData>[]): boolean {
  return nodes.every((n) => n.position.x === 0 && n.position.y === 0);
}

/** Assign top->bottom layered positions. Assumes a DAG (cycles are broken
 * defensively by capping the layering pass at nodes.length iterations). */
export function layoutVertical(
  nodes: Node<RFNodeData>[],
  edges: Edge[],
): Node<RFNodeData>[] {
  const ids = nodes.map((n) => n.id);
  const idSet = new Set(ids);
  const parents = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const e of edges) {
    if (idSet.has(e.source) && idSet.has(e.target)) {
      parents.get(e.target)!.push(e.source);
    }
  }

  // Longest-path layer via memoized recursion with a visiting guard.
  const layer = new Map<string, number>();
  const visiting = new Set<string>();
  function computeLayer(id: string): number {
    if (layer.has(id)) return layer.get(id)!;
    if (visiting.has(id)) return 0; // cycle guard (shouldn't happen on a DAG)
    visiting.add(id);
    const ps = parents.get(id)!;
    const l = ps.length === 0 ? 0 : Math.max(...ps.map(computeLayer)) + 1;
    visiting.delete(id);
    layer.set(id, l);
    return l;
  }
  for (const id of ids) computeLayer(id);

  // Group by layer (preserve node input order within a layer for stability).
  const byLayer = new Map<number, string[]>();
  for (const id of ids) {
    const l = layer.get(id)!;
    if (!byLayer.has(l)) byLayer.set(l, []);
    byLayer.get(l)!.push(id);
  }

  const pos = new Map<string, { x: number; y: number }>();
  for (const [l, group] of byLayer) {
    const width = (group.length - 1) * COL_GAP;
    group.forEach((id, i) => {
      pos.set(id, { x: i * COL_GAP - width / 2, y: l * ROW_GAP });
    });
  }

  return nodes.map((n) => ({ ...n, position: pos.get(n.id) ?? n.position }));
}
```

- [ ] **Step 2: Verify it runs and produces layered output**

Run:
```bash
cd frontend && node --input-type=module -e "
import { layoutVertical, allPositionsZero } from './src/lib/graphLayout.ts';
" 2>&1 | head -5 || echo 'ts-not-directly-runnable-expected'
```
Expected: node cannot import `.ts` directly (that's fine). Instead do a JS smoke check:
```bash
cd frontend && node --input-type=module -e "
const ROW_GAP=160, COL_GAP=240;
// inline copy of the layering math to sanity-check the algorithm shape
const nodes=[{id:'a',position:{x:0,y:0}},{id:'b',position:{x:0,y:0}},{id:'c',position:{x:0,y:0}}];
const edges=[{source:'a',target:'b'},{source:'b',target:'c'}];
const parents=new Map(nodes.map(n=>[n.id,[]]));
for(const e of edges) parents.get(e.target).push(e.source);
const layer=new Map();
const cl=id=>{ if(layer.has(id))return layer.get(id); const ps=parents.get(id); const l=ps.length?Math.max(...ps.map(cl))+1:0; layer.set(id,l); return l;};
nodes.forEach(n=>cl(n.id));
console.log([...layer.entries()]);
"
```
Expected: `[ [ 'a', 0 ], [ 'b', 1 ], [ 'c', 2 ] ]` (a→b→c chain lands on layers 0,1,2).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/graphLayout.ts
git commit -m "feat(graph): vertical top-to-bottom auto-layout (pure)"
```

---

### Task 2: Rollback overlay pure module

**Files:**
- Create: `frontend/src/lib/rollbackEdges.ts`

**Interfaces:**
- Consumes: `Node`, `Edge` from `@xyflow/react`; `RFNodeData` from `./graphEditorState`.
- Produces: `deriveRollbackEdges(nodes: Node<RFNodeData>[], edges: Edge[]): Edge[]` — display-only dashed edges (id prefix `rb:`) from each gated node back to each direct parent. Also `ROLLBACK_EDGE_ID_PREFIX = "rb:"`.

- [ ] **Step 1: Write the module**

```typescript
/* Frontend-only derived rollback overlay edges.
 * A gated node (>=1 approver) can, at RUN time, be rejected and rolled back to
 * a parent node (RunRollbackRequest). This module renders that possibility as
 * dashed warning-colored edges going in reverse (child -> each direct parent).
 * These are DISPLAY-ONLY: id-prefixed `rb:`, never selectable/deletable, never
 * added to `edges` state, never serialized to the API. Pure (no React). */

import type { Node, Edge } from "@xyflow/react";
import type { RFNodeData } from "./graphEditorState";

export const ROLLBACK_EDGE_ID_PREFIX = "rb:";

/** For each gated node, one dashed reverse edge to each of its direct parents. */
export function deriveRollbackEdges(
  nodes: Node<RFNodeData>[],
  edges: Edge[],
): Edge[] {
  const gated = new Set(
    nodes.filter((n) => (n.data.approverUserIds?.length ?? 0) > 0).map((n) => n.id),
  );
  const out: Edge[] = [];
  for (const e of edges) {
    // e: parent(source) -> child(target). If child is gated, it can roll back
    // to this parent, so draw child -> parent as a dashed overlay.
    if (gated.has(e.target)) {
      out.push({
        id: `${ROLLBACK_EDGE_ID_PREFIX}${e.target}->${e.source}`,
        source: e.target,
        target: e.source,
        selectable: false,
        deletable: false,
        focusable: false,
        style: {
          stroke: "var(--color-warning, #b45309)",
          strokeDasharray: "6 4",
          strokeWidth: 1.5,
        },
        label: "rollback",
        labelStyle: { fill: "var(--color-warning, #b45309)", fontSize: 10 },
        // curved so it visually separates from the solid forward edge
        type: "default",
      });
    }
  }
  return out;
}
```

- [ ] **Step 2: Verify the derivation shape**

Run:
```bash
cd frontend && node --input-type=module -e "
const PRE='rb:';
const nodes=[{id:'a',data:{approverUserIds:[]}},{id:'b',data:{approverUserIds:['u1']}}];
const edges=[{source:'a',target:'b'}];
const gated=new Set(nodes.filter(n=>(n.data.approverUserIds?.length??0)>0).map(n=>n.id));
const out=[];
for(const e of edges){ if(gated.has(e.target)) out.push({id:PRE+e.target+'->'+e.source,source:e.target,target:e.source}); }
console.log(JSON.stringify(out));
"
```
Expected: `[{"id":"rb:b->a","source":"b","target":"a"}]` (gated node b rolls back to parent a).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/rollbackEdges.ts
git commit -m "feat(graph): derived dashed rollback overlay edges (display-only)"
```

---

### Task 3: Users context for on-node approver resolution

**Files:**
- Create: `frontend/src/components/workflows/graph/GraphUsersContext.tsx`

**Interfaces:**
- Consumes: `TenantUser` from `../../../lib/usersApi`.
- Produces:
  - `GraphUsersProvider({ users, children }: { users: TenantUser[]; children: ReactNode })`
  - `useGraphUsers(): Map<string, TenantUser>` — id → user lookup for `AgentNode`.

- [ ] **Step 1: Write the context module**

```tsx
/* Frontend-only: makes the tenant user roster available to custom React Flow
 * nodes (AgentNode) so approver ids resolve to emails/initials WITHOUT baking
 * stale user data into node state. */

import { createContext, useContext, useMemo, type ReactNode } from "react";
import type { TenantUser } from "../../../lib/usersApi";

const GraphUsersCtx = createContext<Map<string, TenantUser>>(new Map());

export function GraphUsersProvider({
  users,
  children,
}: {
  users: TenantUser[];
  children: ReactNode;
}) {
  const map = useMemo(
    () => new Map(users.map((u) => [u.id, u])),
    [users],
  );
  return <GraphUsersCtx.Provider value={map}>{children}</GraphUsersCtx.Provider>;
}

export function useGraphUsers(): Map<string, TenantUser> {
  return useContext(GraphUsersCtx);
}
```

- [ ] **Step 2: Verify it compiles as part of the app**

Run:
```bash
cd frontend && node -e "const fs=require('fs'); const s=fs.readFileSync('src/components/workflows/graph/GraphUsersContext.tsx','utf8'); if(!s.includes('GraphUsersProvider')||!s.includes('useGraphUsers')) throw new Error('missing exports'); console.log('exports present');"
```
Expected: `exports present`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workflows/graph/GraphUsersContext.tsx
git commit -m "feat(graph): users context for on-node approver resolution"
```

---

### Task 4: Approver avatars on AgentNode

**Files:**
- Modify: `frontend/src/components/workflows/graph/AgentNode.tsx`
- Create: `frontend/src/components/workflows/graph/ApproverAvatars.tsx`

**Interfaces:**
- Consumes: `useGraphUsers` (Task 3), `RFNodeData.approverUserIds`, `Tooltip` from `ui`.
- Produces: `ApproverAvatars({ userIds }: { userIds: string[] })` — renders up to 2 initials chips + `+N`, with a Tooltip listing all approver emails.

- [ ] **Step 1: Write ApproverAvatars**

```tsx
/* Frontend-only: compact approver display for a graph node — up to two
 * initials chips + "+N" overflow, full email list on hover via Tooltip. */

import { Tooltip } from "../../ui";
import { useGraphUsers } from "./GraphUsersContext";

function initials(email: string): string {
  const name = email.split("@")[0] ?? email;
  const parts = name.split(/[._-]+/).filter(Boolean);
  const chars = parts.length >= 2 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return chars.toUpperCase();
}

export default function ApproverAvatars({ userIds }: { userIds: string[] }) {
  const users = useGraphUsers();
  if (userIds.length === 0) return null;
  const resolved = userIds.map((id) => users.get(id));
  const emails = resolved.map((u, i) => u?.email ?? userIds[i]);
  const shown = userIds.slice(0, 2);
  const overflow = userIds.length - shown.length;

  return (
    <Tooltip label={`Approvers: ${emails.join(", ")}`}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
        {shown.map((id, i) => (
          <span
            key={id}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 18,
              height: 18,
              borderRadius: "50%",
              background: "var(--color-warning, #b45309)",
              color: "#fff",
              fontSize: 9,
              fontWeight: 600,
            }}
          >
            {initials(emails[i])}
          </span>
        ))}
        {overflow > 0 && (
          <span style={{ fontSize: 10, opacity: 0.8 }}>+{overflow}</span>
        )}
      </span>
    </Tooltip>
  );
}
```

- [ ] **Step 2: Modify AgentNode to use it**

Replace the gated-badge block in `AgentNode.tsx` (the `{gated && (...)}` JSX) with a row that keeps the badge text and adds avatars:

```tsx
/* 3D — custom React Flow node: label + bound-agent name + gated badge + approvers. */
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { RFNodeData } from "../../../lib/graphEditorState";
import ApproverAvatars from "./ApproverAvatars";

export default function AgentNode({ data, selected }: NodeProps<RFNodeData>) {
  const approvers = data.approverUserIds ?? [];
  const gated = approvers.length > 0;
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
        <div
          style={{
            marginTop: 4,
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            color: "var(--color-warning, #b45309)",
          }}
        >
          <span>● human-gated</span>
          <ApproverAvatars userIds={approvers} />
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

- [ ] **Step 3: Verify wiring**

Run:
```bash
cd frontend && node -e "const fs=require('fs'); const a=fs.readFileSync('src/components/workflows/graph/AgentNode.tsx','utf8'); if(!a.includes('ApproverAvatars')) throw new Error('AgentNode not wired'); const b=fs.readFileSync('src/components/workflows/graph/ApproverAvatars.tsx','utf8'); if(!b.includes('useGraphUsers')) throw new Error('avatars not wired'); console.log('ok');"
```
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workflows/graph/AgentNode.tsx frontend/src/components/workflows/graph/ApproverAvatars.tsx
git commit -m "feat(graph): show approver avatars + tooltip on nodes"
```

---

### Task 5: Palette sidebar (drag sources + actions)

**Files:**
- Create: `frontend/src/components/workflows/graph/PaletteSidebar.tsx`

**Interfaces:**
- Consumes: `useAgents` (`{ data: Agent[] }`), `Button` from `ui`.
- Produces:
  - Drag payload JSON on `dataTransfer` with MIME `application/x-vaic-node`: `{ kind: "agent", agentId, name }` or `{ kind: "blank" }`.
  - `PaletteSidebar` props:
    ```ts
    interface PaletteSidebarProps {
      edgeMode: "transition" | "rollback";
      onEdgeModeChange: (m: "transition" | "rollback") => void;
      onAutoLayout: () => void;
    }
    ```
  - Exported constant `NODE_DND_MIME = "application/x-vaic-node"`.

- [ ] **Step 1: Write the sidebar**

```tsx
/* Frontend-only left palette: drag Agents / a blank node onto the canvas,
 * toggle the edge view mode, and trigger vertical auto-layout. */

import { useAgents } from "../../../hooks/useAgents";
import { Button } from "../../ui";

export const NODE_DND_MIME = "application/x-vaic-node";

export type EdgeMode = "transition" | "rollback";

export interface PaletteSidebarProps {
  edgeMode: EdgeMode;
  onEdgeModeChange: (m: EdgeMode) => void;
  onAutoLayout: () => void;
}

function setDrag(e: React.DragEvent, payload: Record<string, unknown>) {
  e.dataTransfer.setData(NODE_DND_MIME, JSON.stringify(payload));
  e.dataTransfer.effectAllowed = "copy";
}

export default function PaletteSidebar({
  edgeMode,
  onEdgeModeChange,
  onAutoLayout,
}: PaletteSidebarProps) {
  const agents = useAgents({});
  return (
    <div
      style={{
        width: 220,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
        borderRight: "1px solid var(--color-border)",
        paddingRight: "var(--space-3)",
      }}
    >
      <div>
        <div className="vaic-form-label">Actions</div>
        <Button variant="secondary" onClick={onAutoLayout}>Sắp xếp dọc</Button>
      </div>

      <div>
        <div className="vaic-form-label">Chế độ edge</div>
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button
            variant={edgeMode === "transition" ? "primary" : "ghost"}
            onClick={() => onEdgeModeChange("transition")}
          >
            Transition
          </Button>
          <Button
            variant={edgeMode === "rollback" ? "primary" : "ghost"}
            onClick={() => onEdgeModeChange("rollback")}
          >
            Rollback
          </Button>
        </div>
      </div>

      <div>
        <div className="vaic-form-label">Kéo vào canvas</div>
        <div
          draggable
          onDragStart={(e) => setDrag(e, { kind: "blank" })}
          className="vaic-focusable"
          style={{
            padding: "6px 8px",
            border: "1px dashed var(--color-border)",
            borderRadius: 6,
            cursor: "grab",
            marginBottom: "var(--space-2)",
            fontSize: 13,
          }}
        >
          + Blank node
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 320, overflowY: "auto" }}>
          {(agents.data ?? []).map((a) => (
            <div
              key={a.id}
              draggable
              onDragStart={(e) => setDrag(e, { kind: "agent", agentId: a.id, name: a.name })}
              className="vaic-focusable"
              style={{
                padding: "6px 8px",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                cursor: "grab",
                fontSize: 13,
                background: "var(--color-surface, #fff)",
              }}
            >
              {a.name}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify exports**

Run:
```bash
cd frontend && node -e "const s=require('fs').readFileSync('src/components/workflows/graph/PaletteSidebar.tsx','utf8'); ['NODE_DND_MIME','PaletteSidebarProps','onAutoLayout','kind: \"agent\"'].forEach(k=>{if(!s.includes(k))throw new Error('missing '+k)}); console.log('ok');"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workflows/graph/PaletteSidebar.tsx
git commit -m "feat(graph): left palette sidebar with drag sources + edge-mode + auto-layout"
```

---

### Task 6: Canvas — provider, drop handling, rollback overlay rendering

**Files:**
- Modify: `frontend/src/components/workflows/graph/GraphEditor.tsx`

**Interfaces:**
- Consumes: `deriveRollbackEdges` + `ROLLBACK_EDGE_ID_PREFIX` (Task 2), `NODE_DND_MIME` + `EdgeMode` (Task 5), `RFNodeData`.
- Produces: `GraphEditor` extended props:
  ```ts
  interface GraphEditorProps {
    nodes: Node<RFNodeData>[];
    edges: Edge[];
    edgeMode: "transition" | "rollback";
    onNodesChange: OnNodesChange<Node<RFNodeData>>;
    onEdgesChange: OnEdgesChange;
    onConnect: OnConnect;
    onSelectNode: (id: string | null) => void;
    onDropNode: (payload: { kind: "agent"; agentId: string; name: string } | { kind: "blank" }, position: { x: number; y: number }) => void;
  }
  ```

- [ ] **Step 1: Rewrite GraphEditor**

```tsx
/* 3D — controlled React Flow canvas. Parent (GraphTab) owns forward node/edge
 * state; this renders it, merges the DISPLAY-ONLY rollback overlay, handles
 * palette drops, and reports selection. Wrapped in ReactFlowProvider so
 * screenToFlowPosition is available for accurate drop placement. */
import { useMemo } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  useReactFlow,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import AgentNode from "./AgentNode";
import type { RFNodeData } from "../../../lib/graphEditorState";
import { deriveRollbackEdges } from "../../../lib/rollbackEdges";
import { NODE_DND_MIME, type EdgeMode } from "./PaletteSidebar";

export type DropPayload =
  | { kind: "agent"; agentId: string; name: string }
  | { kind: "blank" };

export interface GraphEditorProps {
  nodes: Node<RFNodeData>[];
  edges: Edge[];
  edgeMode: EdgeMode;
  onNodesChange: OnNodesChange<Node<RFNodeData>>;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  onSelectNode: (id: string | null) => void;
  onDropNode: (payload: DropPayload, position: { x: number; y: number }) => void;
}

function Canvas(props: GraphEditorProps) {
  const {
    nodes, edges, edgeMode,
    onNodesChange, onEdgesChange, onConnect, onSelectNode, onDropNode,
  } = props;
  const nodeTypes = useMemo(() => ({ agent: AgentNode }), []);
  const { screenToFlowPosition } = useReactFlow();

  const renderedEdges = useMemo(() => {
    const rollback = deriveRollbackEdges(nodes, edges);
    const rollbackMode = edgeMode === "rollback";
    // Dim forward edges when emphasizing rollback, and vice-versa.
    const forward = edges.map((e) => ({
      ...e,
      style: { ...(e.style ?? {}), opacity: rollbackMode ? 0.25 : 1 },
    }));
    const overlay = rollback.map((e) => ({
      ...e,
      style: { ...(e.style ?? {}), opacity: rollbackMode ? 1 : 0.6 },
    }));
    return [...forward, ...overlay];
  }, [nodes, edges, edgeMode]);

  return (
    <div style={{ height: 560, border: "1px solid var(--color-border)", borderRadius: 8 }}>
      <ReactFlow
        nodes={nodes}
        edges={renderedEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, n) => onSelectNode(n.id)}
        onPaneClick={() => onSelectNode(null)}
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
        }}
        onDrop={(e) => {
          e.preventDefault();
          const raw = e.dataTransfer.getData(NODE_DND_MIME);
          if (!raw) return;
          const payload = JSON.parse(raw) as DropPayload;
          const position = screenToFlowPosition({ x: e.clientX, y: e.clientY });
          onDropNode(payload, position);
        }}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}

export default function GraphEditor(props: GraphEditorProps) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}
```

- [ ] **Step 2: Verify wiring**

Run:
```bash
cd frontend && node -e "const s=require('fs').readFileSync('src/components/workflows/graph/GraphEditor.tsx','utf8'); ['ReactFlowProvider','screenToFlowPosition','deriveRollbackEdges','onDropNode','NODE_DND_MIME'].forEach(k=>{if(!s.includes(k))throw new Error('missing '+k)}); console.log('ok');"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workflows/graph/GraphEditor.tsx
git commit -m "feat(graph): canvas provider + drop-to-create + rollback overlay render"
```

---

### Task 7: Wire everything in GraphTab

**Files:**
- Modify: `frontend/src/components/workflows/graph/GraphTab.tsx`

**Interfaces:**
- Consumes: `PaletteSidebar` + `EdgeMode` (Task 5), `GraphEditor` + `DropPayload` (Task 6), `GraphUsersProvider` (Task 3), `layoutVertical` + `allPositionsZero` (Task 1), `useUsers`, `nextNodeKey`.
- Produces: no new exports (internal wiring only).

- [ ] **Step 1: Update imports and add state**

At the top of `GraphTab.tsx`, add imports:

```tsx
import PaletteSidebar, { type EdgeMode } from "./PaletteSidebar";
import type { DropPayload } from "./GraphEditor";
import { GraphUsersProvider } from "./GraphUsersContext";
import { layoutVertical, allPositionsZero } from "../../../lib/graphLayout";
import { useUsers } from "../../../hooks/useUsers";
```

Inside the component, after the existing `const [dirty, setDirty] = useState(false);` line, add:

```tsx
const [edgeMode, setEdgeMode] = useState<EdgeMode>("transition");
const users = useUsers();
```

- [ ] **Step 2: Auto-layout on fresh load + add helpers**

Change the resync effect so a fresh graph (all positions 0) is auto-laid-out top→bottom on load. Replace the existing resync `useEffect` body:

```tsx
  // Resync baseline from server on load / after save.
  useEffect(() => {
    if (!graph.data) return;
    const rf = toReactFlow(graph.data);
    const laid = allPositionsZero(rf.nodes)
      ? layoutVertical(rf.nodes, rf.edges)
      : rf.nodes;
    setNodes(laid);
    setEdges(rf.edges);
    setDirty(false);
  }, [graph.data]);
```

Add an auto-layout handler and a drop handler alongside the existing `addNode` function:

```tsx
  function autoLayout() {
    setNodes((ns) => layoutVertical(ns, edges));
    setDirty(true);
  }

  function addNodeFromDrop(payload: DropPayload, position: { x: number; y: number }) {
    const key = nextNodeKey(nodes.map((n) => n.data.nodeKey));
    const isAgent = payload.kind === "agent";
    setNodes((ns) => [
      ...ns,
      {
        id: key,
        type: "agent",
        position,
        data: {
          label: isAgent ? payload.name : key,
          agentId: isAgent ? payload.agentId : "",
          nodeKey: key,
          approverUserIds: [],
        },
      },
    ]);
    setSelectedId(key);
    setDirty(true);
  }
```

- [ ] **Step 3: Update the render tree (3-column layout + provider + toolbar button)**

Replace the returned JSX's outer content region (the `<div style={{ display: "flex", gap: "var(--space-4)"... }}>` block) so the palette is the left column, the canvas is center wrapped in the users provider, and the inspector stays right:

```tsx
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
        <PaletteSidebar
          edgeMode={edgeMode}
          onEdgeModeChange={setEdgeMode}
          onAutoLayout={autoLayout}
        />
        <div style={{ flex: 1 }}>
          <GraphUsersProvider users={users.data ?? []}>
            <GraphEditor
              nodes={nodes}
              edges={edges}
              edgeMode={edgeMode}
              onNodesChange={(c) => {
                setNodes((ns) => applyNodeChanges(c, ns));
                if (c.some((ch) => STRUCTURAL_NODE_CHANGES.has(ch.type))) setDirty(true);
              }}
              onEdgesChange={(c) => {
                setEdges((es) => applyEdgeChanges(c, es));
                if (c.some((ch) => STRUCTURAL_EDGE_CHANGES.has(ch.type))) setDirty(true);
              }}
              onConnect={(conn) => { setEdges((es) => addEdge(conn, es)); setDirty(true); }}
              onSelectNode={setSelectedId}
              onDropNode={addNodeFromDrop}
            />
          </GraphUsersProvider>
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
```

Note: `edges` state stays forward-only. `onEdgesChange` will never receive `rb:`-prefixed edges because React Flow only fires changes for edges the user can interact with, and rollback overlay edges are `selectable:false`/`deletable:false`/`focusable:false`. As a defensive guard, confirm `toDefinition` is unaffected in Step 4.

- [ ] **Step 4: Verify save payload is still forward-only (guard check)**

Run:
```bash
cd frontend && node -e "const s=require('fs').readFileSync('src/components/workflows/graph/GraphTab.tsx','utf8'); if(!s.includes('addNodeFromDrop')||!s.includes('GraphUsersProvider')||!s.includes('autoLayout')) throw new Error('GraphTab not fully wired'); if(!s.includes('toDefinition(nodes, edges)')) throw new Error('save path changed unexpectedly'); console.log('ok');"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workflows/graph/GraphTab.tsx
git commit -m "feat(graph): wire palette, users provider, drop-create, auto-layout into GraphTab"
```

---

### Task 8: Manual end-to-end verification

**Files:** none (verification only).

- [ ] **Step 1: Start the frontend dev server (user-run)**

Ask the user to run (interactive / long-running, so they run it): `! cd frontend && npm run dev`
Then open a workflow detail → Graph tab.

- [ ] **Step 2: Verify each acceptance point**

Confirm visually:
- Graph renders top→bottom; "Sắp xếp dọc" re-lays it vertically.
- A gated node shows approver initials chips; hover shows full emails.
- Dashed warning-colored rollback edges run from each gated node back to its parents; "Rollback" mode emphasizes them and dims forward edges.
- Dragging an Agent from the left palette onto the canvas creates a node bound to that agent at the drop point; "Blank node" creates an unbound node.
- Save still works and reload shows the same forward graph (no `rb:` edges persisted).

- [ ] **Step 3: Commit any polish fixes discovered**

```bash
git add -A && git commit -m "fix(graph): post-verification polish"
```
(Skip if nothing to fix.)

---

## Self-Review

**Spec coverage:**
- Vertical layout (#1) → Task 1 + Task 7 (auto-layout on fresh load + button). ✓
- Approver display (#2) → Task 3 (context) + Task 4 (avatars). ✓
- Rollback dashed edges (#3) → Task 2 (derive) + Task 6 (render + emphasis). ✓
- Drag-drop palette (#4: agent list, blank node, edge-mode toggle, auto-layout) → Task 5 + Task 6 (drop) + Task 7 (wire). ✓
- Display-only / no-persist rollback → Task 2 id-prefix + `selectable/deletable/focusable:false`; Task 7 keeps `edges` forward-only + guard check. ✓
- No backend/API/model change → all files under `frontend/src`; save path `toDefinition(nodes, edges)` unchanged. ✓
- No tests (CLAUDE.md override) → verification via `node` smoke checks + manual E2E only. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `EdgeMode` = `"transition"|"rollback"` used identically in Tasks 5/6/7. `DropPayload` defined in Task 6, imported in Task 7. `NODE_DND_MIME` defined Task 5, used Task 6. `RFNodeData` fields (`approverUserIds`, `agentId`, `nodeKey`, `label`) consistent across Tasks 1/2/4/7. `layoutVertical`/`allPositionsZero`/`deriveRollbackEdges` names consistent between definition and use. ✓

## Open questions

None.
