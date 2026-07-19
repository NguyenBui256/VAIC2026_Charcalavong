---
baseline_note: "down_revision unresolved at authoring time — implementer MUST run `uv run alembic heads` before T2.1 and use the live value, NOT any head observed in this plan"
---

# Story 3.1: Workflow Definition CRUD & UI

Status: ready-for-dev

## Story

As a **user with builder role**,
I want **to create and edit Workflows described in natural language**,
so that **the Orchestrator can dynamically decompose my intent into Tasks at run time without hard-coded routing**.

This is the **foundation story for Epic 3**. It creates the `workflows` table (RLS-protected per AD-2), fills the `orchestrator` module's `models.py`/`service.py`/`routes.py` for Workflow CRUD (the module currently has 3 one-line stub files), and the CRUD + list/detail UI that Story 3.2 (Run lifecycle) and all downstream Epic-3 stories build on. Mirror Epic 2 Story 2.1's shape exactly (same module layering, same RLS pattern, same audit convention) — do not re-invent.

## Acceptance Criteria

1. **AC1 — POST /workflows creates a scoped Workflow (201)**: An authenticated builder posts `POST /workflows` with `{name, description, constraints?: string[]}` and receives `201` with `{id (UUID v7), tenant_id, owner_id, created_at, version}`. `tenant_id` from `tenant_context`; `owner_id` = caller `user_id`; `version` starts at 1. (epics.md L856–857, FR-7)
2. **AC2 — Description is a run-time hint, not a template**: No code path treats `description` as anything other than opaque text passed to the Orchestrator at Run time — Story 3.1 does NOT decompose it. Assert no decomposition logic exists in this story's scope. (FR-7 consequence)
3. **AC3 — GET /workflows is tenant-scoped**: `GET /workflows` returns only Workflows in the caller's Tenant (RLS enforced, no Python `WHERE tenant_id`). (epics.md L859)
4. **AC4 — Cross-tenant GET returns 404, not 403**: `GET /workflows/{id}` for a Workflow owned by a different Tenant returns `404` (`code: "not_found"`), never `403`. (epics.md L860)
5. **AC5 — List page renders required columns**: `/workflows` shows name, owner, run count, last-run timestamp, status pill if currently running, with text search and owner filter. (epics.md L861–863)
6. **AC6 — Definition tab form**: `/workflows/$id` defaults to the Definition tab: Name (required), Description (textarea, required), Constraints (chip-list editor, optional list of "must check X" statements). Form follows UX-DR8 (labels above inputs, required marked `*`, inline validation on blur). (epics.md L864–866)
7. **AC7 — Unsaved-changes guard**: Navigating away from the Definition tab with unsaved changes triggers a confirmation dialog. (epics.md L867)
8. **AC8 — Audit on every CRUD op**: `POST`/`PATCH` each emit exactly one `audit.log()` entry with `type: "workflow.created" | "workflow.updated"`, routed through `AuditPort` (never direct SQL). (epics.md L868, FR-21, AD-4)
9. **AC9 — RLS applied to `workflows`; direct SQL cross-tenant returns empty**: `workflows` table has RLS policies (ENABLE + FORCE + `tenant_id = current_setting('app.tenant_id')::uuid`). Raw SQL under TenantA cannot read TenantB rows. (AD-2)
10. **AC10 — builder role required to create/mutate**: `POST`/`PATCH` require `role == "builder"`; non-builder → `403 FORBIDDEN`. Read/list available to any authenticated tenant user (mirrors Story 2.1 AC10 convention).

## Tasks / Subtasks

- [ ] **T1 — `workflows` model** (AC: #1, #9)
  - [ ] T1.1 Fill `backend/app/modules/orchestrator/models.py`: `Workflow(Base)` SQLAlchemy 2.x `Mapped[...]` declarative, `__tablename__ = "workflows"`
  - [ ] T1.2 Columns: `id` (`UUID(as_uuid=True)` PK, `default=uuid7`), `tenant_id UUID NOT NULL` (FK `tenants.id`, `ondelete="CASCADE"`), `owner_id UUID NOT NULL` (FK `users.id`, `ondelete="RESTRICT"`)
  - [ ] T1.3 Domain columns: `name String(255) NOT NULL`, `description Text NOT NULL`, `constraints JSONB NOT NULL server_default="[]"` (list of strings), `confidence_threshold Float NOT NULL server_default="0.7"` (pre-provision for Story 3.5's FR-11 configurable threshold — see plan.md Open Question 2, avoids a follow-up migration), `escalation_timeout_seconds Integer NOT NULL server_default="300"` (pre-provision for Story 3.6's configurable 5-min timeout, same rationale), `version Integer NOT NULL default 1`
  - [ ] T1.4 Timestamps: `created_at`/`updated_at DateTime(timezone=True) server_default=func.now()` (mirror `tenant/models.py:44-46`). No soft-delete column — Workflows are not soft-deletable per the ACs (out of scope; add later if a DELETE AC is added)
- [ ] **T2 — Alembic migration: create `workflows` + RLS** (AC: #1, #9)
  - [ ] T2.1 **FIRST: `cd backend && uv run alembic heads`** — capture the live head. `down_revision` MUST be that value (NOT any head value referenced elsewhere in this plan — Epic 2 is still landing migrations).
  - [ ] T2.2 `uv run alembic revision -m "create workflows rls"`; `upgrade()`: `op.create_table("workflows", ...)` mirroring the model; index `ix_workflows_tenant_id`
  - [ ] T2.3 RLS DDL — copy the exact pattern from `alembic/versions/82478b8e9fea_create_tools_rls.py` (latest Epic-2 example) or `34cd8281e2b3_create_audit_trail_table.py:96-105`: `ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;` + `FORCE ROW LEVEL SECURITY;` + `CREATE POLICY tenant_isolation_policy ON workflows USING (tenant_id = current_setting('app.tenant_id')::uuid) WITH CHECK (...)`
  - [ ] T2.4 Grants: `GRANT SELECT, INSERT, UPDATE ON workflows TO vaic_app;` (no DELETE grant needed — no soft-delete AC in this story; add a later migration if Story 3.x adds one)
  - [ ] T2.5 `downgrade()`: drop policy, disable RLS, drop table
  - [ ] T2.6 Idempotency: `uv run alembic upgrade head` twice — second run is a no-op
- [ ] **T3 — Service layer** (AC: #1–#8, #10)
  - [ ] T3.1 Fill `backend/app/modules/orchestrator/service.py`. Domain functions read `tenant_context.get()` — NEVER accept `tenant_id` as an argument
  - [ ] T3.2 `create_workflow(session, *, owner_id, role, name, description, constraints=None) -> Workflow` — assert `role == "builder"` (else `AuthorizationError(code="FORBIDDEN")`); INSERT with `owner_id`, `tenant_id` from context
  - [ ] T3.3 `get_workflow(session, workflow_id) -> Workflow` — `select(Workflow).where(Workflow.id == id)`; `None` → `NotFoundError` (yields 404 for cross-tenant via RLS, AC4)
  - [ ] T3.4 `list_workflows(session, *, search=None, owner_id=None) -> list[Workflow]` — `select(Workflow)`, optional `name ILIKE` search + `owner_id` filter (domain filters only, NEVER `tenant_id` — RLS owns that)
  - [ ] T3.5 `update_workflow(session, workflow_id, principal, **changes) -> Workflow` — allow if `principal.role == "builder"` AND (`workflow.owner_id == principal.user_id` OR principal is a builder — Workflows have no department scope, so any builder in the tenant may edit; simpler than Agent's dept-based rule). Bump `version` on update
  - [ ] T3.6 `serialize_workflow(workflow) -> dict` — `{id, tenant_id, owner_id, name, description, constraints, confidence_threshold, escalation_timeout_seconds, version, created_at, updated_at}` (ISO 8601 ms)
- [ ] **T4 — Audit wiring** (AC: #8)
  - [ ] T4.1 After successful commit, `audit.log(AuditEntry(...))` via `PostgresAuditSink` with `type` in `workflow.created|workflow.updated`
  - [ ] T4.2 Reuse the `crud_audit_ids(entity_id)` helper from `app/core/deps.py` (OQ-1 stopgap, already established by Epic 2) — `run_id = str(workflow.id)`, `step_id = uuid7()`, `latency_ms = 0`, `model = ""`. Do NOT invent a new convention.
- [ ] **T5 — Routes** (AC: #1–#7, #10)
  - [ ] T5.1 Fill `backend/app/modules/orchestrator/routes.py`: `APIRouter(prefix="/workflows", tags=["workflows"])`; register in `app/main.py` as an ADDITIVE line at the end of the router-includes block (do not reorder or touch Epic-2 lines — coordinate/rebase if conflicting)
  - [ ] T5.2 Pydantic schemas: `CreateWorkflowRequest{name, description, constraints: list[str] | None}`, `UpdateWorkflowRequest{name?, description?, constraints?, confidence_threshold?, escalation_timeout_seconds?}`
  - [ ] T5.3 Endpoints: `POST ""` (201), `GET "/{workflow_id}"`, `GET ""` (`search`, `owner_id` query params), `PATCH "/{workflow_id}"`
  - [ ] T5.4 Use `get_tenant_session` (from `app/core/deps.py`) + `Principal` from `request.state`. Success envelope `{data, error, meta}`; errors via registered `DomainError` handlers
- [ ] **T6 — Frontend: list + detail shell** (AC: #5, #6, #7)
  - [ ] T6.1 `/workflows` route — searchable list (200ms debounce), owner filter, empty state (UX-DR23: "No workflows yet."), reuse Epic-1/2 primitives (Table, StatusPill, Card)
  - [ ] T6.2 `/workflows/$id` — Definition tab (default view): Name/Description/Constraints chip-list, UX-DR8 validation-on-blur, dirty-state tracking
  - [ ] T6.3 Unsaved-changes confirmation dialog on navigation away with dirty state (AC7) — reuse the pattern from Epic-2 Agent Identity tab if one exists (Story 2.2), else implement via router `beforeUnload`/`blocker` hook
- [ ] **T7 — Tests** (AC: all)
  - [ ] T7.1 `backend/tests/integration/test_workflows_rls.py` — raw SQL cross-tenant read empty (AC9)
  - [ ] T7.2 `backend/tests/integration/test_workflows_api.py` — POST 201 shape (AC1), GET round-trip, cross-tenant GET → 404 (AC4), list tenant-scoped (AC3), search/owner filter, non-builder POST → 403 (AC10)
  - [ ] T7.3 `backend/tests/integration/test_workflow_audit.py` — one `audit_trail` row per CRUD op with correct `type` (AC8)
  - [ ] T7.4 Frontend Vitest: list rendering + empty state (AC5), Definition tab validation (AC6), unsaved-changes dialog (AC7)
- [ ] **T8 — Green run + DoD evidence** (AC: all)
  - [ ] T8.1 `uv run alembic upgrade head`; `uv run pytest`; `uv run ruff check app tests alembic`; `npm run test` (frontend)
  - [ ] T8.2 Record test evidence (`file:line` PASSED) + production code reference (`file:line`) per AR-14 DoD

## Dev Notes

### Scope Boundaries — CRITICAL

**Story 3.1 is the Workflow data + CRUD foundation only. Do NOT implement:**
- Run lifecycle, `workflow_runs`/`tasks` tables, state machine — **Story 3.2**
- Orchestrator decomposition logic — **Story 3.3**
- Task dispatch/claim/aggregation — **Story 3.4**
- Escalation — **Story 3.6**
- Runs list / live Run view UI — **Stories 3.7/3.8**

Keep the `Workflow` model lean: `name`, `description`, `constraints`, `owner_id`, plus the two pre-provisioned config fields (`confidence_threshold`, `escalation_timeout_seconds` — cheap now, needed by 3.5/3.6, avoids a follow-up migration). Do NOT add `status`/`run_count` columns — run count is a computed join in 3.7, not a stored column (avoid denormalization without a proven need, YAGNI).

### Architecture Compliance

**AD-2 — RLS** (load-bearing for AC4, AC3, AC9): same pattern as `agents` table. `workflows` carries `tenant_id UUID NOT NULL`; policy on `tenant_id = current_setting('app.tenant_id')::uuid`, ENABLE + FORCE. `assume_app_role` (`app/core/deps.py:33`) must run first in tests (superuser bypasses RLS otherwise).

**AD-1 — Hexagonal**: domain logic in `orchestrator/service.py`; routes are thin adapters. Do NOT import `agent_builder` internals from `orchestrator` (not needed in this story — no Agent lookups yet, that's Story 3.3).

**AD-4 — Audit**: reuse `crud_audit_ids` from `app/core/deps.py` verbatim — do not invent a parallel convention. This is CRUD outside a Run, same category as Epic-2 Agent CRUD.

**AR-14**: UUID v7 via `app.core.ids.uuid7`; `timestamptz` UTC ISO 8601 ms; error shape `{error:{code,message,details,trace_id}}`; envelope `{data,error,meta}`; 50-line function ceiling; DoD = test `file:line` + green run AND production `file:line`.

### Epic-1/2 Contract Base (reuse, with file:line)

- **Auth/tenant context**: `AuthMiddleware` — `backend/app/core/auth.py:173-226`. Read principal from `request.state`.
- **Tenant-scoped session**: `get_tenant_session` — `backend/app/core/deps.py:51-66` (already promoted by Epic 2 Phase 0 — import from `core.deps`, NOT `tenant/routes.py`).
- **Audit convention**: `crud_audit_ids` — `backend/app/core/deps.py:69-84`.
- **Error/success envelope**: `backend/app/core/errors.py`.
- **Audit sink**: `AuditEntry` + `PostgresAuditSink.log()` — `backend/app/core/ports/audit.py:23-68`.
- **RLS migration reference**: latest Epic-2 example `backend/alembic/versions/82478b8e9fea_create_tools_rls.py` (check its exact DDL before writing T2.3 — more recent than the audit_trail migration).
- **Router registration pattern**: `backend/app/main.py:38-39` (`agents_router` inclusion) — add `workflows_router` the same way, additive only.

### File Structure Changes

```
backend/
├── alembic/
│   └── versions/
│       └── <rev>_create_workflows_rls.py     # NEW — down_revision resolved at execution time
├── app/
│   ├── main.py                                # UPDATED — additive: include workflows router
│   └── modules/
│       └── orchestrator/
│           ├── models.py                      # FILLED — Workflow
│           ├── service.py                     # FILLED — create/get/list/update + authz + audit
│           └── routes.py                      # FILLED — /workflows CRUD
└── tests/
    └── integration/
        ├── test_workflows_rls.py              # NEW — AC9
        ├── test_workflows_api.py              # NEW — AC1, AC3, AC4, AC10
        └── test_workflow_audit.py             # NEW — AC8

frontend/
└── src/
    └── routes/
        └── workflows/
            ├── index.tsx                       # NEW — /workflows list
            └── $id/
                └── index.tsx                   # NEW — /workflows/$id Definition tab
```

### Anti-Patterns to Avoid

1. Do NOT filter `tenant_id` in Python — RLS owns it (AD-2).
2. Do NOT return 403 for cross-tenant reads — 404 only (AC4).
3. Do NOT write `audit_trail` directly — route through `AuditPort` only (AD-4).
4. Do NOT trust `tenant_id`/`owner_id` from request body — derive from context/principal.
5. Do NOT add Run/Task columns to `workflows` now — those are Story 3.2's tables.
6. Do NOT hardcode a migration `down_revision` from this document — re-check `alembic heads` live (Epic 2 concurrency).
7. Do NOT exceed 50 lines per function (AR-14).

### Open Questions (carried to plan.md Open Questions)

- **Confidence threshold + escalation timeout placement**: this spec pre-provisions both columns on `workflows` in T1.3 to avoid a follow-up migration in Story 3.5/3.6. Confirm this is acceptable (minor schema-ahead-of-use tradeoff) vs. deferring the columns to when 3.5/3.6 actually need them (stricter YAGNI). Default recommendation: pre-provision (cheap, avoids migration churn on a table that's already RLS-wired).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.1 L847-868] ACs verbatim
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-2, AD-1, AD-4]
- [Source: ARCHITECTURE-SPINE/consistency-conventions.md]
- [Source: docs/prd.md#FR-7]
- [Source: backend/app/core/deps.py] shared session/audit-id helpers (Epic 2 Phase 0 output)
- [Source: _bmad-output/implementation-artifacts/2-1-agent-crud-identity-department-scoping.md] template story shape

## Change Log

- 2026-07-18: Story 3.1 spec authored by planner agent. Status: ready-for-dev.
