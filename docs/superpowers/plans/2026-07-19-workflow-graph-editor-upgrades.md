# Workflow Graph Editor Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the workflow graph canvas fill the viewport, add a right-side chat panel that edits the current flow via deterministic commands, and let new workflows start from a template (empty nodes) or by duplicating an existing workflow.

**Architecture:** Pure-frontend. §1 is a flexbox/height change in `GraphTab`/`GraphEditor`. §2 adds a `GraphRightPanel` (Inspector|Chat toggle) driving a deterministic command parser against `GraphTab`'s existing state mutators. §3 adds a "Start from" modal at workflow creation that stashes a seed in router state; `DefinitionTab` seeds the new workflow's graph via the existing `PUT /workflows/{id}/graph-definition` after the record is created.

**Tech Stack:** React + TypeScript, `@xyflow/react` (React Flow v12), TanStack Query, React Router, existing `vaic-*` CSS design tokens.

## Global Constraints

- **No automated tests** — project override (`CLAUDE.md`): do not write or run tests.
- **Do not auto-run** typecheck / lint / build / format — only when the user asks. Verification steps in this plan are **manual (visual in the running app)**.
- **No backend or DB changes** — reuse existing endpoints: `POST /workflows`, `PATCH /workflows/{id}`, `PUT /workflows/{id}/graph-definition`, `GET /workflows/{id}/graph-definition`.
- **No new dependencies.**
- Follow existing file conventions: inline-style + `vaic-*` tokens, kebab-case for new `chat/`-style files, PascalCase for existing `graph/` component files (match the directory each file lands in).
- Commit after each task. Commit trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- Graph seed nodes MUST have empty `agent_id` (user fills agents after).

---

### Task 1: Full-viewport canvas

**Files:**
- Modify: `frontend/src/components/workflows/graph/GraphEditor.tsx` (canvas wrapper height)
- Modify: `frontend/src/components/workflows/graph/GraphTab.tsx` (root + body-row layout)

**Interfaces:**
- Consumes: nothing new.
- Produces: `GraphTab` renders a full-height flex column; the body row is a flex row with `flex:1; min-height:0` so React Flow gets a measured height. No prop changes.

- [ ] **Step 1: Make the canvas fill its parent**

In `GraphEditor.tsx`, change the canvas wrapper `<div>` (currently `height: 560`):

```tsx
  return (
    <div style={{ height: "100%", border: "1px solid var(--color-border)", borderRadius: 8 }}>
      <ReactFlow
```

(Only the `height` value changes: `560` → `"100%"`. Everything else in that div stays.)

- [ ] **Step 2: Make GraphTab a full-height flex column**

In `GraphTab.tsx`, replace the outer wrapper and the body row in the returned JSX. The current return is:

```tsx
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <GraphToolbar ... />
      <div style={{ display: "flex", gap: "var(--space-4)", alignItems: "flex-start" }}>
```

Change to:

```tsx
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
        // Fill the space below the shell header + tab bar. Tune the offset to
        // the running shell if the toolbar/header height changes.
        height: "calc(100vh - 240px)",
        minHeight: 480,
      }}
    >
      <GraphToolbar ... />
      <div
        style={{
          display: "flex",
          gap: "var(--space-4)",
          alignItems: "stretch",
          flex: 1,
          minHeight: 0,
        }}
      >
```

(Leave the `GraphToolbar` props exactly as they are — only its wrapping container changes. The `GraphToolbar` element is naturally `flex-shrink` because the row below it takes `flex:1`.)

- [ ] **Step 3: Give the center column flex sizing**

Still in `GraphTab.tsx`, the center column currently is `<div style={{ flex: 1 }}>` wrapping `GraphUsersProvider`. Change it to also clamp width and height:

```tsx
        <div style={{ flex: 1, minWidth: 0, minHeight: 0 }}>
          <GraphUsersProvider users={users.data ?? []}>
            <GraphEditor ... />
          </GraphUsersProvider>
        </div>
```

Leave `PaletteSidebar` and the `NodeInspector` column unchanged in this task (the right column becomes `GraphRightPanel` in Task 6).

- [ ] **Step 4: Manual verify**

Run the frontend the way the project normally does (ask the user if unsure — do not assume a command). In the browser: open a workflow → Graph tab. Confirm the canvas now stretches to near the bottom of the window, resizes when the window resizes, and pan/zoom still works. No console errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workflows/graph/GraphEditor.tsx frontend/src/components/workflows/graph/GraphTab.tsx
git commit -m "feat(graph): full-viewport canvas layout

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Graph templates module

**Files:**
- Create: `frontend/src/lib/graphTemplates.ts`

**Interfaces:**
- Consumes: `GraphDefinition`, `GraphDefinitionNode`, `GraphDefinitionEdge` from `./workflowGraphApi`.
- Produces:
  - `type CreateSeed` — discriminated union used by Task 3 (modal) and Task 4 (DefinitionTab).
  - `interface GraphTemplate { id: string; name: string; description: string; build(): GraphDefinition }`
  - `const GRAPH_TEMPLATES: GraphTemplate[]`
  - `function getTemplate(id: string): GraphTemplate | undefined`

- [ ] **Step 1: Write the module**

```ts
/* Frontend-defined starter graphs for new workflows. Each build() returns a
 * GraphDefinition whose nodes have an EMPTY agent_id — the user fills agents
 * in the graph editor after creation. Positions are hand-laid top->bottom so
 * no layout pass is needed at seed time. */

import type {
  GraphDefinition,
  GraphDefinitionNode,
} from "./workflowGraphApi";

/** How a new workflow's graph should be seeded (chosen in NewWorkflowModal). */
export type CreateSeed =
  | { kind: "blank" }
  | { kind: "template"; templateId: string; defaultName: string }
  | { kind: "duplicate"; sourceId: string; def: GraphDefinition; defaultName: string };

export interface GraphTemplate {
  id: string;
  name: string;
  description: string;
  build(): GraphDefinition;
}

const ROW = 160;
const COL = 240;

/** Blank node with the given key/label at (x,y). agent_id intentionally "". */
function node(key: string, label: string, x: number, y: number): GraphDefinitionNode {
  return {
    node_key: key,
    label,
    agent_id: "",
    config: {},
    position: { x, y },
    approver_user_ids: [],
  };
}

export const GRAPH_TEMPLATES: GraphTemplate[] = [
  {
    id: "linear",
    name: "Linear pipeline",
    description: "Three steps in sequence: A → B → C.",
    build: () => ({
      nodes: [
        node("n1", "Step 1", 0, 0),
        node("n2", "Step 2", 0, ROW),
        node("n3", "Step 3", 0, ROW * 2),
      ],
      edges: [
        { from: "n1", to: "n2" },
        { from: "n2", to: "n3" },
      ],
    }),
  },
  {
    id: "approval",
    name: "Approval chain",
    description: "Task → Review → Approve.",
    build: () => ({
      nodes: [
        node("n1", "Task", 0, 0),
        node("n2", "Review", 0, ROW),
        node("n3", "Approve", 0, ROW * 2),
      ],
      edges: [
        { from: "n1", to: "n2" },
        { from: "n2", to: "n3" },
      ],
    }),
  },
  {
    id: "fanout",
    name: "Fan-out / Fan-in",
    description: "One source fans out to two branches, then joins.",
    build: () => ({
      nodes: [
        node("n1", "Source", 0, 0),
        node("n2", "Branch 1", -COL / 2, ROW),
        node("n3", "Branch 2", COL / 2, ROW),
        node("n4", "Join", 0, ROW * 2),
      ],
      edges: [
        { from: "n1", to: "n2" },
        { from: "n1", to: "n3" },
        { from: "n2", to: "n4" },
        { from: "n3", to: "n4" },
      ],
    }),
  },
];

export function getTemplate(id: string): GraphTemplate | undefined {
  return GRAPH_TEMPLATES.find((t) => t.id === id);
}
```

- [ ] **Step 2: Manual verify (type-level)**

Open the file in the editor; confirm imports resolve (no red squiggles on `GraphDefinition`/`GraphDefinitionNode`). No runtime step — module is consumed in later tasks.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/graphTemplates.ts
git commit -m "feat(workflow): frontend graph templates + CreateSeed type

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: "Start from" modal at workflow creation

**Files:**
- Create: `frontend/src/components/workflows/NewWorkflowModal.tsx`
- Modify: `frontend/src/routes/workflows.tsx` (open modal instead of navigating directly)

**Interfaces:**
- Consumes: `GRAPH_TEMPLATES`, `CreateSeed` (Task 2); `useWorkflows` (`../hooks/useWorkflows`); `getWorkflowGraph` (`../lib/workflowGraphApi`); `Button` (`../components/ui`).
- Produces: `NewWorkflowModal` with props `{ open: boolean; onCancel(): void; onConfirm(seed: CreateSeed): void }`. On confirm it resolves the seed (for Duplicate it fetches the source graph first) and calls `onConfirm`.

- [ ] **Step 1: Write the modal**

Create `frontend/src/components/workflows/NewWorkflowModal.tsx`. Mirrors the overlay/dialog pattern from `chat/chat-new-chat-modal.tsx`.

```tsx
/* "Start from" modal for creating a workflow: Blank, a Template, or Duplicate
 * an existing workflow. On confirm it resolves a CreateSeed (fetching the
 * source graph for Duplicate) and hands it back to the caller. */

import { useEffect, useRef, useState } from "react";
import { durations, easings } from "../../lib/motion";
import { Button } from "../ui";
import { useWorkflows } from "../../hooks/useWorkflows";
import { getWorkflowGraph } from "../../lib/workflowGraphApi";
import { GRAPH_TEMPLATES, type CreateSeed } from "../../lib/graphTemplates";

type Mode = "blank" | "template" | "duplicate";

interface Props {
  open: boolean;
  onCancel: () => void;
  onConfirm: (seed: CreateSeed) => void;
}

export default function NewWorkflowModal({ open, onCancel, onConfirm }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<Mode>("blank");
  const [templateId, setTemplateId] = useState(GRAPH_TEMPLATES[0]?.id ?? "");
  const [sourceId, setSourceId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: workflows } = useWorkflows({});

  useEffect(() => {
    if (!open) return;
    setMode("blank");
    setTemplateId(GRAPH_TEMPLATES[0]?.id ?? "");
    setSourceId("");
    setBusy(false);
    setError(null);
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    const t = window.setTimeout(() => dialogRef.current?.focus(), 0);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.clearTimeout(t);
    };
  }, [open, onCancel]);

  if (!open) return null;

  async function confirm() {
    setError(null);
    if (mode === "blank") {
      onConfirm({ kind: "blank" });
      return;
    }
    if (mode === "template") {
      const t = GRAPH_TEMPLATES.find((x) => x.id === templateId);
      if (!t) {
        setError("Pick a template.");
        return;
      }
      onConfirm({ kind: "template", templateId: t.id, defaultName: t.name });
      return;
    }
    // duplicate
    const src = (workflows ?? []).find((w) => w.id === sourceId);
    if (!src) {
      setError("Pick a workflow to duplicate.");
      return;
    }
    try {
      setBusy(true);
      const def = await getWorkflowGraph(src.id);
      onConfirm({
        kind: "duplicate",
        sourceId: src.id,
        def,
        defaultName: `${src.name} (copy)`,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load source graph");
    } finally {
      setBusy(false);
    }
  }

  const modeButton = (m: Mode, label: string) => (
    <Button variant={mode === m ? "primary" : "ghost"} onClick={() => setMode(m)}>
      {label}
    </Button>
  );

  return (
    <div
      role="presentation"
      className="vaic-confirm-overlay"
      style={{ animationDuration: `${durations.modal}ms`, animationTimingFunction: easings.modal }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="vaic-new-wf-title"
        tabIndex={-1}
        className="vaic-confirm-dialog"
        style={{ animationDuration: `${durations.modal}ms`, animationTimingFunction: easings.modal }}
      >
        <h3 id="vaic-new-wf-title" className="text-h3">Start a new workflow</h3>
        <p className="text-body" style={{ color: "var(--color-text-tertiary)", textWrap: "pretty" }}>
          Start from scratch, a template, or by duplicating an existing workflow.
        </p>

        <div style={{ display: "flex", gap: "var(--space-2)", margin: "var(--space-3) 0" }}>
          {modeButton("blank", "Blank")}
          {modeButton("template", "Template")}
          {modeButton("duplicate", "Duplicate")}
        </div>

        {mode === "template" && (
          <div className="vaic-form-field">
            <label className="vaic-form-label">Template</label>
            <select
              className="vaic-form-input vaic-focusable"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
            >
              {GRAPH_TEMPLATES.map((t) => (
                <option key={t.id} value={t.id}>{t.name} — {t.description}</option>
              ))}
            </select>
          </div>
        )}

        {mode === "duplicate" && (
          <div className="vaic-form-field">
            <label className="vaic-form-label">Duplicate from</label>
            <select
              className="vaic-form-input vaic-focusable"
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
            >
              <option value="">— choose workflow —</option>
              {(workflows ?? []).map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
        )}

        {error && (
          <div className="vaic-inline-alert" role="alert" style={{ marginTop: "var(--space-2)" }}>
            {error}
          </div>
        )}

        <div className="vaic-confirm-actions">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button variant="primary" disabled={busy} onClick={confirm}>
            {busy ? "Loading…" : "Continue"}
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire the modal into the workflows list**

In `frontend/src/routes/workflows.tsx`:

1. Add imports at the top (after existing imports):

```tsx
import NewWorkflowModal from "../components/workflows/NewWorkflowModal";
import type { CreateSeed } from "../lib/graphTemplates";
```

2. Add modal open state inside `WorkflowsPage` (next to the other `useState` calls):

```tsx
  const [newOpen, setNewOpen] = useState(false);
```

3. Replace BOTH `onClick={() => navigate("/workflows/new")}` handlers (the empty-state action button and the header button) with `onClick={() => setNewOpen(true)}`.

4. Add a confirm handler inside the component:

```tsx
  function handleNewConfirm(seed: CreateSeed) {
    setNewOpen(false);
    navigate("/workflows/new", { state: { seed } });
  }
```

5. Render the modal at the end of the returned JSX, just before the closing `</div>` of `vaic-workflows-page`:

```tsx
      <NewWorkflowModal
        open={newOpen}
        onCancel={() => setNewOpen(false)}
        onConfirm={handleNewConfirm}
      />
```

- [ ] **Step 3: Manual verify**

In the app: Workflows list → New Workflow → modal opens. Toggle Blank/Template/Duplicate. In Duplicate, the workflow dropdown lists existing workflows. Click Continue → navigates to `/workflows/new` (blank form for now — seeding is Task 4). No console errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workflows/NewWorkflowModal.tsx frontend/src/routes/workflows.tsx
git commit -m "feat(workflow): Start-from modal (blank/template/duplicate) on create

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Seed the new workflow's graph on create

**Files:**
- Modify: `frontend/src/components/workflows/DefinitionTab.tsx`

**Interfaces:**
- Consumes: `CreateSeed`, `getTemplate` (Task 2); `putWorkflowGraph` (`../../lib/workflowGraphApi`); `useLocation` (`react-router-dom`).
- Produces: when `isNew` and a seed is present in router state, prefills the Name field from the seed's default name and, after the workflow record is created, seeds its graph via `putWorkflowGraph` before `onSaved` navigates away.

- [ ] **Step 1: Read the seed and prefill the name**

In `DefinitionTab.tsx`, add imports:

```tsx
import { useLocation } from "react-router-dom";
import { getTemplate, type CreateSeed } from "../../lib/graphTemplates";
import { putWorkflowGraph } from "../../lib/workflowGraphApi";
```

Inside the component, read the seed and use it as the default name when creating:

```tsx
  const location = useLocation();
  const seed = isNew ? ((location.state as { seed?: CreateSeed } | null)?.seed ?? null) : null;
```

Change the initial form state so a new workflow's name defaults to the seed name. Replace:

```tsx
  const initial = toFormState(workflow);
```

with:

```tsx
  const initial = toFormState(workflow);
  if (isNew && seed && seed.kind !== "blank" && !initial.name) {
    initial.name = seed.defaultName;
  }
```

(`toFormState` returns a fresh object each call, so mutating `initial` here is safe.)

- [ ] **Step 2: Seed the graph after create**

In `handleSave`, after the create/update branch, seed the graph when this was a new workflow with a non-blank seed. Replace the existing `try` block body:

```tsx
    try {
      const saved = isNew
        ? await create.mutateAsync(payload)
        : await update.mutateAsync(payload);
      show("Workflow saved");
      onSaved?.(saved);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save Workflow");
    }
```

with:

```tsx
    try {
      const saved = isNew
        ? await create.mutateAsync(payload)
        : await update.mutateAsync(payload);

      // Seed the new workflow's graph from the chosen template / source.
      if (isNew && seed && seed.kind !== "blank") {
        try {
          const def =
            seed.kind === "template"
              ? getTemplate(seed.templateId)?.build()
              : seed.def;
          if (def) await putWorkflowGraph(saved.id, def);
        } catch (graphErr) {
          // The record exists; surface the seeding failure but still proceed —
          // the user can build the graph manually in the Graph tab.
          show(
            graphErr instanceof Error
              ? `Workflow created, but seeding the graph failed: ${graphErr.message}`
              : "Workflow created, but seeding the graph failed.",
            "error",
          );
        }
      }

      show("Workflow saved");
      onSaved?.(saved);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save Workflow");
    }
```

- [ ] **Step 3: Manual verify**

In the app: New Workflow → Template → Linear pipeline → Continue → fill Description → Save. Should navigate to `/workflows/:id`; open Graph tab and confirm 3 blank nodes (Step 1/2/3) connected in a line, each with no agent. Repeat with Duplicate on a workflow that has a graph → new workflow shows a copy of that graph (agents preserved from source `def`). Repeat with Blank → empty graph as before.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workflows/DefinitionTab.tsx
git commit -m "feat(workflow): seed new-workflow graph from template/duplicate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Graph chat command parser

**Files:**
- Create: `frontend/src/lib/graphChatCommands.ts`

**Interfaces:**
- Consumes: nothing (pure string parsing).
- Produces:
  - `type GraphCommand` — discriminated union:
    - `{ kind: "add_node"; label: string }`
    - `{ kind: "assign_agent"; nodeRef: string; agentName: string }`
    - `{ kind: "connect"; from: string; to: string }`
    - `{ kind: "delete_node"; nodeRef: string }`
    - `{ kind: "list" }`
    - `{ kind: "help" }`
    - `{ kind: "unknown" }`
  - `function parseGraphCommand(text: string): GraphCommand`

- [ ] **Step 1: Write the parser**

```ts
/* Deterministic parser for the graph-editing chat panel. No AI: maps a small
 * set of EN + VN command phrases to structured GraphCommand objects. The
 * caller (GraphTab) resolves node/agent references and performs the mutation. */

export type GraphCommand =
  | { kind: "add_node"; label: string }
  | { kind: "assign_agent"; nodeRef: string; agentName: string }
  | { kind: "connect"; from: string; to: string }
  | { kind: "delete_node"; nodeRef: string }
  | { kind: "list" }
  | { kind: "help" }
  | { kind: "unknown" };

/** Normalize separators used in "connect A -> B": ->, →, or the word "to". */
function splitConnect(rest: string): [string, string] | null {
  const m = rest.match(/^(.+?)\s*(?:->|→|\bto\b)\s*(.+)$/i);
  if (!m) return null;
  const from = m[1].trim();
  const to = m[2].trim();
  if (!from || !to) return null;
  return [from, to];
}

export function parseGraphCommand(text: string): GraphCommand {
  const t = text.trim();
  const lower = t.toLowerCase();

  if (lower === "help" || lower === "?" || lower === "trợ giúp") {
    return { kind: "help" };
  }
  if (lower === "list" || lower === "danh sách" || lower === "liệt kê") {
    return { kind: "list" };
  }

  // add node <label> | thêm node <label>
  let m = t.match(/^(?:add node|thêm node)\s+(.+)$/i);
  if (m) return { kind: "add_node", label: m[1].trim() };

  // set agent <agentName> on <node> | gán agent <agentName> cho <node>
  m = t.match(/^(?:set agent|gán agent)\s+(.+?)\s+(?:on|cho)\s+(.+)$/i);
  if (m) return { kind: "assign_agent", agentName: m[1].trim(), nodeRef: m[2].trim() };

  // connect <A> -> <B> | nối <A> -> <B>
  m = t.match(/^(?:connect|nối|noi)\s+(.+)$/i);
  if (m) {
    const pair = splitConnect(m[1]);
    if (pair) return { kind: "connect", from: pair[0], to: pair[1] };
  }

  // delete node <node> | xoá node <node> | xóa node <node>
  m = t.match(/^(?:delete node|xoá node|xóa node|remove node)\s+(.+)$/i);
  if (m) return { kind: "delete_node", nodeRef: m[1].trim() };

  return { kind: "unknown" };
}
```

- [ ] **Step 2: Manual verify (mental trace)**

Confirm each supported phrase maps as expected, e.g. `parseGraphCommand("connect Step 1 -> Step 2")` → `{kind:"connect", from:"Step 1", to:"Step 2"}`; `parseGraphCommand("gán agent Reviewer cho Review")` → `{kind:"assign_agent", agentName:"Reviewer", nodeRef:"Review"}`; unrecognized → `{kind:"unknown"}`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/graphChatCommands.ts
git commit -m "feat(graph): deterministic chat command parser

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Chat panel + Inspector|Chat toggle, wired to GraphTab

**Files:**
- Create: `frontend/src/hooks/useGraphChat.ts`
- Create: `frontend/src/components/workflows/graph/GraphChatPanel.tsx`
- Create: `frontend/src/components/workflows/graph/GraphRightPanel.tsx`
- Modify: `frontend/src/components/workflows/graph/GraphTab.tsx` (resolver callbacks + swap right column)

**Interfaces:**
- Consumes: `parseGraphCommand`, `GraphCommand` (Task 5); `NodeInspector`; React Flow `Node`/`Edge`; `RFNodeData`.
- Produces:
  - `useGraphChat({ run })` hook — holds `messages` and a `send(text)` that parses, calls the injected `run(cmd)` (returns a reply string), and appends user + assistant messages.
  - `GraphChatActions` interface — the resolver surface `GraphTab` implements.
  - `GraphRightPanel` — Inspector|Chat toggle wrapper.

- [ ] **Step 1: Write the chat hook**

Create `frontend/src/hooks/useGraphChat.ts`:

```ts
/* Local (non-persisted) chat state for the graph-editing side panel. Each
 * send() parses the text, runs the command via the injected resolver, and
 * records the user message + the resolver's reply. No backend, no streaming. */

import { useCallback, useState } from "react";
import { parseGraphCommand } from "../lib/graphChatCommands";

export interface GraphChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

let seq = 0;
function nextId(): string {
  seq += 1;
  return `gcm-${seq}`;
}

const WELCOME =
  'Type a command to edit the flow. Try "help". Examples: "add node Review", ' +
  '"gán agent Reviewer cho Review", "connect Step 1 -> Step 2", "delete node Review".';

export function useGraphChat(opts: { run: (cmd: ReturnType<typeof parseGraphCommand>) => string }) {
  const { run } = opts;
  const [messages, setMessages] = useState<GraphChatMessage[]>([
    { id: nextId(), role: "assistant", content: WELCOME },
  ]);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      const cmd = parseGraphCommand(trimmed);
      const reply = run(cmd);
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", content: trimmed },
        { id: nextId(), role: "assistant", content: reply },
      ]);
    },
    [run],
  );

  return { messages, send };
}
```

- [ ] **Step 2: Write the chat panel**

Create `frontend/src/components/workflows/graph/GraphChatPanel.tsx`:

```tsx
/* Chat panel for the graph editor's right column. Renders the message log and
 * a composer; delegates command execution to the injected `send`. */

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";
import type { GraphChatMessage } from "../../../hooks/useGraphChat";

interface Props {
  messages: GraphChatMessage[];
  onSend: (text: string) => void;
}

export default function GraphChatPanel({ messages, onSend }: Props) {
  const [value, setValue] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  function submit() {
    const text = value.trim();
    if (!text) return;
    onSend(text);
    setValue("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "var(--space-2)", paddingBottom: "var(--space-2)" }}>
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "90%",
              padding: "6px 10px",
              borderRadius: 8,
              fontSize: 13,
              whiteSpace: "pre-wrap",
              background: m.role === "user" ? "var(--color-primary)" : "var(--color-surface-muted, #f1f1f1)",
              color: m.role === "user" ? "var(--color-primary-contrast, #fff)" : "var(--color-text-primary)",
              border: m.role === "user" ? "none" : "1px solid var(--color-border)",
            }}
          >
            {m.content}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: "var(--space-2)", paddingTop: "var(--space-2)", borderTop: "1px solid var(--color-border)" }}>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          placeholder='e.g. add node Review'
          style={{
            flex: 1,
            resize: "none",
            padding: "var(--space-2)",
            borderRadius: 8,
            border: "1px solid var(--color-border)",
            background: "var(--color-surface)",
            color: "var(--color-text-primary)",
            fontSize: 13,
            fontFamily: "inherit",
            outline: "none",
          }}
        />
        <button
          type="button"
          onClick={submit}
          disabled={!value.trim()}
          aria-label="Send"
          style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 36, height: 36, flexShrink: 0, borderRadius: 8, border: "none",
            background: "var(--color-primary)", color: "var(--color-primary-contrast, #fff)",
            cursor: value.trim() ? "pointer" : "not-allowed", opacity: value.trim() ? 1 : 0.5,
          }}
        >
          <SendHorizontal size={16} strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write the right-panel toggle wrapper**

Create `frontend/src/components/workflows/graph/GraphRightPanel.tsx`:

```tsx
/* Right column of the graph editor: a segmented Inspector|Chat toggle. */

import { useState } from "react";
import { Button } from "../../ui";
import NodeInspector, { type NodeInspectorProps } from "./NodeInspector";
import GraphChatPanel from "./GraphChatPanel";
import type { GraphChatMessage } from "../../../hooks/useGraphChat";

interface Props {
  inspector: NodeInspectorProps;
  chat: { messages: GraphChatMessage[]; onSend: (text: string) => void };
}

export default function GraphRightPanel({ inspector, chat }: Props) {
  const [view, setView] = useState<"inspector" | "chat">("inspector");
  return (
    <div style={{ width: 320, flexShrink: 0, display: "flex", flexDirection: "column", minHeight: 0, borderLeft: "1px solid var(--color-border)", paddingLeft: "var(--space-3)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
        <Button variant={view === "inspector" ? "primary" : "ghost"} onClick={() => setView("inspector")}>
          Inspector
        </Button>
        <Button variant={view === "chat" ? "primary" : "ghost"} onClick={() => setView("chat")}>
          Chat
        </Button>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflowY: view === "inspector" ? "auto" : "hidden" }}>
        {view === "inspector" ? <NodeInspector {...inspector} /> : <GraphChatPanel {...chat} />}
      </div>
    </div>
  );
}
```

Note: this imports `NodeInspectorProps` from `NodeInspector`. That type is already exported in `NodeInspector.tsx` (`export interface NodeInspectorProps`).

- [ ] **Step 4: Add resolver callbacks + swap the right column in GraphTab**

In `GraphTab.tsx`:

1. Add imports:

```tsx
import GraphRightPanel from "./GraphRightPanel";
import { useGraphChat } from "../../../hooks/useGraphChat";
import type { GraphCommand } from "../../../lib/graphChatCommands";
import { useAgents } from "../../../hooks/useAgents";
```

2. Load agents (for name→id resolution) near the other hooks:

```tsx
  const agents = useAgents({});
```

3. Add resolver helpers inside the component (after `deleteNode`, before `save`). These reuse existing state and setters:

```tsx
  // Resolve a chat node reference (by node key first, then case-insensitive label).
  function findNode(ref: string): Node<RFNodeData> | undefined {
    const byKey = nodes.find((n) => n.data.nodeKey === ref);
    if (byKey) return byKey;
    const low = ref.toLowerCase();
    return nodes.find((n) => n.data.label.toLowerCase() === low);
  }

  function runChatCommand(cmd: GraphCommand): string {
    switch (cmd.kind) {
      case "help":
        return [
          "Commands:",
          "• add node <label>",
          "• set agent <agent> on <node>  (or: gán agent <agent> cho <node>)",
          "• connect <A> -> <B>  (or: nối <A> -> <B>)",
          "• delete node <node>  (or: xoá node <node>)",
          "• list",
        ].join("\n");
      case "list": {
        if (nodes.length === 0) return "No nodes yet.";
        const lines = nodes.map((n) => {
          const agent = (agents.data ?? []).find((a) => a.id === n.data.agentId);
          return `• ${n.data.nodeKey} — ${n.data.label}${agent ? ` (${agent.name})` : " (no agent)"}`;
        });
        return `${lines.join("\n")}\n${edges.length} edge(s).`;
      }
      case "add_node": {
        const key = nextNodeKey(nodes.map((n) => n.data.nodeKey));
        setNodes((ns) => [
          ...ns,
          {
            id: key,
            type: "agent",
            position: { x: 80 + ns.length * 40, y: 80 + ns.length * 40 },
            data: { label: cmd.label, agentId: "", nodeKey: key, approverUserIds: [] },
          },
        ]);
        setSelectedId(key);
        setDirty(true);
        return `Added node "${cmd.label}" (${key}).`;
      }
      case "assign_agent": {
        const node = findNode(cmd.nodeRef);
        if (!node) return `Node "${cmd.nodeRef}" not found.`;
        const low = cmd.agentName.toLowerCase();
        const matches = (agents.data ?? []).filter((a) => a.name.toLowerCase().includes(low));
        if (matches.length === 0) return `Agent "${cmd.agentName}" not found.`;
        if (matches.length > 1) return `"${cmd.agentName}" matches ${matches.length} agents — be more specific.`;
        const agent = matches[0];
        setNodes((ns) => ns.map((n) => (n.id === node.id ? { ...n, data: { ...n.data, agentId: agent.id } } : n)));
        setDirty(true);
        return `Assigned agent "${agent.name}" to "${node.data.label}".`;
      }
      case "connect": {
        const from = findNode(cmd.from);
        const to = findNode(cmd.to);
        if (!from) return `Node "${cmd.from}" not found.`;
        if (!to) return `Node "${cmd.to}" not found.`;
        if (from.id === to.id) return "Cannot connect a node to itself.";
        const dup = edges.some((e) => e.source === from.id && e.target === to.id);
        if (dup) return `Edge ${from.data.label} -> ${to.data.label} already exists.`;
        setEdges((es) => addEdge({ source: from.id, target: to.id }, es));
        setDirty(true);
        return `Connected ${from.data.label} -> ${to.data.label}.`;
      }
      case "delete_node": {
        const node = findNode(cmd.nodeRef);
        if (!node) return `Node "${cmd.nodeRef}" not found.`;
        deleteNode(node.id);
        return `Deleted node "${node.data.label}".`;
      }
      default:
        return 'Unrecognized command. Type "help" for the list.';
    }
  }

  const chat = useGraphChat({ run: runChatCommand });
```

Note: `addEdge` is already imported in `GraphTab.tsx`. `nextNodeKey` is already imported.

4. Replace the right-column block. Currently:

```tsx
        <div style={{ width: 300, flexShrink: 0 }}>
          <NodeInspector
            node={selected}
            onChange={patchSelected}
            onDelete={() => selectedId && deleteNode(selectedId)}
          />
        </div>
```

Replace with:

```tsx
        <GraphRightPanel
          inspector={{
            node: selected,
            onChange: patchSelected,
            onDelete: () => selectedId && deleteNode(selectedId),
          }}
          chat={{ messages: chat.messages, onSend: chat.send }}
        />
```

5. Remove the now-unused direct `NodeInspector` import from `GraphTab.tsx` (it is rendered via `GraphRightPanel` now). Delete the line `import NodeInspector from "./NodeInspector";`.

- [ ] **Step 5: Manual verify**

In the app: open a workflow → Graph tab. Right column shows Inspector|Chat toggle. Inspector still edits the selected node. Switch to Chat:
- `add node Review` → new node appears, assistant confirms.
- `connect Step 1 -> Review` (adjust to real labels) → edge appears.
- `gán agent <an existing agent name> cho Review` → node's agent set (verify in Inspector).
- `delete node Review` → node + edges removed.
- `list` and `help` → sensible text.
- A nonsense line → "Unrecognized command" hint.
Each mutating command marks the graph dirty (Save button enables). No console errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useGraphChat.ts frontend/src/components/workflows/graph/GraphChatPanel.tsx frontend/src/components/workflows/graph/GraphRightPanel.tsx frontend/src/components/workflows/graph/GraphTab.tsx
git commit -m "feat(graph): Inspector|Chat right panel with flow-editing commands

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §1 full-viewport canvas → Task 1. ✓
- §2 chat command sidebar (Inspector|Chat toggle, parser, commands add/assign/connect/delete/list/help, no template command, marks dirty) → Tasks 5 (parser) + 6 (panel/toggle/resolvers). ✓
- §3 templates & duplicate at creation (Start-from modal, frontend templates with empty agent_id, seed via PUT after create, blank/template/duplicate) → Tasks 2 (templates+CreateSeed) + 3 (modal) + 4 (seed on create). ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:**
- `CreateSeed` defined in Task 2; consumed identically in Tasks 3 (`onConfirm(seed)`) and 4 (`location.state.seed`). ✓
- `GraphCommand` defined in Task 5; `runChatCommand(cmd: GraphCommand)` in Task 6 handles every variant incl. `unknown` (via `default`). ✓
- `useGraphChat({ run })` in Task 6 Step 1 matches usage in Step 4 (`useGraphChat({ run: runChatCommand })`). ✓
- `NodeInspectorProps` is already exported from `NodeInspector.tsx` (verified). ✓
- `putWorkflowGraph`, `getWorkflowGraph`, `GraphDefinition` names match `workflowGraphApi.ts`. ✓
- `create.mutateAsync` returns `Workflow` with `.id` (verified in `useWorkflowMutations` usage). ✓

## Open questions (carry from spec)

- Exact `calc(100vh - 240px)` offset — tune to the running shell in Task 1 Step 4.
- Whether Duplicate should also copy `constraints`/`confidence_threshold`. Current plan copies only the **graph** (via source `def`); Name defaults to "<source> (copy)", Description is left for the user. Confirm if constraints copy is wanted.
