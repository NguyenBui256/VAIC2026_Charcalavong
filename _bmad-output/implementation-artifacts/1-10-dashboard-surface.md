---
baseline_commit: ec5fdd5fe5f014ac4057cd6b9ea231a0b8e46ee3
---

# Story 1.10: Dashboard Surface

Status: review

## Story

As a **logged-in user**,
I want **a dashboard that orients me to what's running, what needs my attention, and what ran recently**,
So that **I can decide what to do next without hunting through menus**.

## Acceptance Criteria

(Sourced verbatim from `_bmad-output/planning-artifacts/epics.md` L599–L613.)

1. **AC (UX-DR15 three sections)** — `/dashboard` renders three sections: KPI strip, Escalation inbox preview, Recent Runs list.
2. **AC (KPI strip)** — Three cards: Active Runs (count), Pending Escalations (count), Today's Mini-App Events (count) — populated from mock data via TanStack Query.
3. **AC (Escalation inbox preview)** — Top 3 pending items with Run name, escalation reason, and "Open" affordance.
4. **AC (Recent Runs list)** — Last 5 Runs with name, status pill, run-time, and click-to-trace affordance.
5. **AC (UX-DR23 empty)** — Empty sections render EmptyState (illustration + CTA).
6. **AC (UX-DR23 loading)** — Loading sections render Skeleton matching final layout (not generic spinner).
7. **AC (UX-DR23 error)** — Failed sections render ErrorState with message + retry action.
8. **AC (default route)** — Dashboard is default route after login (verified — wired in 1-8).

## Tasks / Subtasks

- [x] **T1 — Mock data layer**
  - [x] T1.1 `src/lib/mockData.ts` — deterministic types (`KpiCounts`, `EscalationItem`, `RunSummary`, `DashboardData`), three fixtures (`mockDashboardPopulated`, `mockDashboardEmpty`, `mockDashboardErrorFactory`), seeded generator (`mulberry32` + `generateSeededDashboard`), formatters (`formatDuration`, `formatRelativeFromOffset`), fixed `MOCK_NOW` anchor.
- [x] **T2 — Data hook**
  - [x] T2.1 `src/hooks/useDashboardData.ts` — TanStack Query `useQuery` with mock `queryFn`; test mutators `__setDashboardMockMode` / `__setDashboardMockDelay` / `__resetDashboardMock`; artificial delay in dev (disabled in tests).
- [x] **T3 — KPI strip (AC #2, #6, #7)**
  - [x] T3.1 `src/components/dashboard/KpiStrip.tsx` — three cards (Active Runs, Pending Escalations, Today's Mini-App Events), tabular-nums, semantic icons from `lib/icons.tsx`.
  - [x] T3.2 `src/components/dashboard/KpiStrip.test.tsx` — 5 tests: populated, labels, empty zeros, loading skeletons, error state.
- [x] **T4 — Escalation inbox (AC #3, #5, #6, #7)**
  - [x] T4.1 `src/components/dashboard/EscalationInbox.tsx` — top 3 items with Run name, reason, relative timestamp, "Open" affordance (Button). Uses `semanticIcons.Escalation`.
  - [x] T4.2 `src/components/dashboard/EscalationInbox.test.tsx` — 6 tests: heading, rows, Open onClick, empty state, loading skeleton, error state.
- [x] **T5 — Recent Runs list (AC #4, #5, #6, #7)**
  - [x] T5.1 `src/components/dashboard/RecentRuns.tsx` — last 5 Runs, status pill, duration, relative time, keyboard-activatable row (click-to-trace). Uses `StatusPill` + `semanticIcons.Run`.
  - [x] T5.2 `src/components/dashboard/RecentRuns.test.tsx` — 8 tests: heading, ≤5 rows, name+pill, duration, row click, empty state, loading skeleton, error state.
- [x] **T6 — Dashboard route (AC #1, #8)**
  - [x] T6.1 `src/routes/dashboard.tsx` — replaced 1-8 placeholder with full dashboard wiring `useDashboardData` + the three components; retry handler calls `query.refetch()`; click-to-trace navigates to `/audit?run=<id>`.
  - [x] T6.2 `src/routes/dashboard.test.tsx` — 7 tests: heading, three sections present, KPI numbers, escalation rows, run rows, empty mode, error mode.
- [x] **T7 — Verification**
  - [x] T7.1 `npx tsc --noEmit` clean.
  - [x] T7.2 `npm run build` succeeds.
  - [x] T7.3 `npx vitest run` — 139 tests pass (20 new + 119 existing).

## AC Coverage Map

| AC | Component / Test |
|---|---|
| #1 three sections | `DashboardPage` (`dashboard.test.tsx`: "renders all three sections") |
| #2 KPI strip | `KpiStrip` (`KpiStrip.test.tsx`: "renders three KPI cards") |
| #3 Escalation inbox preview | `EscalationInbox` (`EscalationInbox.test.tsx`: "renders each escalation row", "Open affordance fires onOpen") |
| #4 Recent Runs list | `RecentRuns` (`RecentRuns.test.tsx`: "renders at most 5 run rows", "row click-to-trace fires onOpenRun") |
| #5 empty state | `KpiStrip` (zeros), `EscalationInbox` + `RecentRuns` (EmptyState); `dashboard.test.tsx`: "renders empty states" |
| #6 loading skeleton | `KpiStrip` / `EscalationInbox` / `RecentRuns` "renders skeleton placeholders when loading" |
| #7 error state | `KpiStrip` / `EscalationInbox` / `RecentRuns` "renders ErrorState"; `dashboard.test.tsx`: "renders error states" |
| #8 default route | Verified — `App.tsx` routes `/` and `*` → `/dashboard`; `PublicOnlyRoute` redirects authenticated users from `/login` → `/dashboard`. No change required. |

## Deviations

- **Click-to-trace target:** The real trace route (`/trace/:runId`) arrives in Epic 4. Until then, click-to-trace navigates to `/audit?run=<runId>`. This is a documented placeholder, not a deviation from the AC (the AC only requires the affordance exist).
- **Refresh button:** platform-design.md §3.1 shows a `[Refresh]` button in the header. Not in the ACs for 1.10; omitted to keep the single-Primary-CTA rule (UX-DR3) clean. Retry actions on error states cover the refresh need. Will add in a later story if desired.
- **"Today's Mini-App Events" KPI:** the mock returns a fixed integer (`14`). Real aggregation arrives in Epic 5. No deviation from the AC.
- **Mock data determinism:** `MOCK_NOW` is a fixed timestamp (`2026-07-17T09:30:00Z`) so relative-time assertions are stable across runs.

## Open Questions

- None blocking. The trace-route placeholder (`/audit?run=`) should be revisited when Epic 4 lands.

## Test Results

```
Test Files  20 passed (20)
     Tests  139 passed (139)
  Duration  6.12s
```

```
npx tsc --noEmit  → clean
npm run build     → ✓ built in 406ms
```
