# Workflow Graph Editor Upgrades — Design

Date: 2026-07-19
Status: Approved
Scope: Frontend only (no backend / DB changes, no new tests)

## Goal

Three improvements to the workflow config (graph) experience:

1. **Full-viewport canvas** — the React Flow pane fills the browser height instead of a fixed 560px.
2. **Chat command sidebar** — a right-side chat panel that edits the *current* flow via deterministic commands.
3. **Templates & duplicate at creation** — new workflows can start from a template (empty nodes) or duplicate an existing workflow's graph.

## Context (current state)

- `GraphTab.tsx` — owns `nodes`/`edges` state, load/save, validation. Renders a 3-column flex **row** (`PaletteSidebar` · `GraphEditor` · `NodeInspector` 300px) inside a growing **column**.
- `GraphEditor.tsx` — controlled React Flow canvas, hard-coded `height: 560` wrapper.
- `chat/` (`chatStore.ts`) — an existing **mock-reply** chat shell (localStorage, fake streamed bot replies). Not reused for graph editing.
- Workflow creation: `workflows.tsx` "New Workflow" → `navigate("/workflows/new")` → `WorkflowDetailShell` (Graph tab disabled while `isNew`) → `DefinitionTab` `create.mutateAsync({name,description,constraints})` → on save navigate to `/workflows/:id`.
- Graph persistence is a **separate** endpoint: `PUT /workflows/{id}/graph-definition` (`putWorkflowGraph`). A workflow id must exist before its graph can be seeded.

## §1 — Full-viewport canvas

**`GraphTab.tsx`**
- Root wrapper: `height: calc(100vh - var(--app-header-offset, 220px))`, `display:flex; flex-direction:column; gap:var(--space-3)`.
  (`--app-header-offset` accounts for the shell header + tab bar + toolbar; a static fallback is fine — tune the value to the shell.)
- Toolbar: keep at top, `flex-shrink:0`.
- Body row: `display:flex; gap:var(--space-4); flex:1; min-height:0; align-items:stretch`.
  `min-height:0` is required so the flex child can shrink and give React Flow a real measured height.
- Center column (GraphEditor wrapper): `flex:1; min-width:0`.

**`GraphEditor.tsx`**
- Canvas outer `<div>`: `height: 560` → `height: "100%"` (keep border/radius). Parent flex sizing now drives it. `fitView` unchanged.

Result: canvas grows/shrinks with the window; pan/zoom internal behavior unchanged.

## §2 — Right column: Inspector | Chat toggle

Replace the bare `<NodeInspector>` right column with a new **`GraphRightPanel`** (300px, `flex-shrink:0`, full height, its own scroll):

- Segmented toggle at top: **`Inspector`** | **`Chat`**.
- `Inspector` view → existing `NodeInspector` (unchanged props).
- `Chat` view → new **`GraphChatPanel`**.

**`GraphChatPanel.tsx`** — message log (scrolling) + composer (reuse styling of `chat-composer` where practical, but standalone). Backed by a new **`useGraphChat`** hook holding local `ChatMessage[]` (no persistence, no mock bot). On submit it:
1. appends the user message,
2. parses via `lib/graphChatCommands.ts`,
3. runs the resulting action against callbacks passed down from `GraphTab`,
4. appends an assistant confirmation or error message.

**`lib/graphChatCommands.ts`** — pure parser. `parseGraphCommand(text): GraphCommand | { kind: "unknown" }`. Case-insensitive, trims, supports EN + VN keywords:

| Command | Patterns |
|---|---|
| Add node | `add node <label>` · `thêm node <label>` |
| Assign agent | `set agent <agentName> on <node>` · `gán agent <agentName> cho <node>` |
| Connect | `connect <A> -> <B>` · `nối <A> -> <B>` (accept `->`, `→`, `to`) |
| Delete node | `delete node <node>` · `xoá node <node>` / `xóa node <node>` |
| List / help | `list` · `help` |

**Resolution & actions** (executed in `GraphTab`, which owns state):
- Node lookup: match `<node>` against `nodeKey` first, then `label` (case-insensitive). Ambiguity/absence → error message, no mutation.
- Agent lookup: fuzzy match `<agentName>` against `useAgents` names (case-insensitive contains, unique). No match / multiple → error.
- Add node → reuse `addNode` logic but honor the provided label; return the new key in the confirmation.
- Assign agent → patch that node's `agentId` (+ `label` if it was the key) by node key.
- Connect → `addEdge({source,target})` after verifying both nodes exist; reject self/duplicate.
- Delete node → `deleteNode(id)`.
- `list` → echo current nodes (`key — label — agent?`) and edge count. `help` → usage lines.

Every command that mutates sets `dirty` (via the existing setters). No backend. **No `apply template` command** — templates are creation-time only (§3).

New callback surface passed `GraphTab → GraphRightPanel → GraphChatPanel`:
- `agents: Agent[]`, `nodes`, `edges` (read),
- `addNamedNode(label): string` (returns key),
- `assignAgent(nodeRef, agentName): Result`,
- `connect(aRef, bRef): Result`,
- `removeNode(nodeRef): Result`.
(These wrap existing `GraphTab` mutators; resolution helpers live in a small `graphChatActions` module or inline in `GraphTab`.)

## §3 — Templates & duplicate at workflow creation

### "Start from" modal

**`NewWorkflowModal.tsx`** — opened from `workflows.tsx` "New Workflow" buttons (both header and empty-state), replacing the direct `navigate("/workflows/new")`.

Options:
- **Blank** — current behavior (empty graph).
- **Template** — pick one of the built-in templates (§ below).
- **Duplicate** — searchable list of existing workflows (reuse `useWorkflows`); on confirm, fetch source graph via `getWorkflowGraph(sourceId)`.

On confirm the modal stores the chosen **seed** and navigates to `/workflows/new`. Seed is passed via **React Router location state** (`navigate("/workflows/new", { state: { seed } })`) so it survives the route change without global singletons. Seed shape:
```ts
type CreateSeed =
  | { kind: "blank" }
  | { kind: "template"; templateId: string; defaultName?: string }
  | { kind: "duplicate"; sourceId: string; def: GraphDefinition; defaultName: string };
```

### `lib/graphTemplates.ts`

Each template: `{ id, name, description, build(): GraphDefinition }`. Nodes get labels + layout but **empty `agent_id`** (and empty `config`, `approver_user_ids` unless the template intends approvers). Positions via existing `layoutVertical`.

Starter templates:
- **linear** — Linear pipeline: `A → B → C`.
- **approval** — Approval chain: `Task → Review → Approve` (Review may carry an approver slot; left empty for the user).
- **fanout** — Fan-out / Fan-in: `Source → {Branch 1, Branch 2} → Join`.

### Creation flow wiring (`DefinitionTab.tsx`)

While `isNew`, read `location.state.seed`:
- Prefill `name` from `seed.defaultName` (e.g. Duplicate → `"<source> (copy)"`) when present.
- After `create.mutateAsync(payload)` returns the new workflow:
  - `template` → `putWorkflowGraph(saved.id, template.build())`.
  - `duplicate` → `putWorkflowGraph(saved.id, seed.def)`.
  - `blank` → skip.
- Then `onSaved(saved)` → navigate to `/workflows/:id`; user opens Graph tab to fill agents into the blank nodes and Save.

Failure of the graph-seed PUT surfaces a toast/inline error but the workflow record still exists (user can still edit its graph manually).

## Files touched

Modified: `GraphTab.tsx`, `GraphEditor.tsx`, `DefinitionTab.tsx`, `workflows.tsx`.
New: `graph/GraphRightPanel.tsx`, `graph/GraphChatPanel.tsx`, `hooks/useGraphChat.ts`, `lib/graphChatCommands.ts`, `lib/graphTemplates.ts`, `workflows/NewWorkflowModal.tsx`.

## Non-goals / YAGNI

- No backend or DB changes (reuse existing POST `/workflows`, PUT `/workflows/{id}/graph-definition`).
- No LLM/AI in chat — deterministic parser only.
- No chat persistence across sessions.
- No new automated tests (per project override).
- No template management UI (templates are code-defined constants).

## Open questions

- Exact `--app-header-offset` value (tune against the running shell during implementation).
- Whether Duplicate should also copy workflow `constraints`/`confidence_threshold` (default: copy name + description + constraints; graph via PUT). Confirm during implementation if constraints copy is desired.
