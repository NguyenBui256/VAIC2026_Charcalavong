# Tracking — Realtime personal review inbox (design)

Date: 2026-07-19
Status: Approved (brainstorming) → ready for implementation plan

## 1. Problem & goal

Approvers have no cross-run place to see, in realtime, which workflow sessions
involve them and when it is their turn to act. Today the only review surface is
`RunTrackingView`, reachable only from inside one specific workflow's runs tab.

Add a top-level **Tracking** section: a per-account inbox listing every run that
has at least one node where the current user is an approver, showing current
status, which step the run is on, and a clear "your turn" signal. Clicking a
session opens the existing `RunTrackingView` where Approve / Reject / Retry
already work.

**Realtime** = React Query polling (~3s), consistent with the existing system.
No WebSocket/SSE introduced.

### Tracking vs Audit (explicit boundary)

- **Tracking**: *current* progress, realtime, action-oriented ("my turn → act").
  Focus on running / awaiting sessions relevant to me.
- **Audit**: detailed logs + Evaluation + Optimization, retrospective. Unchanged.

## 2. Scope decisions (locked)

- Realtime mechanism: **polling ~3s** (reuse React Query pattern).
- Relevance filter: **only runs where current user ∈ `approver_user_ids`** of at
  least one node. Not runs I merely started; not all tenant runs.
- Actions location: **open detail** — Tracking is a list; click → reuse
  `RunTrackingView` (graph + review panel). No inline approve/reject.
- "Your turn" signal: **sidebar badge + bell notification**. When a node enters
  `awaiting_approval`, backend creates a notification per approver (existing
  bell renders it); sidebar shows a count of sessions awaiting my review.

## 3. Architecture

```
[graph_engine] node → awaiting_approval
      ├─ (NEW) notify each approver via create_notification → existing bell
      │
[Tracking page] polling ~3s:
      GET /me/tracking?scope=active|all   → runs I approve on + summary
      GET /me/tracking/summary            → { awaiting_my_review: N } → sidebar badge
      │
   click run → navigate /workflows/:wfId/runs/:runId → RunTrackingView (existing)
      → Approve/Reject/Retry via existing decision endpoint (unchanged)
```

Principle: maximum reuse. New code = 2 aggregate read endpoints, 1 list page,
1 badge, hooks/api, and one notification hook point (covering both first-time
gating and re-entry after retry/rollback).

## 4. Backend

### 4.1 New read model — `orchestrator/tracking_routes.py` + `tracking_service.py`

Cross-run, per-user query — kept out of run-scoped `graph_routes.py`.

```
GET /me/tracking?scope=active|all
  → [ {
      run_id, workflow_id, workflow_name,
      run_status,
      my_awaiting_nodes: [ { node_key, label } ],   # status=awaiting_approval
                                                     # AND decision IS NULL
                                                     # AND current_user ∈ approver_user_ids
      current_node: { node_key, label, status } | null,
      is_my_turn: bool,                              # my_awaiting_nodes non-empty
      updated_at
    } ]
  # sort: is_my_turn desc, updated_at desc
  # scope=active drops runs with a terminal run status; scope=all keeps them.

GET /me/tracking/summary
  → { awaiting_my_review: N }                        # count of runs with is_my_turn=true
```

Query: select `run_node_executions` where
`approver_user_ids @> to_jsonb(array[current_user_id])`, group by `run_id`, join
`workflow_runs` + `workflows`. Uses existing `get_tenant_session` (RLS-scoped)
plus the explicit `user_id` predicate — a user sees only their own inbox.

`current_node` = the run's currently active node (awaiting_approval else
running/pending frontier) for the "which step" display; may be null.

Register the router where orchestrator routers are wired (same place as
`graph_routes`). Standard `{data,error,meta}` envelope used elsewhere.

### 4.2 Notification on "your turn" — `graph_engine.py`

At the human-gate pause (`graph_orchestrate`, ~line 292, right after
`transition_node_status(... to_status="awaiting_approval")` +
`_set_run_awaiting_human`):

```python
_notify_approvers(session, run, nxt)   # NEW
```

`_notify_approvers(session, run, node_exec)`:
- for each `user_id` in `node_exec.approver_user_ids`
- `create_notification(session, tenant_id=run.tenant_id, user_id=<approver>,
   category="graph_review",
   title="Đến lượt bạn review: <workflow_name> / <node label>",
   ref={"run_id","workflow_id","node_key"})`
- reuses existing `notification.service.create_notification`; caller's
  transaction/commit already owns the surrounding commit.

**Re-entry coverage**: the node can re-enter `awaiting_approval` after a
retry/rollback (in `run_node`, ~line 143, and via the rollback→pending→re-run
path). The implementation must add the same `_notify_approvers` call at every
transition into `awaiting_approval` so a second "your turn" is not lost. Verify
both sites during implementation.

**Idempotency**: each genuine transition into `awaiting_approval` is a distinct
event, so one notification per transition is correct. Polling reads the read
model, not notifications, so no dedup needed there.

Decision / rollback logic is untouched.

## 5. Frontend

### 5.1 Route & nav
- `App.tsx`: `<Route path="/tracking" element={<TrackingPage />} />`.
- `Sidebar.tsx`: add `{ to: "/tracking", label: "Tracking", icon: ClipboardList }`
  above Audit. Badge count next to label when `awaiting_my_review > 0`.

### 5.2 New files
```
routes/tracking.tsx                     # TrackingPage: layout + hooks
components/tracking/TrackingList.tsx     # list container + empty/loading/error
components/tracking/TrackingRow.tsx      # one session row
hooks/useTracking.ts                     # useTrackingList(scope) + useTrackingSummary()
lib/trackingApi.ts                       # getTracking(scope), getTrackingSummary()
```

### 5.3 Behavior
- `useTrackingList(scope)`: `useQuery(["tracking", scope], …, { refetchInterval: 3000 })`.
- `useTrackingSummary()`: polling 3s, used by Sidebar badge (separate light query,
  avoids pulling the whole list for the count).
- Row shows: workflow name, `RunStatusBadge` (reused), current step, and if
  `is_my_turn` a prominent **"Đến lượt bạn"** chip; my-turn rows sort to top.
- Click row → `navigate("/workflows/:workflowId/runs/:runId")` → existing
  `RunTrackingView` handles Approve/Reject/Retry.
- Filter toggle **Đang hoạt động / Tất cả** → `scope=active|all`.
- Empty state: "Chưa có session nào cần bạn theo dõi."

### 5.4 Realtime loop closure
After a decision in `RunTrackingView`, list/summary self-update on next poll;
badge decrements. Optionally invalidate `["tracking"]` on decision success for
instant feedback.

Reuse: `RunStatusBadge`, `RunTrackingView`, notification bell, UI primitives
(`Button`, `Skeleton`, `ErrorState`), React Query polling. No new dependencies.

## 6. Out of scope (YAGNI)
- WebSocket/SSE push.
- Inline approve/reject in the list.
- Runs where I am owner/initiator but not an approver.
- All-tenant operational dashboard.
- Notification dedup/collapse (one per genuine gate transition is fine).

## 7. Open questions
- None outstanding. (Notification content/category confirmed; polling interval
  fixed at ~3s to match run polling cadence.)
