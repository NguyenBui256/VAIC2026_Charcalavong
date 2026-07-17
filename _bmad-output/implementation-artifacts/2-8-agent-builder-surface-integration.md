---
baseline_commit: 4e2c5ad3cb823b8edb5f8ce6d0ea8b3d94a4fd1c
---

# Story 2.8: Agent Builder Surface Integration

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user configuring an Agent end-to-end**,
I want **the six configuration tabs to behave as one cohesive surface**,
So that **I can move between identity, KB, tools, integrations, prompt, and model without losing context**.

## Acceptance Criteria

(Sourced verbatim from `_bmad-output/planning-artifacts/epics.md` L822–L839.)

1. **AC (6 tabs visible, UX-DR16)** — Opening `/agents/:id` renders all six tabs in the detail navigation: Identity, Knowledge Base, Tools, API Integrations, Prompt, Model. [epics.md L824–826]
2. **AC (Count badges)** — Tabs whose data is countable show a count badge: Knowledge Base → "N documents", Tools → "N tools", API Integrations → "N integrations". Zero/loading states render without a misleading count. [epics.md L827]
3. **AC (Per-tab dirty dot)** — An unsaved-changes dot appears on a tab when that tab's form is dirty, and clears when the tab is saved or reset. [epics.md L828]
4. **AC (Switch-with-unsaved confirmation)** — Switching tabs while the current tab has unsaved changes opens a confirmation dialog "Save changes before leaving?" with **Save / Discard / Cancel** options. Save persists then switches; Discard drops edits then switches; Cancel stays on the current tab. [epics.md L829–830]
5. **AC (Per-tab error state, UX-DR23)** — When any tab fails to load its data, the tab body shows an error state (message + retry), not a silent failure. [epics.md L831–832]
6. **AC (Per-tab loading skeleton, UX-DR23)** — When any tab is loading, a skeleton matching that tab's final layout renders (never a generic spinner). [epics.md L833–834]
7. **AC (New-Agent gating)** — When the Agent has never been saved (new-Agent flow), the Identity tab is the only enabled tab; the other five are disabled until the Agent is saved once (creating the record). [epics.md L835–836]
8. **AC (Detail header + Save All)** — The detail-view header shows the Agent name, Department badge, status pill (Draft/Active), and a global "Save All" button that appears/enables when any tab has unsaved changes. [epics.md L837]
9. **AC (Keyboard nav, UX-DR12)** — Keyboard navigation works across tabs: Tab/Shift+Tab to move focus, Enter to activate, arrow keys to switch between tabs. [epics.md L838]
10. **AC (Responsive, UX-DR13)** — The surface is fully responsive within the desktop-first commitment (1440–1600px target) and collapses the Inspector under 1280px. [epics.md L839]

## Tasks / Subtasks

- [ ] **T1 — Tab registry & shared dirty/count contract** (AC: #1, #2, #3, #8)
  - [ ] T1.1 `src/components/agents/tabRegistry.ts` — single source of truth: ordered array of the six tabs `{ key, label, icon (semanticIcons), component, countKey? }` for `identity | knowledge-base | tools | api-integrations | prompt | model`. Drives both the nav render (AC #1) and the count-badge lookup (AC #2). Icon per tab from `semanticIcons` (`Agent`, `KnowledgeBase`, `Tool`, `ApiIntegration`, `Prompt`, `Model`).
  - [ ] T1.2 `src/components/agents/agentBuilderTypes.ts` — shared types: `TabKey`, `TabDirtyState` (per-tab `isDirty`), `TabRegistration` (`{ isDirty, save(): Promise<void>, reset(): void }`), `TabCounts` (`{ documents?: number; tools?: number; integrations?: number }`).
  - [ ] T1.3 `src/components/agents/AgentBuilderContext.tsx` — React context + provider owning: the map of per-tab `TabRegistration` handles (children register/unregister via `useRegisterTab(tabKey, handle)`), an `anyDirty` selector, `saveAll()` (calls every dirty tab's `save()` in a safe order — Identity first), and the pending-switch guard state. Keeps the shell decoupled from each tab's internal form state.
- [ ] **T2 — Detail shell integration (upgrade AgentDetailShell)** (AC: #1, #2, #3, #7, #8, #9, #10)
  - [ ] T2.1 Upgrade `src/components/agents/AgentDetailShell.tsx` (from Story 2.2) to drive the six tabs from `tabRegistry` (T1.1) instead of hard-coded placeholders, wrapping content in `AgentBuilderProvider`.
  - [ ] T2.2 `src/components/agents/AgentTabNav.tsx` — the tab strip: renders one `AgentTab` per registry entry with label, optional count badge (AC #2), and dirty dot (AC #3). Implements the roving-tabindex keyboard model (AC #9): `role="tablist"`, each tab `role="tab"`, arrow keys move active tab, `Home`/`End` jump, `Enter`/`Space` activate. Disabled tabs are `aria-disabled` and skipped by arrow nav (AC #7).
  - [ ] T2.3 `src/components/agents/AgentDetailHeader.tsx` — header row: Agent name, `DepartmentBadge` (Story 2.2), `AgentStatusPill` (Draft/Active, Story 2.2), and the global **Save All** `Button` (single Primary CTA) shown/enabled only when `anyDirty` (AC #8). Save All calls `saveAll()` and shows a toast on success / inline error on failure.
  - [ ] T2.4 New-Agent gating (AC #7): when `id === "new"` or the Agent record has never been persisted, compute `enabledTabs = ["identity"]`; disable the other five with a tooltip "Save the Agent to unlock this tab". After first successful Identity save (record created → real `:id`), re-enable all tabs and navigate `/agents/:newId`.
  - [ ] T2.5 Responsive shell (AC #10): desktop-first 1440–1600px target; the optional 320px right Inspector collapses under 1280px per UX-DR13. Tab strip wraps/scrolls horizontally rather than overflowing the body; no horizontal page scroll.
- [ ] **T3 — Count badges wiring** (AC: #2)
  - [ ] T3.1 `src/components/agents/useTabCounts.ts` — aggregates counts from the per-tab data hooks that already exist from sibling stories: `useKbDocuments(agentId)` (Story 2.4 → documents), the Tools list hook (Story 2.6 → tools), the API Integrations list hook (Story 2.7 → integrations). Returns `TabCounts`; each field is `undefined` while loading so the badge hides instead of flashing "0".
  - [ ] T3.2 `src/components/agents/TabCountBadge.tsx` — small pill rendering `"N documents" | "N tools" | "N integrations"` with correct singular/plural. Hidden when count is `undefined`; renders "0 documents" only once its query has resolved to an empty list (distinguishes empty from loading).
- [ ] **T4 — Per-tab dirty aggregation** (AC: #3, #8)
  - [ ] T4.1 Each tab component (IdentityTab, KnowledgeBaseTab, ToolsTab, ApiIntegrationsTab, PromptTab, ModelTab) calls `useRegisterTab(tabKey, { isDirty, save, reset })` exposing its own dirty state + save/reset. Editing tabs (Identity, Prompt, Model) report form dirtiness; list-style tabs (KB, Tools, Integrations) report `isDirty=false` for the surface but still contribute counts (their mutations are immediate, not form-buffered — see Dev Notes).
  - [ ] T4.2 The shell reads each registration's `isDirty` to render the per-tab dirty dot (AC #3) and to compute `anyDirty` for Save All (AC #8).
- [ ] **T5 — Switch-with-unsaved confirmation** (AC: #4)
  - [ ] T5.1 `src/components/agents/TabSwitchGuard.tsx` (or inline in shell) — intercept tab-switch intent: if the current tab `isDirty`, open a `ConfirmDialog` (Story 2.2) titled "Save changes before leaving?" with three actions. **Save** → `await currentTab.save()` then switch (abort switch if save fails, keep dialog error); **Discard** → `currentTab.reset()` then switch; **Cancel** → close dialog, stay. Esc = Cancel (UX-DR1).
  - [ ] T5.2 Extend/confirm `ConfirmDialog` supports a three-button variant (Save / Discard / Cancel) with a destructive-styled Discard; if the Story 2.2 `ConfirmDialog` is two-button only, add an optional `tertiaryAction` prop rather than forking a new dialog.
- [ ] **T6 — Per-tab loading / error states** (AC: #5, #6)
  - [ ] T6.1 `src/components/agents/TabBoundary.tsx` — wraps each tab body and enforces the UX-DR23 branch order: error (`ErrorState` + retry) → loading (`Skeleton` matching that tab's layout) → empty (`EmptyState`, where relevant) → data. Retry re-runs the tab's query.
  - [ ] T6.2 Per-tab skeleton shapes: form-shaped skeleton for Identity/Prompt/Model; list/table-shaped skeleton for KB/Tools/Integrations. Reuse `Skeleton` from `src/components/ui`. No generic spinner anywhere (AC #6).
  - [ ] T6.3 Error retry surfaces `ApiError.message`; a failing tab does not blank the whole shell — the header and nav stay interactive so the user can switch to a healthy tab (AC #5).
- [ ] **T7 — Routing / App wiring** (AC: #1, #7)
  - [ ] T7.1 Ensure `/agents/:id` (and the `new` sentinel) resolves to the upgraded shell. If Story 2.2's routing is already in `src/App.tsx`, verify the integration doesn't regress it; otherwise wire the nested route. Tab selection persists via URL query `?tab=<key>` so deep-links and the confirmation-guard survive refresh.
- [ ] **T8 — Tests (Vitest + Testing Library)** (AC: all)
  - [ ] T8.1 `src/components/agents/AgentDetailShell.test.tsx` — all six tabs render in order (AC #1); Identity is default; disabled-tab gating for new Agent (AC #7); tabs unlock after first save.
  - [ ] T8.2 `src/components/agents/AgentTabNav.test.tsx` — count badges render/hide correctly incl. singular/plural + loading-vs-zero (AC #2); dirty dot appears on edit and clears on save/reset (AC #3); keyboard model: arrow keys switch, Enter/Space activate, disabled tabs skipped, Home/End (AC #9).
  - [ ] T8.3 `src/components/agents/TabSwitchGuard.test.tsx` — dirty + switch → dialog with Save/Discard/Cancel; Save persists then switches; Save-failure keeps user on tab; Discard drops edits then switches; Cancel stays; Esc = Cancel (AC #4).
  - [ ] T8.4 `src/components/agents/TabBoundary.test.tsx` — error → `ErrorState` + retry; loading → layout-matching `Skeleton`; healthy header/nav stay interactive while one tab errors (AC #5, #6).
  - [ ] T8.5 `AgentDetailHeader.test.tsx` — name + Department badge + status pill render; Save All hidden when clean, shown/enabled when `anyDirty`, calls `saveAll()`, success toast / failure inline error (AC #8).
  - [ ] T8.6 Mock the count + agent hooks and the sibling-tab modules (`vi.mock`) so specs are deterministic and do not require Stories 2.3–2.7 to be merged (see Dev Notes on graceful degradation).
- [ ] **T9 — Verify** (AC: all)
  - [ ] T9.1 `npx tsc --noEmit` clean.
  - [ ] T9.2 `npx vitest run` — all existing + new tests pass.
  - [ ] T9.3 `npm run build` succeeds.

## Dev Notes

### Scope Boundaries

**Story 2.8 is the Epic-2 CAPSTONE / integration story. It stitches the six tabs into ONE cohesive surface. It does NOT re-implement any tab's feature logic.**

- **In scope:** the detail shell orchestration — tab registry/nav, count badges, per-tab dirty dots, switch-with-unsaved confirmation (Save/Discard/Cancel), new-Agent tab gating, Save All, per-tab loading/error/skeleton boundaries, keyboard nav across tabs, responsive shell (Inspector collapse).
- **Out of scope (owned by their stories, consumed here):**
  - Identity form fields + Agent CRUD → **Story 2.2** (list + detail shell + Identity tab; this story upgrades that shell).
  - Model/Prompt tab (provider/model picker, params, prompt editor, char-count, context-window warning) → **Story 2.3**.
  - Knowledge Base upload/list/status polling → **Story 2.4**; KB retrieval runtime → **Story 2.5**.
  - Tools tab (JSON Schema editor, sandbox, Test Tool) → **Story 2.6**.
  - API Integrations tab (register connection, encrypted auth header, Test Integration) → **Story 2.7**.

### Explicit dependency on Stories 2.2–2.7 (ALL)

This story **depends on all six preceding Epic-2 stories** and integrates their surfaces:

- **2.2** provides `AgentDetailShell.tsx`, the 6-tab scaffold (Identity, Knowledge Base, Tools, API Integrations, Prompt, Model), `IdentityTab.tsx`, `AgentStatusPill.tsx`, `DepartmentBadge.tsx`, `ConfirmDialog.tsx`, `Toast`/`useToast`, and the `/agents/:id` route (incl. the `new` sentinel + first-save-creates-record flow). **This story upgrades that shell** — it does not create a parallel one.
- **2.3** provides `ModelTab.tsx` + `PromptTab.tsx` (editing tabs → contribute `isDirty`).
- **2.4** provides `KnowledgeBaseTab.tsx` + `useKbDocuments.ts` (→ "N documents" count; status-polling list).
- **2.5** provides KB retrieval runtime (backend; no direct UI here — no tab count impact).
- **2.6** provides `ToolsTab.tsx` + its list hook (→ "N tools" count).
- **2.7** provides `ApiIntegrationsTab.tsx` + its list hook (→ "N integrations" count).

**Graceful degradation for parallel development:** if a sibling tab or its hook is not yet merged when this story is built, integrate against the Story 2.2 placeholder panel and a mocked count hook, and swap to the live component/hook when available. Keep the registry (`tabRegistry.ts`) the single seam so wiring a real tab is a one-line change. Tests must mock sibling modules (`vi.mock`) so 2.8 is verifiable independently.

**Note on tab file locations (open question):** Story 2.2 placed the five non-Identity tabs under `src/components/agents/tabs/{...}Tab.tsx`, while Stories 2.3/2.4 place `ModelTab.tsx`/`PromptTab.tsx`/`KnowledgeBaseTab.tsx` directly under `src/components/agents/`. Resolve to ONE location during integration (recommend `src/components/agents/tabs/`), and update `tabRegistry.ts` imports accordingly. This is a path reconciliation, not new behavior.

### UX Compliance

- **UX-DR16 (Agent Builder Surface — six-tab detail)** [epics.md L233, L824–826] — The detail view MUST show exactly six tabs in this order: Identity, Knowledge Base, Tools, API Integrations, Prompt, Model. Identity remains the default landing tab (from Story 2.2). The registry (`tabRegistry.ts`) is the ordered source of truth so the nav and count-badge lookups never drift.
- **UX-DR13 (App Shell — responsive + Inspector collapse)** [epics.md L227, L839] — Desktop-first commitment, 1440–1600px primary target. The optional 320px right Inspector panel collapses under 1280px viewport (sidebar likewise collapses to a 72px icon rail per the app shell, already handled by Story 1.8's `AppShell`). The tab strip must wrap or horizontally scroll within its container — the page body never scrolls horizontally.
- **UX-DR23 (Empty / Loading / Error States)** [epics.md L247, L831–834] — EVERY tab defines all three: Empty (`EmptyState` illustration + CTA where a list can be empty), Loading (`Skeleton` matching that tab's final layout — form-shaped vs list-shaped), Error (`ErrorState` message + retry). No silent failures; a single failing tab must not blank the shell. Follow the branch order established in `src/components/dashboard/RecentRuns.tsx` (error → skeleton → empty → data) via the `TabBoundary` wrapper.
- **UX-DR12 (Accessibility — keyboard nav across tabs)** [epics.md L586, L838] — The tab strip uses the WAI-ARIA tablist pattern: `role="tablist"` on the strip, `role="tab"` on each tab, roving `tabindex` (active tab `0`, others `-1`), arrow keys switch the active tab, `Home`/`End` jump to first/last, `Enter`/`Space` activate, and disabled tabs are `aria-disabled` + skipped by arrow nav. Focus rings visible (`--focus-ring` token). Announce tab-load errors via `ErrorState` `role="alert"`.
- **UX-DR3 (Buttons — single Primary CTA)** — "Save All" is the single Primary `Button` on the shell header. Individual tab Save buttons (Identity/Prompt/Model) are Primary within their own tab body; because only one tab body is mounted at a time plus the header, keep to one Primary per rendered view or the `Button` dev warning fires. Prefer Save All as the shell-level Primary and demote per-tab Save to Secondary where both would co-render.
- **UX-DR1 (Escape routes)** — The Save/Discard/Cancel confirmation closes on Esc with Cancel semantics (no data loss), mirroring `CommandPalette.tsx` / `ConfirmDialog.tsx`.
- **UX-DR9 (Motion)** — Dialog uses `durations.modal` (200ms) + `easings.modal`; toast uses `durations.toast` (280ms); tab-body transitions use only transform/opacity and respect `prefers-reduced-motion`. Import from `src/lib/motion.ts`.
- **UX-DR10/DR11 (Icons)** — Tab icons come from `semanticIcons` in `src/lib/icons.tsx` (lucide-react, 1.5px stroke). Do not add a new icon library or invent icons; if a semantic key is missing (e.g. `Prompt`, `Model`, `ApiIntegration`), reuse the keys defined by Story 2.2/2.3, do not redefine locked entries.

### Architecture Compliance

- **Stack (pinned — no web research)** [ARCHITECTURE-SPINE/stack.md]: React 19, Vite 8, TypeScript 7.x, Tailwind CSS 4, TanStack Query (latest), Vitest (latest). Routing is **react-router-dom** (see `src/App.tsx`), NOT TanStack Router — epics.md L825's `/agents/$id` maps to react-router's `/agents/:id` (syntactic mapping, not a behavioral deviation).
- **API access** — All data goes through `apiFetch<T>()` in `src/lib/api.ts` (JWT + `X-Tenant-Id`/`X-Department-Id` injection, `{data,error,meta}` envelope unwrap, typed `ApiError`, 401→/login). This story issues no new direct API calls — it consumes the per-tab hooks (`useAgent`, `useKbDocuments`, Tools/Integrations list hooks). Do NOT call `fetch` directly.
- **Server state** — TanStack Query via the existing `QueryClient` (`src/main.tsx`, `staleTime: 30_000, retry: 1`). Count badges read the same query keys the tabs use (`["agent-kb", id]`, `["agent-tools", id]`, `["agent-integrations", id]`) so counts stay consistent with tab contents and update when a tab mutates + invalidates. Save All must await each tab's mutation and then rely on their own invalidations.
- **Dirty/save contract** — The shell owns NO form state; each tab registers a `{ isDirty, save, reset }` handle via `useRegisterTab`. This keeps tab internals encapsulated and lets Save All / the switch-guard operate uniformly without knowing any tab's fields. Editing tabs (Identity/Prompt/Model) buffer edits and report dirtiness; list tabs (KB/Tools/Integrations) apply mutations immediately and report `isDirty=false` (their "unsaved" concept is per-row, handled inside the tab).
- **New-Agent gating** — Reuses Story 2.2's "first Identity save creates the record" flow. Until a real `id` exists, only Identity is enabled; the other five are `aria-disabled` with an explanatory tooltip. On successful create, navigate to `/agents/:newId?tab=identity` and enable the full set.

### File Structure (under `frontend/src`)

Create (new):
- `components/agents/tabRegistry.ts` — ordered six-tab registry (label, icon, component, countKey)
- `components/agents/agentBuilderTypes.ts` — `TabKey`, `TabRegistration`, `TabCounts`, dirty types
- `components/agents/AgentBuilderContext.tsx` — provider: tab registrations, `anyDirty`, `saveAll`, switch-guard state, `useRegisterTab`
- `components/agents/AgentTabNav.tsx` — tablist strip with count badge + dirty dot + keyboard model
- `components/agents/AgentDetailHeader.tsx` — name + Department badge + status pill + Save All
- `components/agents/TabCountBadge.tsx` — "N documents/tools/integrations" pill (loading-aware)
- `components/agents/useTabCounts.ts` — aggregates KB/Tools/Integrations counts
- `components/agents/TabSwitchGuard.tsx` — Save/Discard/Cancel confirmation on dirty switch
- `components/agents/TabBoundary.tsx` — per-tab error → skeleton → empty → data wrapper
- Co-located `*.test.tsx` for shell, nav, switch-guard, boundary, header

Modify (existing, from Story 2.2):
- `components/agents/AgentDetailShell.tsx` — drive tabs from registry, wrap in `AgentBuilderProvider`, mount header + nav + boundary
- `components/agents/IdentityTab.tsx` (+ 2.3/2.4/2.6/2.7 tabs) — call `useRegisterTab(...)` to expose `{ isDirty, save, reset }`
- `components/ui/ConfirmDialog.tsx` — optional `tertiaryAction` for the three-button Save/Discard/Cancel variant (only if 2.2 shipped it two-button)
- `src/App.tsx` — verify `/agents/:id` (+ `new`) routing intact (do not regress Story 2.2)

Reuse (do not recreate): `Button`, `StatusPill`, `Card`, `EmptyState`, `Skeleton`, `ErrorState`, `Tooltip`, `Toast`/`useToast`, `ConfirmDialog` from `src/components/ui`; `AgentStatusPill`, `DepartmentBadge`, `IdentityTab` from `src/components/agents` (Story 2.2); `semanticIcons`/`stateMapping` from `src/lib/icons.tsx`; motion tokens from `src/lib/motion.ts`; tokens from `src/styles/tokens.css` + `components.css`.

### Testing (Vitest)

- Framework: Vitest + @testing-library/react (see `src/test-setup.ts`, existing `*.test.tsx`). Run `npx vitest run`.
- Wrap the shell in `MemoryRouter` (route `/agents/:id`) and a fresh `QueryClientProvider` per test; mount `ToastProvider`.
- Mock sibling tab modules and count hooks (`vi.mock("../agents/tabs/ToolsTab")`, `vi.mock("../agents/useKbDocuments")`, etc.) so 2.8 is verifiable without 2.3–2.7 merged. Provide fake `TabRegistration` handles to assert dirty-dot / Save All / switch-guard behavior deterministically.
- Assert AC-specific behaviors: six tabs in order; badge singular/plural + hidden-while-loading vs "0" when empty; dirty dot only after edit and cleared after save/reset; three-button dialog on dirty switch with correct Save/Discard/Cancel outcomes (incl. save-failure staying on tab); disabled tabs for new Agent then unlocked after first save; keyboard arrow/Enter/Home/End on the tablist skipping disabled tabs; a single tab erroring keeps header + nav interactive.
- Do NOT hit a live backend. Prefer module mocks and query-client injection.

### Anti-Patterns (do NOT do these)

- Do NOT re-implement any tab's feature logic — this is integration only. Consume 2.2–2.7 surfaces.
- Do NOT let the shell own each tab's form state — use the `useRegisterTab` `{ isDirty, save, reset }` contract so tabs stay encapsulated.
- Do NOT create a second/parallel detail shell — upgrade Story 2.2's `AgentDetailShell.tsx`.
- Do NOT show a count badge while its query is loading (avoid flashing "0"); only render "0 documents" after the list resolves empty.
- Do NOT switch tabs silently when dirty — always route through the Save/Discard/Cancel confirmation (AC #4).
- Do NOT enable the non-Identity tabs before the Agent record exists (new-Agent flow, AC #7).
- Do NOT render a generic spinner for tab loading — use a layout-matching `Skeleton` (UX-DR23).
- Do NOT blank the whole shell when one tab errors — keep header + nav interactive so the user can switch away (AC #5).
- Do NOT call `fetch()` directly or hand-roll auth/tenant headers — use `apiFetch`/the existing tab hooks.
- Do NOT use TanStack Router or add a new router/dialog/icon/toast library — reuse existing primitives.
- Do NOT mount more than one Primary `Button` per rendered view (UX-DR3 dev warning) — Save All is the shell Primary.
- Do NOT reassign or extend the locked `stateMapping`/`semanticIcons` in `lib/icons.tsx`.
- Do NOT modify `sprint-status.yaml` (the orchestrator owns it centrally).

## References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.8 (L816–L839)] — story + all acceptance criteria
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.2 (L684–L706)] — list + detail shell + Identity tab (upgraded here)
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.3..2.7 (L708–L814)] — Model/Prompt, KB, Tools, API Integrations tabs (consumed)
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR16 (L233)] — Agent Builder six-tab surface
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR13 (L227)] — app shell responsive + 320px Inspector collapse under 1280px
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR23 (L247)] — empty/loading/error states
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR12 (L586)] — accessibility / keyboard nav
- [Source: _bmad-output/implementation-artifacts/2-2-agent-list-detail-shell-identity-tab.md] — `AgentDetailShell`, tab scaffold, `ConfirmDialog`, `Toast`, `AgentStatusPill`, `DepartmentBadge`, `/agents/:id` + `new` flow
- [Source: _bmad-output/implementation-artifacts/2-3-per-agent-model-selection-prompt-editing.md] — `ModelTab.tsx`, `PromptTab.tsx`
- [Source: _bmad-output/implementation-artifacts/2-4-knowledge-base-upload-storage.md] — `KnowledgeBaseTab.tsx`, `useKbDocuments.ts` (documents count)
- [Source: frontend/src/App.tsx] — react-router-dom routing (`/agents` placeholder + guards)
- [Source: frontend/src/lib/api.ts] — `apiFetch`, `ApiError`, envelope unwrap, header injection
- [Source: frontend/src/components/ui/index.ts] — reusable primitives barrel (Story 1.9)
- [Source: frontend/src/lib/icons.tsx] — locked `semanticIcons` + `stateMapping`
- [Source: frontend/src/lib/motion.ts] — motion durations/easings (UX-DR9)
- [Source: frontend/src/hooks/useDashboardData.ts] — TanStack Query hook + test-mock pattern
- [Source: frontend/src/components/dashboard/RecentRuns.tsx] — UX-DR23 branch-order reference
- [Source: frontend/src/components/CommandPalette/CommandPalette.tsx] — modal overlay + focus-trap + Esc pattern
- [Source: ARCHITECTURE-SPINE/stack.md] — pinned stack (React 19 / Vite 8 / TS 7 / Tailwind 4 / TanStack Query / Vitest)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
