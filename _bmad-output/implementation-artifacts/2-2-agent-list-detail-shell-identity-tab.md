---
baseline_commit: 86e0dc8c653ccb3633a45d3fa8e37c53e4747fe7
---

# Story 2.2: Agent List & Detail Shell with Identity Tab

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **a list of all Agents in my Tenant and a detail view with tabbed configuration**,
So that **I can navigate the Agent inventory and edit an Agent's identity without hunting through menus**.

## Acceptance Criteria

(Sourced verbatim from `_bmad-output/planning-artifacts/epics.md` L690–L706.)

1. **AC (List surface)** — Navigating to `/agents` shows a searchable list of Agents in the caller's Tenant; each row shows name, Department badge, status (Draft/Active), owner, last-modified. [epics.md L693–694]
2. **AC (Department filter)** — The list supports filtering by Department via a header dropdown. [epics.md L695]
3. **AC (Text search, debounced)** — The list supports text search on name, debounced at 200ms. [epics.md L696]
4. **AC (UX-DR23 empty)** — An empty state renders when there are zero Agents (illustration + CTA). [epics.md L697]
5. **AC (6-tab detail, UX-DR16)** — Clicking a row or "New Agent" opens the detail view at `/agents/:id` with a 6-tab navigation: Identity, Knowledge Base, Tools, API Integrations, Prompt, Model. [epics.md L698–699]
6. **AC (Identity default tab)** — The Identity tab is the default landing tab. [epics.md L700]
7. **AC (Identity form fields)** — The Identity tab shows a form: Name (text, required), Department (select, required), System Prompt (textarea, required), Status (Draft/Active toggle). [epics.md L701]
8. **AC (UX-DR8 form patterns)** — Required fields marked with `*` in destructive color, validate on blur, show inline errors. [epics.md L702]
9. **AC (Save → PATCH)** — Editing the form and clicking Save fires `PATCH /agents/{id}`; success shows a toast; failure shows an inline error. [epics.md L703–704]
10. **AC (Dirty indicator)** — An unsaved-changes indicator (dirty dot in the tab) appears when the form is modified and not saved. [epics.md L705]
11. **AC (Unsaved-changes guard)** — Navigating away with unsaved changes shows a confirmation dialog. [epics.md L706]

## Tasks / Subtasks

- [ ] **T1 — Agent API layer & types** (AC: #1, #5, #7, #9)
  - [ ] T1.1 `src/lib/agentsApi.ts` — TS types (`Agent`, `AgentStatus = "draft" | "active"`, `AgentListParams`, `CreateAgentInput`, `UpdateAgentInput`) mirroring the Story 2.1 record shape (`id`, `tenant_id`, `department_id`, `owner_id`, `name`, `system_prompt`, `status`, `created_at`, `updated_at`/`last_modified`, `version`).
  - [ ] T1.2 Typed functions wrapping `apiFetch` from `src/lib/api.ts`: `listAgents(params)` → `GET /agents?department_id=&q=`, `getAgent(id)` → `GET /agents/{id}`, `createAgent(input)` → `POST /agents`, `updateAgent(id, patch)` → `PATCH /agents/{id}`. All rely on `apiFetch` for JWT + `X-Tenant-Id`/`X-Department-Id` header injection and `{data,error,meta}` envelope unwrapping (Story 1.4 / 1.8).
  - [ ] T1.3 `src/lib/departmentsApi.ts` (or extend agentsApi) — `listDepartments()` for the filter dropdown and Identity Department select. See Open Questions re: department source endpoint.
- [ ] **T2 — Data hooks (TanStack Query)** (AC: #1, #2, #3, #9)
  - [ ] T2.1 `src/hooks/useAgents.ts` — `useQuery` keyed `["agents", { departmentId, q }]` calling `listAgents`; exposes loading/error/data.
  - [ ] T2.2 `src/hooks/useAgent.ts` — `useQuery` keyed `["agent", id]` calling `getAgent`; `enabled: !!id && id !== "new"`.
  - [ ] T2.3 `src/hooks/useAgentMutations.ts` — `useMutation` for `updateAgent` (and `createAgent` for the "New Agent" flow); on success invalidates `["agents"]` and `["agent", id]`.
  - [ ] T2.4 `src/hooks/useDepartments.ts` — `useQuery` keyed `["departments"]` calling `listDepartments`.
  - [ ] T2.5 `src/lib/useDebounce.ts` — generic 200ms debounce hook for the search input (AC #3).
- [ ] **T3 — Shared UX primitives (net-new)** (AC: #9, #11)
  - [ ] T3.1 `src/components/ui/Toast.tsx` + `ToastProvider` + `useToast()` — transient success/error toast; 280ms toast-in motion (UX-DR9 `durations.toast`); mount provider once at app root; `aria-live="polite"`.
  - [ ] T3.2 `src/components/ui/ConfirmDialog.tsx` — modal confirm (title, body, Confirm/Cancel). Reuse the overlay + focus-trap + Esc-to-close pattern from `CommandPalette.tsx` and `durations.modal`/`easings.modal` (UX-DR9, UX-DR1 escape routes).
  - [ ] T3.3 Extend `src/components/ui/index.ts` barrel with `Toast`/`ToastProvider`/`useToast` and `ConfirmDialog`.
- [ ] **T4 — Agent list surface** (AC: #1, #2, #3, #4)
  - [ ] T4.1 `src/routes/agents.tsx` — list route: header with title, "New Agent" Primary CTA (UX-DR3), Department filter dropdown, debounced search input. Renders `Table` primitive (UX-DR6) with columns: Name, Department (badge), Status (Draft/Active pill), Owner, Last-modified. Row click → navigate `/agents/:id`. Loading → skeleton rows; error → `ErrorState` + retry (UX-DR23); zero rows → `EmptyState` with "New Agent" CTA.
  - [ ] T4.2 `src/components/agents/AgentStatusPill.tsx` — Draft → reuse `StatusPill state="draft"`; Active → emerald pill using `--color-success` token with label "Active" (agent status is not part of the locked RunState set — see Dev Notes).
  - [ ] T4.3 `src/components/agents/DepartmentBadge.tsx` — small badge using `semanticIcons.Department` + department name.
- [ ] **T5 — Detail shell & 6-tab navigation** (AC: #5, #6)
  - [ ] T5.1 `src/routes/agent-detail.tsx` — route for `/agents/:id`; reads `:id` param, loads `useAgent(id)`; renders `AgentDetailShell`. Handles `id === "new"` for the "New Agent" flow.
  - [ ] T5.2 `src/components/agents/AgentDetailShell.tsx` — 6-tab nav (Identity, Knowledge Base, Tools, API Integrations, Prompt, Model) per UX-DR16; Identity is the default active tab (AC #6). Tab state via URL query (`?tab=identity`) or local state. Tabs carry a dirty-dot slot (AC #10). Loading/error/empty per UX-DR23.
  - [ ] T5.3 Placeholder panels for the 5 non-Identity tabs (`KnowledgeBaseTab`, `ToolsTab`, `ApiIntegrationsTab`, `PromptTab`, `ModelTab`) — each a "Coming soon" panel wired to its real story (2.3–2.6). DO NOT implement their functionality here.
- [ ] **T6 — Identity tab form** (AC: #7, #8, #9, #10)
  - [ ] T6.1 `src/components/agents/IdentityTab.tsx` — form using `FormField` (UX-DR8): Name (text, required), Department (select, required — via `FormField` `children` render slot), System Prompt (textarea, required — via `children` slot), Status Draft/Active toggle. Required `*` in destructive color, validate on blur, inline errors.
  - [ ] T6.2 Dirty tracking — compare current form values to the loaded Agent; expose `isDirty` up to the shell so the Identity tab shows a dirty dot (AC #10). Reset dirty on successful save.
  - [ ] T6.3 Save handler — call `useAgentMutations().update`; on success `useToast().show("Agent saved")` and refetch; on failure render inline error (map `ApiError.message`) (AC #9).
- [ ] **T7 — Unsaved-changes navigation guard** (AC: #11)
  - [ ] T7.1 Block in-app navigation when `isDirty` using react-router `useBlocker` (v6.4+ data-router) OR a route-level guard; on block, open `ConfirmDialog` ("Discard unsaved changes?"). Confirm → proceed; Cancel → stay.
  - [ ] T7.2 `beforeunload` handler for full-page unload/refresh while dirty.
- [ ] **T8 — Routing wiring** (AC: #1, #5)
  - [ ] T8.1 `src/App.tsx` — replace the `/agents` `ComingSoon` placeholder with `<AgentsPage />`; add nested route `/agents/:id` → `<AgentDetailPage />`. Mount `ToastProvider` at the app root (inside `CommandPaletteProvider` scope or wrapping it).
- [ ] **T9 — Tests (Vitest + Testing Library)** (AC: all)
  - [ ] T9.1 `src/routes/agents.test.tsx` — list renders rows, department filter changes query, debounced search, empty state, loading skeleton, error state, "New Agent" navigates.
  - [ ] T9.2 `src/routes/agent-detail.test.tsx` — 6 tabs present, Identity is default, tab switching, placeholder panels render.
  - [ ] T9.3 `src/components/agents/IdentityTab.test.tsx` — required markers, blur validation + inline errors, dirty dot appears on edit, Save fires update + success toast, failure shows inline error.
  - [ ] T9.4 Unsaved-changes guard test — dirty + navigate → ConfirmDialog; Confirm proceeds, Cancel stays.
  - [ ] T9.5 `src/components/ui/Toast.test.tsx`, `ConfirmDialog.test.tsx` — render, auto-dismiss/close, Esc closes dialog.
  - [ ] T9.6 Mock `apiFetch`/agentsApi in tests (no live network) so specs are deterministic.
- [ ] **T10 — Verify** (AC: all)
  - [ ] T10.1 `npx tsc --noEmit` clean.
  - [ ] T10.2 `npx vitest run` — all existing + new tests pass.
  - [ ] T10.3 `npm run build` succeeds.

## Dev Notes

### Scope Boundaries

**Story 2.2 delivers the Agent list surface + detail shell + functional Identity tab ONLY. Do NOT implement:**
- Model / Prompt tab functionality (provider picker, prompt editor) → **Story 2.3**
- Knowledge Base upload/list → **Story 2.4**; KB retrieval → **Story 2.5**
- Tools tab (schemas) → **Story 2.6**; API Integrations → later Epic 2 story
- The 5 non-Identity tabs are **placeholder panels** in this story (structure only, "Coming soon").
- Backend Agent endpoints — those are **Story 2.1** (this story consumes them, see dependency below).

### Dependency on Story 2.1 (explicit)

This story **consumes the Agent endpoints delivered by Story 2.1**: `POST /agents`, `GET /agents/{id}`, `GET /agents` (list, with optional `department_id` filter), and `PATCH /agents/{id}`. The Story 2.1 record shape is the contract for the `Agent` TS type: `{ id (UUID v7), tenant_id, department_id, owner_id, name, system_prompt, status, created_at, version }` (epics.md L672). Tenant scoping, RLS, and the `403 FORBIDDEN` / `404` (cross-tenant) semantics are enforced server-side by 2.1 — the frontend surfaces `ApiError` messages but does not re-implement authz. If 2.1 is not yet merged when this story starts, develop against a mocked `agentsApi` and wire to the live endpoints when available.

### UX Compliance

- **UX-DR16 (Agent Builder Surface)** [epics.md L233] — List view (all Agents in Tenant with status pills, search, filter by Department) + Detail view with the exact 6 tabs: Identity (name, Department, system prompt), Knowledge Base, Tools, API Integrations, Prompt, Model. This story builds the full shell and the Identity tab; the other five are placeholders. Identity is the default landing tab.
- **UX-DR8 (Form Patterns)** [epics.md L217] — Labels always visible above inputs (never placeholder-only), required fields marked `*` in destructive color, helper text below input, error replaces helper in destructive color, inline validation on **blur, not keystroke**. The existing `FormField` primitive (`src/components/ui/FormField.tsx`) already implements all of this — use it, including its `children` render slot for the Department `<select>` and System Prompt `<textarea>`.
- **UX-DR23 (Empty / Loading / Error States)** [epics.md L247] — Every surface (list + each data-loading tab) must define: Empty state (`EmptyState` illustration + CTA), Loading state (`Skeleton` matching final layout, never a generic spinner), Error state (`ErrorState` message + retry). No silent failures. Follow the exact pattern established in `src/components/dashboard/RecentRuns.tsx` (error → skeleton → empty → data branch order).
- **UX-DR3 (Buttons)** — "New Agent" is the single Primary CTA on the list view; Save is the single Primary CTA on the Identity tab. The `Button` primitive fires a dev warning if more than one Primary mounts — keep to one per view.
- **UX-DR1 (Escape routes)** — `ConfirmDialog` must close on Esc (Cancel semantics), mirroring `CommandPalette.tsx`.
- **UX-DR9 (Motion)** — Toast uses `durations.toast` (280ms), ConfirmDialog uses `durations.modal` (200ms) + `easings.modal`. Import from `src/lib/motion.ts`. Only transform/opacity animate; respect `prefers-reduced-motion`.
- **UX-DR10/DR11 (Icons)** — Use `semanticIcons` from `src/lib/icons.tsx`: `Agent` (Bot), `Department` (Building2), `KnowledgeBase`, `Tool`, `ApiIntegration`, `Model`, plus the locked `stateMapping` for the Draft pill. lucide-react only, 1.5px stroke. No new icon library.

### Architecture Compliance

- **Stack (pinned — no web research needed)** [ARCHITECTURE-SPINE/stack.md]: React 19, Vite 8, TypeScript 7.x, Tailwind CSS 4, TanStack Query (latest), Vitest (latest). Routing is **react-router-dom** (already in use in `App.tsx`), not TanStack Router.
- **Routing path note** — epics.md L699 writes the detail route as `/agents/$id` (TanStack Router file-route syntax). The project uses react-router-dom, so implement it as `/agents/:id`. This is a syntactic mapping, not a behavioral deviation.
- **API access** — All calls go through `apiFetch<T>()` in `src/lib/api.ts` (Story 1.8), which injects `Authorization: Bearer <jwt>`, `X-Tenant-Id`, `X-Department-Id`, unwraps the `{data,error,meta}` envelope (Story 1.4 contract), throws typed `ApiError(message, status, code)`, and auto-redirects to `/login` on 401. Do NOT call `fetch` directly and do NOT re-implement header injection.
- **Server state** — Use TanStack Query (`useQuery`/`useMutation`) via the `QueryClient` already provided in `src/main.tsx` (`staleTime: 30_000, retry: 1`). Follow the hook shape established in `src/hooks/useDashboardData.ts`. Mutations invalidate the relevant query keys on success.
- **Agent status pill** — Agent `status` is `Draft | Active`, which is NOT in the locked `RunState` set (`pending|running|success|error|escalated|draft`). Reuse `StatusPill state="draft"` for Draft; for Active render a dedicated emerald pill built from the `--color-success` token so the locked `stateMapping` labels stay untouched (UX-DR11 consistency preserved). Encapsulate in `AgentStatusPill.tsx`.

### File Structure (under `frontend/src`)

Create (new):
- `src/routes/agents.tsx` — list surface (`/agents`)
- `src/routes/agent-detail.tsx` — detail shell route (`/agents/:id`)
- `src/components/agents/AgentDetailShell.tsx` — 6-tab nav container
- `src/components/agents/IdentityTab.tsx` — Identity form
- `src/components/agents/AgentStatusPill.tsx`, `DepartmentBadge.tsx`
- `src/components/agents/tabs/{KnowledgeBaseTab,ToolsTab,ApiIntegrationsTab,PromptTab,ModelTab}.tsx` — placeholders
- `src/components/ui/Toast.tsx`, `src/components/ui/ConfirmDialog.tsx` (+ barrel export)
- `src/lib/agentsApi.ts`, `src/lib/departmentsApi.ts`, `src/lib/useDebounce.ts`
- `src/hooks/useAgents.ts`, `useAgent.ts`, `useAgentMutations.ts`, `useDepartments.ts`
- Co-located `*.test.tsx` for each surface/component

Modify (existing):
- `src/App.tsx` — replace `/agents` `ComingSoon` placeholder, add `/agents/:id`, mount `ToastProvider`
- `src/components/ui/index.ts` — export `Toast`/`ToastProvider`/`useToast`, `ConfirmDialog`

Reuse (do not recreate): `Button`, `StatusPill`, `Card`, `Table`, `FormField`, `EmptyState`, `Skeleton`, `ErrorState`, `Tooltip` from `src/components/ui` (barrel `index.ts`); design tokens from `src/styles/tokens.css` + `components.css` (Story 1.8); `semanticIcons`/`stateMapping` from `src/lib/icons.tsx`; motion tokens from `src/lib/motion.ts`.

### Testing (Vitest)

- Framework: Vitest + @testing-library/react (see `src/test-setup.ts` and any existing `*.test.tsx`). Run `npx vitest run`.
- Mock the API at the `agentsApi`/`apiFetch` boundary — never hit a live backend. Prefer injecting a mock module (as `useDashboardData` does with its `__set*` mock mutators) or `vi.mock("../lib/agentsApi")`.
- Wrap components needing router context in `MemoryRouter` (see `App.test.tsx` — `AppRoutes` is exported specifically for this).
- Wrap components needing query context in a fresh `QueryClientProvider` per test.
- Assert on UX-DR8 behaviors: required `*` present, no validation on keystroke, error appears on blur, error clears on edit.
- Assert dirty-dot appears only after edit and clears after successful save; assert ConfirmDialog blocks navigation when dirty.

### Anti-Patterns (do NOT do these)

- Do NOT call `fetch()` directly or hand-roll auth/tenant headers — use `apiFetch`.
- Do NOT use TanStack Router or add a new router — the app is on react-router-dom.
- Do NOT add a new icon library, toast library, or modal/dialog library — build Toast/ConfirmDialog from the existing CSS/motion tokens and the CommandPalette modal pattern.
- Do NOT reassign or extend the locked `stateMapping`/`semanticIcons` in `lib/icons.tsx` to fake an "Active" state — build `AgentStatusPill` separately.
- Do NOT validate form fields on every keystroke — blur only (UX-DR8). Do NOT use placeholder-only labels.
- Do NOT render a generic spinner for loading — use `Skeleton` matching the final layout (UX-DR23).
- Do NOT implement the 5 non-Identity tabs' functionality — placeholders only.
- Do NOT mount more than one Primary `Button` per view (UX-DR3 dev warning).
- Do NOT modify `sprint-status.yaml` (orchestrator owns it centrally).

## References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.2 (L684–L706)] — story + all acceptance criteria
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.1 (L662–L682)] — consumed Agent endpoints + record shape
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR16 (L233)] — Agent Builder surface, 6 tabs
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR8 (L217)] — form patterns
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR23 (L247)] — empty/loading/error states
- [Source: frontend/src/lib/api.ts] — `apiFetch`, `ApiError`, envelope unwrap, header injection (Story 1.8 / 1.4 envelope)
- [Source: frontend/src/components/ui/index.ts] — reusable primitives barrel (Story 1.9)
- [Source: frontend/src/components/ui/FormField.tsx] — UX-DR8 form primitive with `children` slot
- [Source: frontend/src/lib/icons.tsx] — locked `semanticIcons` + `stateMapping`
- [Source: frontend/src/lib/motion.ts] — motion durations/easings (UX-DR9)
- [Source: frontend/src/hooks/useDashboardData.ts] — TanStack Query hook + test-mock pattern
- [Source: frontend/src/routes/dashboard.tsx + components/dashboard/RecentRuns.tsx] — surface + UX-DR23 branch-order reference
- [Source: frontend/src/App.tsx] — react-router-dom routing + `ComingSoon` `/agents` placeholder to replace
- [Source: frontend/src/main.tsx] — QueryClient config; where to mount ToastProvider
- [Source: frontend/src/components/CommandPalette/CommandPalette.tsx] — modal overlay + focus-trap + Esc pattern for ConfirmDialog
- [Source: ARCHITECTURE-SPINE/stack.md] — pinned stack (React 19 / Vite 8 / TS 7 / Tailwind 4 / TanStack Query / Vitest)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
