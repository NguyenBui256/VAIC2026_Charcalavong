# Tracking — Realtime Personal Review Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a top-level **Tracking** section — a per-account realtime inbox of every workflow run where the current user is an approver, with a "your turn" signal, that deep-links into the existing `RunTrackingView` for Approve/Reject/Retry.

**Architecture:** Two new aggregate read endpoints (`GET /me/tracking`, `GET /me/tracking/summary`) in the orchestrator module compute per-run review status for the current user. One new call site in `graph_engine.graph_orchestrate` creates a bell notification for each approver when a node enters `awaiting_approval`. The frontend adds a `/tracking` route, list/row components, polling hooks (~3s), and a Sidebar entry with a count badge. Everything reuses existing infrastructure (decision endpoint, `RunTrackingView`, notification bell, React Query polling, `{data,error,meta}` envelope).

**Tech Stack:** Backend — FastAPI, SQLAlchemy (RLS-scoped `get_tenant_session`), Postgres JSONB. Frontend — React 19, TypeScript, TanStack Query, react-router-dom.

## Global Constraints

- **No automated tests** unless the user explicitly asks (CLAUDE.md working preferences override TDD/verify mandates). Each task ends with a **manual verification** + commit instead of a test cycle.
- **Do NOT auto-run** `typecheck` / `lint` / `test` / `build` / `format` (CLAUDE.md). Manual verify commands in this plan are **optional**, for the user to run if they choose.
- Response envelope for all backend endpoints: `{"data": ..., "error": null, "meta": {}}` via the module-local `_ok` / `_err` helpers.
- Current user id on the backend: `uuid.UUID(str(request.state.user_id))`.
- RLS: every backend query uses `get_tenant_session` (already tenant-scoped); add the explicit `user_id` predicate for per-user filtering.
- Frontend API calls go through `apiFetch<T>(path, init?)` from `lib/api.ts`, which injects JWT+tenant and unwraps the envelope.
- Polling interval: **3000 ms** (`refetchInterval: 3000`).
- Terminal run statuses (drop when `scope=active`): `completed`, `failed`, `timed_out`, `completed_with_failures` (mirror `frontend/src/lib/runStatusMeta.ts` `TERMINAL_RUN_STATUSES`).
- Node "my turn" predicate: `status == "awaiting_approval"` AND `decision IS NULL` AND `current_user_id ∈ approver_user_ids`.
- Files > 200 LOC should be split (CLAUDE.md); the components below are intentionally small and focused.

---

### Task 1: Backend read model — tracking service + routes

**Files:**
- Create: `backend/app/modules/orchestrator/tracking_service.py`
- Create: `backend/app/modules/orchestrator/tracking_routes.py`
- Modify: `backend/app/main.py` (import + `include_router`, near line 115 where `workflows_graph_router` is wired)

**Interfaces:**
- Produces (service):
  - `list_my_tracking(session: Session, user_id: uuid.UUID, *, scope: str = "active") -> list[dict[str, Any]]`
  - `count_my_awaiting(session: Session, user_id: uuid.UUID) -> int`
  - Each tracking item dict shape:
    ```
    {
      "run_id": str, "workflow_id": str, "workflow_name": str,
      "run_status": str,
      "my_awaiting_nodes": [ {"node_key": str, "label": str} ],
      "current_node": {"node_key": str, "label": str, "status": str} | None,
      "is_my_turn": bool,
      "updated_at": str | None   # ISO8601
    }
    ```
- Produces (routes): router with `GET /me/tracking?scope=active|all` and `GET /me/tracking/summary`.

- [ ] **Step 1: Create the tracking service**

Create `backend/app/modules/orchestrator/tracking_service.py`:

```python
"""Cross-run, per-user review inbox read model (Tracking).

Pure service layer (no HTTP). Aggregates run_node_executions the current user
is an approver on into one row per run, with a "my turn" flag. Reuses the
RLS-scoped session — the explicit user_id predicate scopes to the caller's
own inbox.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.orchestrator.graph_engine import load_graph
from app.modules.orchestrator.models import RunNodeExecution, WorkflowRun
from app.modules.orchestrator.service import _reassert_rls

_TERMINAL_RUN_STATUSES = (
    "completed",
    "failed",
    "timed_out",
    "completed_with_failures",
)


def _iso(dt: Any) -> str | None:
    return dt.isoformat() if dt is not None else None


def _label_for(snapshot: dict[str, Any] | None, node_key: str) -> str:
    if not snapshot:
        return node_key
    try:
        _keys, nodes_by_key, _edges = load_graph(snapshot)
    except Exception:
        return node_key
    return nodes_by_key.get(node_key, {}).get("label", node_key)


def _run_ids_for_approver(session: Session, user_id: uuid.UUID) -> list[str]:
    """Distinct run ids that have >=1 node exec where user is an approver."""
    _reassert_rls(session)
    uid_json = json.dumps([str(user_id)])
    rows = session.execute(
        text(
            "SELECT DISTINCT run_id FROM run_node_executions "
            "WHERE approver_user_ids @> CAST(:uid AS jsonb)"
        ),
        {"uid": uid_json},
    ).fetchall()
    return [str(r[0]) for r in rows]


def _build_item(
    session: Session, user_id: uuid.UUID, run: WorkflowRun
) -> dict[str, Any]:
    _reassert_rls(session)
    execs: list[RunNodeExecution] = (
        session.query(RunNodeExecution)
        .filter(RunNodeExecution.run_id == run.id)
        .execution_options(populate_existing=True)
        .all()
    )
    uid = str(user_id)

    my_awaiting: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    latest = run.started_at or run.created_at
    for e in execs:
        approvers = [str(a) for a in (e.approver_user_ids or [])]
        for ts in (e.decided_at, e.completed_at, e.started_at, e.created_at):
            if ts is not None and (latest is None or ts > latest):
                latest = ts
        if (
            e.status == "awaiting_approval"
            and e.decision is None
            and uid in approvers
        ):
            label = _label_for(run.graph_snapshot, e.node_key)
            my_awaiting.append({"node_key": e.node_key, "label": label})
        # "current" = the node the run is actively on: prefer awaiting_approval,
        # else running, else pending frontier. First match by that priority.
        if current is None and e.status in ("awaiting_approval", "running"):
            current = {
                "node_key": e.node_key,
                "label": _label_for(run.graph_snapshot, e.node_key),
                "status": e.status,
            }

    # Look up workflow name (RLS-scoped).
    _reassert_rls(session)
    name_row = session.execute(
        text("SELECT name FROM workflows WHERE id = :wid"),
        {"wid": str(run.workflow_id)},
    ).fetchone()

    return {
        "run_id": str(run.id),
        "workflow_id": str(run.workflow_id),
        "workflow_name": name_row[0] if name_row else "",
        "run_status": run.status,
        "my_awaiting_nodes": my_awaiting,
        "current_node": current,
        "is_my_turn": bool(my_awaiting),
        "updated_at": _iso(latest),
    }


def list_my_tracking(
    session: Session, user_id: uuid.UUID, *, scope: str = "active"
) -> list[dict[str, Any]]:
    run_ids = _run_ids_for_approver(session, user_id)
    items: list[dict[str, Any]] = []
    for rid in run_ids:
        _reassert_rls(session)
        run = session.get(WorkflowRun, uuid.UUID(rid))
        if run is None:
            continue
        if scope == "active" and run.status in _TERMINAL_RUN_STATUSES:
            continue
        items.append(_build_item(session, user_id, run))
    # Sort: my-turn first, then most-recently-updated.
    items.sort(
        key=lambda it: (it["is_my_turn"], it["updated_at"] or ""),
        reverse=True,
    )
    return items


def count_my_awaiting(session: Session, user_id: uuid.UUID) -> int:
    return sum(
        1 for it in list_my_tracking(session, user_id, scope="active") if it["is_my_turn"]
    )
```

- [ ] **Step 2: Create the tracking routes**

Create `backend/app/modules/orchestrator/tracking_routes.py`:

```python
"""HTTP routes for the per-user Tracking inbox (cross-run review status)."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.orchestrator import tracking_service as svc

router = APIRouter(prefix="/me/tracking", tags=["tracking"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _current_user_id(request: Request) -> uuid.UUID:
    return uuid.UUID(str(request.state.user_id))


@router.get("")
def list_tracking_route(  # noqa: B008
    request: Request,
    scope: str = "active",
    session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    scope = scope if scope in ("active", "all") else "active"
    items = svc.list_my_tracking(session, _current_user_id(request), scope=scope)
    return JSONResponse(status_code=200, content=_ok(items))


@router.get("/summary")
def tracking_summary_route(  # noqa: B008
    request: Request,
    session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    n = svc.count_my_awaiting(session, _current_user_id(request))
    return JSONResponse(status_code=200, content=_ok({"awaiting_my_review": n}))
```

- [ ] **Step 3: Wire the router in main.py**

In `backend/app/main.py`, add the import alongside the other orchestrator imports (near line 40):

```python
from app.modules.orchestrator.tracking_routes import router as tracking_router
```

And register it alongside the other routers (after `workflows_files_router`, near line 116):

```python
app.include_router(tracking_router)
```

- [ ] **Step 4: Manual verification (optional — user runs if desired)**

Start the backend (`cd backend && uv run uvicorn app.main:app --reload --port 8000`), obtain a JWT for a user who is an approver on a gated run, then:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/me/tracking?scope=active" | jq
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/me/tracking/summary" | jq
```

Expected: `data` is an array of run items (my-turn items first); summary returns `{"awaiting_my_review": N}` where N = number of runs currently awaiting this user.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/orchestrator/tracking_service.py backend/app/modules/orchestrator/tracking_routes.py backend/app/main.py
git commit -m "feat(tracking): backend read model for per-user review inbox"
```

---

### Task 2: Backend — notify approvers when a node enters awaiting_approval

**Files:**
- Modify: `backend/app/modules/orchestrator/graph_engine.py` (add `_notify_approvers`; call it at the human-gate pause, ~line 292–301 in `graph_orchestrate`)

**Interfaces:**
- Consumes: `notification.service.create_notification(session, *, tenant_id, user_id, category, title, body, ref)` (existing); `models.Workflow` for the workflow name.
- Produces: `_notify_approvers(session: Session, run: WorkflowRun, node_exec: RunNodeExecution) -> None` (module-private).

- [ ] **Step 1: Add the `_notify_approvers` helper**

In `backend/app/modules/orchestrator/graph_engine.py`, add this function (place it near the other module helpers, e.g. above `graph_orchestrate`). Add `import uuid` if not already imported at the top (it is used elsewhere in the module):

```python
def _notify_approvers(
    session: Session, run: WorkflowRun, node_exec: RunNodeExecution
) -> None:
    """Create one bell notification per approver when a node needs review.

    Reuses notification.service.create_notification. Called at the human-gate
    pause; the retry/rollback re-entry path also flows back through this same
    gate, so a re-review is not missed. Best-effort: a notification failure
    must never break run orchestration.
    """
    from app.modules.notification.service import create_notification
    from app.modules.orchestrator.models import Workflow

    approvers = node_exec.approver_user_ids or []
    if not approvers:
        return
    _reassert_rls(session)
    wf = session.get(Workflow, run.workflow_id)
    wf_name = wf.name if wf else ""
    _keys, nodes_by_key, _edges = load_graph(run.graph_snapshot or {"nodes": [], "edges": []})
    node_label = nodes_by_key.get(node_exec.node_key, {}).get("label", node_exec.node_key)
    ref = {
        "run_id": str(run.id),
        "workflow_id": str(run.workflow_id),
        "node_key": node_exec.node_key,
    }
    try:
        for uid in approvers:
            create_notification(
                session,
                tenant_id=run.tenant_id,
                user_id=uuid.UUID(str(uid)),
                category="graph_review",
                title=f"Đến lượt bạn review: {wf_name} / {node_label}",
                body="Một node trong quy trình đang chờ bạn duyệt.",
                ref=ref,
            )
        session.commit()
        _reassert_rls(session)
    except Exception:
        # Notification is best-effort; never block the engine.
        session.rollback()
        _reassert_rls(session)
```

- [ ] **Step 2: Call it at the human-gate pause**

In `graph_orchestrate`, at the gated branch (currently):

```python
        if nxt.approver_user_ids:  # human-gated -> pause for review
            transition_node_status(
                session,
                nxt.id,
                from_status="running",
                to_status="awaiting_approval",
                extra_cols={"output": json.dumps(res.output)},
            )
            _set_run_awaiting_human(session, run_id)
            return
```

Insert the notify call after `_set_run_awaiting_human`, before `return`. Re-fetch the node exec so `approver_user_ids` / `node_key` are populated from the persisted row:

```python
        if nxt.approver_user_ids:  # human-gated -> pause for review
            transition_node_status(
                session,
                nxt.id,
                from_status="running",
                to_status="awaiting_approval",
                extra_cols={"output": json.dumps(res.output)},
            )
            _set_run_awaiting_human(session, run_id)
            _reassert_rls(session)
            gated = execs.get(nxt.node_key) or nxt
            _notify_approvers(session, run, gated)
            return
```

(`nxt` is the `RunNodeExecution` selected for this iteration and already carries `approver_user_ids` + `node_key`, so `nxt` is sufficient; `execs.get(...)` is a defensive fallback.)

- [ ] **Step 3: Impact check (required by CLAUDE.md GitNexus rule)**

Before finalizing, run impact analysis on the edited symbol and report blast radius:

```
impact({target: "graph_orchestrate", direction: "upstream"})
```

Report direct callers + risk level to the user. Proceed only if not HIGH/CRITICAL (warn the user if it is).

- [ ] **Step 4: Manual verification (optional — user runs if desired)**

Trigger a run that reaches a human-gated node whose `approver_user_ids` includes a known user, then check that user's notifications:

```bash
curl -s -H "Authorization: Bearer $APPROVER_TOKEN" "http://localhost:8000/notifications?unread=true" | jq '.data[] | select(.category=="graph_review")'
```

Expected: a `graph_review` notification with `ref.run_id` / `ref.node_key` matching the gated node.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/orchestrator/graph_engine.py
git commit -m "feat(tracking): notify approvers when a node awaits review"
```

---

### Task 3: Frontend — API layer + polling hooks

**Files:**
- Create: `frontend/src/lib/trackingApi.ts`
- Create: `frontend/src/hooks/useTracking.ts`

**Interfaces:**
- Produces (`trackingApi.ts`):
  - `interface TrackingNodeRef { node_key: string; label: string }`
  - `interface TrackingCurrentNode { node_key: string; label: string; status: string }`
  - `interface TrackingItem { run_id: string; workflow_id: string; workflow_name: string; run_status: string; my_awaiting_nodes: TrackingNodeRef[]; current_node: TrackingCurrentNode | null; is_my_turn: boolean; updated_at: string | null }`
  - `getTracking(scope: "active" | "all"): Promise<TrackingItem[]>`
  - `getTrackingSummary(): Promise<{ awaiting_my_review: number }>`
- Produces (`useTracking.ts`):
  - `useTrackingList(scope: "active" | "all"): UseQueryResult<TrackingItem[], Error>`
  - `useTrackingSummary(): UseQueryResult<{ awaiting_my_review: number }, Error>`

- [ ] **Step 1: Create the API wrappers**

Create `frontend/src/lib/trackingApi.ts`:

```ts
/* Tracking inbox API — typed wrappers around apiFetch for the per-user
 * cross-run review endpoints. apiFetch injects JWT + tenant and unwraps
 * the {data,error,meta} envelope.
 */
import { apiFetch } from "./api";

export interface TrackingNodeRef {
  node_key: string;
  label: string;
}

export interface TrackingCurrentNode {
  node_key: string;
  label: string;
  status: string;
}

export interface TrackingItem {
  run_id: string;
  workflow_id: string;
  workflow_name: string;
  run_status: string;
  my_awaiting_nodes: TrackingNodeRef[];
  current_node: TrackingCurrentNode | null;
  is_my_turn: boolean;
  updated_at: string | null;
}

export function getTracking(scope: "active" | "all"): Promise<TrackingItem[]> {
  return apiFetch<TrackingItem[]>(`/me/tracking?scope=${scope}`);
}

export function getTrackingSummary(): Promise<{ awaiting_my_review: number }> {
  return apiFetch<{ awaiting_my_review: number }>(`/me/tracking/summary`);
}
```

- [ ] **Step 2: Create the polling hooks**

Create `frontend/src/hooks/useTracking.ts`:

```ts
/* Tracking inbox reads — both polled at 3s. The list drives the Tracking
 * page; the summary drives the Sidebar badge (kept as a separate light query
 * so the badge does not pull the whole list).
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  getTracking,
  getTrackingSummary,
  type TrackingItem,
} from "../lib/trackingApi";

const POLL_MS = 3000;

export function useTrackingList(
  scope: "active" | "all",
): UseQueryResult<TrackingItem[], Error> {
  return useQuery<TrackingItem[], Error>({
    queryKey: ["tracking", scope],
    queryFn: () => getTracking(scope),
    refetchInterval: POLL_MS,
  });
}

export function useTrackingSummary(): UseQueryResult<
  { awaiting_my_review: number },
  Error
> {
  return useQuery<{ awaiting_my_review: number }, Error>({
    queryKey: ["trackingSummary"],
    queryFn: () => getTrackingSummary(),
    refetchInterval: POLL_MS,
  });
}
```

- [ ] **Step 3: Manual verification (optional)**

`cd frontend && npm run dev`; these hooks are exercised by Task 4's page. No standalone check needed.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/trackingApi.ts frontend/src/hooks/useTracking.ts
git commit -m "feat(tracking): frontend API layer + polling hooks"
```

---

### Task 4: Frontend — Tracking page, list, and row

**Files:**
- Create: `frontend/src/components/tracking/TrackingRow.tsx`
- Create: `frontend/src/components/tracking/TrackingList.tsx`
- Create: `frontend/src/routes/tracking.tsx`
- Modify: `frontend/src/App.tsx` (import + `<Route path="/tracking" ... />`)

**Interfaces:**
- Consumes: `useTrackingList` (Task 3), `TrackingItem` (Task 3), `RunStatusBadge` from `../workflows/runs/RunStatusBadge`, UI primitives `Skeleton` / `ErrorState` from `../ui`.
- Produces: default-exported `TrackingPage` React component mounted at `/tracking`.

- [ ] **Step 1: Create `TrackingRow`**

Create `frontend/src/components/tracking/TrackingRow.tsx`:

```tsx
/* One session row in the Tracking inbox. Clicking navigates to the existing
 * RunTrackingView, where Approve/Reject/Retry live.
 */
import { useNavigate } from "react-router-dom";
import RunStatusBadge from "../workflows/runs/RunStatusBadge";
import type { TrackingItem } from "../../lib/trackingApi";

export interface TrackingRowProps {
  item: TrackingItem;
}

export default function TrackingRow({ item }: TrackingRowProps) {
  const navigate = useNavigate();
  const go = () =>
    navigate(`/workflows/${item.workflow_id}/runs/${item.run_id}`);

  return (
    <button
      type="button"
      data-testid="vaic-tracking-row"
      onClick={go}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3)",
        width: "100%",
        textAlign: "left",
        padding: "var(--space-3)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-card, 8px)",
        background: item.is_my_turn
          ? "var(--color-warning-bg, rgba(255,193,7,0.08))"
          : "var(--color-surface, transparent)",
        cursor: "pointer",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <strong>{item.workflow_name || "Workflow"}</strong>
          {item.is_my_turn && (
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "2px 8px",
                borderRadius: "999px",
                background: "var(--color-warning, #b8860b)",
                color: "#fff",
              }}
            >
              Đến lượt bạn
            </span>
          )}
        </div>
        <div style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
          {item.current_node
            ? `Đang ở bước: ${item.current_node.label}`
            : "Chưa có bước đang chạy"}
        </div>
      </div>
      <RunStatusBadge status={item.run_status} />
    </button>
  );
}
```

- [ ] **Step 2: Create `TrackingList`**

Create `frontend/src/components/tracking/TrackingList.tsx`:

```tsx
/* Tracking inbox list: scope toggle (active/all), polled via useTrackingList,
 * renders a TrackingRow per session with loading/error/empty states.
 */
import { useState } from "react";
import { ErrorState, Skeleton } from "../ui";
import TrackingRow from "./TrackingRow";
import { useTrackingList } from "../../hooks/useTracking";

export default function TrackingList() {
  const [scope, setScope] = useState<"active" | "all">("active");
  const query = useTrackingList(scope);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <button
          type="button"
          onClick={() => setScope("active")}
          aria-pressed={scope === "active"}
          style={{ fontWeight: scope === "active" ? 700 : 400 }}
        >
          Đang hoạt động
        </button>
        <button
          type="button"
          onClick={() => setScope("all")}
          aria-pressed={scope === "all"}
          style={{ fontWeight: scope === "all" ? 700 : 400 }}
        >
          Tất cả
        </button>
      </div>

      {query.isLoading && <Skeleton lines={4} height="56px" />}
      {query.isError && (
        <ErrorState message={query.error?.message ?? "Không tải được Tracking"} />
      )}
      {query.data && query.data.length === 0 && (
        <div style={{ color: "var(--color-text-muted)", padding: "var(--space-4)" }}>
          Chưa có session nào cần bạn theo dõi.
        </div>
      )}
      {query.data?.map((item) => (
        <TrackingRow key={item.run_id} item={item} />
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create the route page**

Create `frontend/src/routes/tracking.tsx`:

```tsx
/* /tracking — per-account realtime review inbox. */
import TrackingList from "../components/tracking/TrackingList";

export default function TrackingPage() {
  return (
    <div data-testid="vaic-tracking-page" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <h1 className="text-h1">Tracking</h1>
      <p style={{ color: "var(--color-text-muted)", marginTop: "calc(-1 * var(--space-2))" }}>
        Tiến độ realtime của các quy trình đang chờ bạn xử lý.
      </p>
      <TrackingList />
    </div>
  );
}
```

- [ ] **Step 4: Register the route in `App.tsx`**

Add the import next to the other route imports (near line 16 where `RunTrackingPage` is imported):

```tsx
import TrackingPage from "./routes/tracking";
```

Add the route among the other `<Route>`s (e.g. right after the `/workflows/:id` routes block, near line 76):

```tsx
        <Route path="/tracking" element={<TrackingPage />} />
```

- [ ] **Step 5: Verify `RunStatusBadge` prop + `Skeleton`/`ErrorState` exports match**

Confirm the reused pieces have the shapes used above:

```bash
grep -n "export" frontend/src/components/workflows/runs/RunStatusBadge.tsx
grep -nE "Skeleton|ErrorState" frontend/src/components/ui/index.ts
```

Expected: `RunStatusBadge` is a default export taking a `status: string` prop; `Skeleton` and `ErrorState` are exported from `../ui` with `lines`/`height` and `message` props respectively. If a prop name differs, adjust the call sites in Steps 1–2 to match (do not change the reused components).

- [ ] **Step 6: Manual verification (optional — user runs if desired)**

`cd frontend && npm run dev`, log in as an approver, open `/tracking`. Expected: sessions awaiting you appear first with a "Đến lượt bạn" chip; toggling Đang hoạt động/Tất cả changes the list; clicking a row opens the run review view; the list refreshes ~every 3s.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/tracking/ frontend/src/routes/tracking.tsx frontend/src/App.tsx
git commit -m "feat(tracking): Tracking page, list, and session row"
```

---

### Task 5: Frontend — Sidebar nav entry + count badge

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx` (add nav item above Audit; render badge when `awaiting_my_review > 0`)

**Interfaces:**
- Consumes: `useTrackingSummary` (Task 3). Icon from `lucide-react` (`ClipboardList`), matching the existing icon-import pattern in `Sidebar.tsx`.

- [ ] **Step 1: Add the nav item**

In `frontend/src/components/Sidebar.tsx`, import the icon with the others (the file already imports icons like `Workflow`, `Activity` from `lucide-react`):

```tsx
import { /* …existing… */ ClipboardList } from "lucide-react";
```

Add the entry to the nav array, **above** the Audit entry (currently `{ to: "/audit", label: "Audit", icon: Activity }`):

```tsx
  { to: "/tracking", label: "Tracking", icon: ClipboardList },
```

- [ ] **Step 2: Wire the count badge**

At the top of the `Sidebar` component body, read the summary:

```tsx
import { useTrackingSummary } from "../hooks/useTracking";
// …inside the component:
  const trackingSummary = useTrackingSummary();
  const awaitingCount = trackingSummary.data?.awaiting_my_review ?? 0;
```

Where each nav item's label is rendered (the `{!collapsed && <span>{item.label}</span>}` line, ~line 197), render a badge when the item is Tracking and `awaitingCount > 0`:

```tsx
              {!collapsed && <span>{item.label}</span>}
              {item.to === "/tracking" && awaitingCount > 0 && (
                <span
                  data-testid="vaic-tracking-badge"
                  style={{
                    marginLeft: "auto",
                    minWidth: 18,
                    height: 18,
                    padding: "0 5px",
                    borderRadius: 9,
                    background: "var(--color-warning, #b8860b)",
                    color: "#fff",
                    fontSize: "0.7rem",
                    fontWeight: 700,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {awaitingCount}
                </span>
              )}
```

If the collapsed rail hides labels, the badge still renders after the icon when expanded; for the collapsed state it is acceptable to omit the badge (guarded by `!collapsed` is optional — keep the badge visible only when expanded to match the label guard, or show a small dot when collapsed; expanded-only is the minimal choice).

- [ ] **Step 3: Manual verification (optional — user runs if desired)**

With the dev server running and a user who has ≥1 session awaiting review, the **Tracking** sidebar item shows a count badge; approving/rejecting all pending items drops the count to 0 (badge disappears) within ~3s.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat(tracking): sidebar Tracking nav item + awaiting-review badge"
```

---

## Self-Review

**Spec coverage:**
- §3 architecture (2 read endpoints + notify hook + list/badge) → Tasks 1, 2, 4, 5. ✓
- §4.1 `GET /me/tracking` + `/summary`, approver filter, scope, current_node → Task 1. ✓
- §4.2 notify approvers at awaiting_approval (single site covers re-entry) → Task 2. ✓
- §5.1 route + nav + badge → Tasks 4 (route/nav) + 5 (badge). ✓
- §5.2 files (trackingApi, useTracking, TrackingList, TrackingRow, tracking page) → Tasks 3, 4. ✓
- §5.3 behavior: polling 3s, my-turn chip + sort, click→RunTrackingView, active/all filter, empty state → Tasks 3, 4. ✓
- §5.4 realtime loop closure via polling → inherent in Task 3 hooks. ✓
- §6 out-of-scope items are not implemented. ✓

**Placeholder scan:** No TBD/TODO; all code blocks are complete; verification steps are concrete. ✓

**Type consistency:** `TrackingItem` shape identical across service dict (Task 1), `trackingApi.ts` interface (Task 3), and consumers (Task 4). `getTracking`/`getTrackingSummary` names match hook usage. `useTrackingList`/`useTrackingSummary` names match Sidebar + list usage. `_notify_approvers` signature matches its single call site. ✓

**Note on tests:** No automated-test tasks are included, per CLAUDE.md working preferences (no tests / no auto-run of test tooling unless the user explicitly asks). If the user later requests tests, add: (a) an integration test that seeds a gated run + asserts `GET /me/tracking` returns it with `is_my_turn=true`, and (b) a test that a `graph_review` notification is created for each approver at the gate.
