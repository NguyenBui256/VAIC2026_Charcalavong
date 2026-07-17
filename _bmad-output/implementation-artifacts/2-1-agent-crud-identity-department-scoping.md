---
baseline_commit: 4e2c5ad3cb823b8edb5f8ce6d0ea8b3d94a4fd1c
---

# Story 2.1: Agent CRUD, Identity & Department Scoping

Status: ready-for-dev

## Story

As a **user with builder role**,
I want **to create, read, update, and list Specialist Agents scoped to my Tenant and Department**,
so that **I can manage the Agent inventory that the Orchestrator will dispatch Tasks to**.

This is the **foundation story for Epic 2** (Specialist Agent Builder). It creates the `agents` table (RLS-protected per Story 1.2), the `agent_builder` module's models/service/routes, and the CRUD + scoping endpoints that Stories 2-2 (list/detail shell), 2-3 (model/prompt), 2-6 (tools), and 2-7 (API integrations) all build on. Epic 1 is DONE and is the stable contract base — reuse its auth, RLS, error/success envelope, and audit sink; do not re-implement them.

## Acceptance Criteria

1. **AC1 — POST /agents creates a scoped Agent (201)**: An authenticated builder in TenantA/DepartmentX posts `POST /agents` with `{name, department_id: <DeptX>, system_prompt}` and receives `201` with `{id (UUID v7), tenant_id, department_id, owner_id (= caller user_id), created_at, version}`. `tenant_id` is taken from `tenant_context` (never from the request body); `owner_id` is the caller's `user_id`; `version` starts at 1. (epics.md L670–L673)
2. **AC2 — GET /agents/{id} returns the same record**: `GET /agents/{id}` for the just-created id returns the identical record under the caller's tenant. (epics.md L673)
3. **AC3 — Cross-tenant read returns 404, not 403**: The Agent record is unreadable from TenantB — `GET /agents/{id}` under TenantB returns `404` (code `not_found`), never `403`, to avoid confirming existence. RLS makes the row invisible; the handler translates "no row" → `NotFoundError`. (epics.md L674, FR-1)
4. **AC4 — List is tenant-scoped**: `GET /agents` with no filter returns only Agents in the caller's Tenant (enforced by RLS, not a Python `WHERE tenant_id`). (epics.md L675–L676)
5. **AC5 — Department filter**: `GET /agents?department_id=<id>` returns only Agents in that Department within the caller's Tenant. Cross-tenant departments yield an empty list. (epics.md L677)
6. **AC6 — Authorization on PATCH**: A User who is **not** the `owner_id` **and** does not have builder role in the same Department attempts `PATCH /agents/{id}` → `403` with `code: "FORBIDDEN"`. The owner, or a builder in the Agent's Department, is allowed. (epics.md L678–L679)
7. **AC7 — DELETE is soft-delete only, same scoping**: `DELETE /agents/{id}` applies the same authorization as PATCH and performs a **soft delete** (sets `deleted_at`/`is_deleted`); it NEVER hard-deletes — preserving audit referential integrity. Soft-deleted Agents are excluded from GET/list by default. (epics.md L680)
8. **AC8 — Every CRUD op emits an audit entry**: `POST`/`PATCH`/`DELETE` each emit exactly one `audit.log()` entry with `type: "agent.created" | "agent.updated" | "agent.deleted"` respectively, routed through the `AuditPort` (`PostgresAuditSink`), never via direct SQL/ORM to `audit_trail`. (epics.md L681, FR-21, AD-4)
9. **AC9 — RLS applied to `agents`; direct SQL cross-tenant returns empty**: The `agents` table has RLS policies applied per Story 1.2 (ENABLE + FORCE + `tenant_id = current_setting('app.tenant_id')::uuid`). A raw `SELECT` under TenantA cannot read TenantB's Agent rows — result is empty. (epics.md L682, AD-2)
10. **AC10 — builder role required to create/mutate**: Creating (`POST`), updating (`PATCH`), and deleting (`DELETE`) an Agent requires the caller to have `role == "builder"`; a non-builder (e.g. operator, manager) receives `403 FORBIDDEN`. Read/list are available to any authenticated tenant user. (epics.md L664, L670 "Given … builder role")

## Tasks / Subtasks

- [ ] **T1 — `agents` model** (AC: #1, #7, #9)
  - [ ] T1.1 Fill `app/modules/agent_builder/models.py`: `Agent(Base)` SQLAlchemy 2.x `Mapped[...]` declarative, `__tablename__ = "agents"`
  - [ ] T1.2 Columns: `id` (`UUID(as_uuid=True)` PK, `default=uuid7`), `tenant_id UUID NOT NULL` (FK `tenants.id`, `ondelete="CASCADE"`), `department_id UUID NOT NULL` (FK `departments.id`, `ondelete="RESTRICT"`), `owner_id UUID NOT NULL` (FK `users.id`, `ondelete="RESTRICT"`)
  - [ ] T1.3 Domain columns: `name String(255) NOT NULL`, `system_prompt Text NOT NULL`, `status String(32) NOT NULL default "draft"` (values `draft|active`), `version Integer NOT NULL default 1`
  - [ ] T1.4 Soft-delete + timestamps: `is_deleted Boolean NOT NULL server_default "false"`, `deleted_at DateTime(timezone=True) nullable`, `created_at`/`updated_at DateTime(timezone=True) server_default=func.now()` (mirror `tenant/models.py:96-101`)
- [ ] **T2 — Alembic migration: create `agents` + RLS** (AC: #1, #7, #9)
  - [ ] T2.1 `cd backend && uv run alembic revision -m "create agents rls"` — `down_revision` MUST be `34cd8281e2b3` (current head, the audit_trail migration)
  - [ ] T2.2 `upgrade()`: `op.create_table("agents", ...)` mirroring the model; index `ix_agents_tenant_id` and `ix_agents_department_id`
  - [ ] T2.3 RLS DDL — copy the exact pattern from `alembic/versions/34cd8281e2b3_create_audit_trail_table.py:96-105`: `ALTER TABLE agents ENABLE ROW LEVEL SECURITY;` + `FORCE ROW LEVEL SECURITY;` + `CREATE POLICY tenant_isolation_policy ON agents USING (tenant_id = current_setting('app.tenant_id')::uuid) WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);`
  - [ ] T2.4 Grants: `GRANT SELECT, INSERT, UPDATE ON agents TO vaic_app;` and `REVOKE DELETE, TRUNCATE ON agents FROM vaic_app;` — the REVOKE **enforces soft-delete-only at the DB** (no hard delete possible; mirrors audit_trail's append-only stance). (AC7)
  - [ ] T2.5 `downgrade()`: drop policy, `NO FORCE` / `DISABLE` RLS, drop table (mirror the audit_trail downgrade)
  - [ ] T2.6 Idempotency: `uv run alembic upgrade head` twice — second run is a no-op
- [ ] **T3 — Service layer** (AC: #1–#8, #10)
  - [ ] T3.1 Fill `app/modules/agent_builder/service.py`. Domain functions read `tenant_context.get()` — NEVER accept `tenant_id` as an argument (consistency-conventions "Tenant context")
  - [ ] T3.2 `create_agent(session, *, owner_id, role, name, department_id, system_prompt) -> Agent` — assert `role == "builder"` (else `AuthorizationError(code="FORBIDDEN")`); INSERT with `owner_id` and `tenant_id` from context; RLS `WITH CHECK` guarantees the row lands in the caller's tenant
  - [ ] T3.3 `get_agent(session, agent_id) -> Agent` — `select(Agent).where(Agent.id == id, Agent.is_deleted.is_(False))`; if `None` raise `NotFoundError` (this yields the 404 for cross-tenant, since RLS returns no row — AC3)
  - [ ] T3.4 `list_agents(session, *, department_id=None) -> list[Agent]` — `select(Agent).where(Agent.is_deleted.is_(False))`, optional `department_id` filter only (NEVER a `tenant_id` filter — RLS owns that)
  - [ ] T3.5 `update_agent(session, agent_id, principal, **changes) -> Agent` and `soft_delete_agent(session, agent_id, principal) -> None` — both call a shared `_authorize_mutation(agent, principal)` guard
  - [ ] T3.6 `_authorize_mutation(agent, principal)`: allow if `principal.role == "builder"` AND (`agent.owner_id == principal.user_id` OR `agent.department_id == principal.department_id`); else raise `AuthorizationError(code="FORBIDDEN")` (AC6, AC10). Bump `version` on update; keep functions ≤ 50 lines (AR-14)
  - [ ] T3.7 `serialize_agent(agent) -> dict` — response payload: `{id, tenant_id, department_id, owner_id, name, system_prompt, status, version, created_at, updated_at}` (ISO 8601 ms)
- [ ] **T4 — Audit wiring** (AC: #8)
  - [ ] T4.1 After each successful commit, emit `audit.log(AuditEntry(...))` via `PostgresAuditSink` with `type` in `agent.created|agent.updated|agent.deleted`, `agent_id = str(agent.id)`, `input`/`output` capturing the change
  - [ ] T4.2 Resolve the `run_id`/`step_id` convention for non-Run CRUD audit — see **Open Question OQ-1** in Dev Notes. Recommended stopgap: `run_id = str(agent.id)`, `step_id = str(uuid7())`, `latency_ms = 0`, `model = ""`. Do NOT bypass `AuditPort` (AD-4)
- [ ] **T5 — Routes** (AC: #1–#7, #10)
  - [ ] T5.1 Fill `app/modules/agent_builder/routes.py`: `APIRouter(prefix="/agents", tags=["agents"])`; register in `app/main.py` via `app.include_router(agents_router)` (mirror `main.py:31`)
  - [ ] T5.2 Pydantic request schemas: `CreateAgentRequest{name, department_id, system_prompt}`, `UpdateAgentRequest{name?, system_prompt?, status?, department_id?}`
  - [ ] T5.3 Endpoints: `POST ""` (201), `GET "/{agent_id}"`, `GET ""` (`department_id` query param), `PATCH "/{agent_id}"`, `DELETE "/{agent_id}"` (204/200 soft-delete)
  - [ ] T5.4 Use the tenant-scoped session dependency + a `Principal` extracted from `request.state` (`user_id, tenant_id, department_id, role` set by `AuthMiddleware`, see `auth.py:216-219`). Success envelope `{data, error, meta}`; errors flow through the registered `DomainError` handlers (`errors.py:235-238`) — no manual `_err` needed for `DomainError` subclasses
  - [ ] T5.5 Session/dependency reuse — see **Open Question OQ-2**: `get_tenant_session` currently lives in `tenant/routes.py:101`. Prefer promoting it to a shared `app/core/deps.py` (Rule of Three now met: tenant + agent_builder + downstream 2-2/2-6) rather than importing across modules (AD-1 forbids reaching into another module's internals)
- [ ] **T6 — Tests** (AC: all)
  - [ ] T6.1 `tests/integration/conftest.py` — extend `seed_data` to seed a builder user, an operator user, and a second department in TenantA (reuse existing two-tenant fixtures from Story 1.2)
  - [ ] T6.2 `tests/integration/test_agents_rls.py` — raw SQL cross-tenant read returns empty (AC9); ORM cross-tenant read empty
  - [ ] T6.3 `tests/integration/test_agents_api.py` — POST 201 shape (AC1), GET round-trip (AC2), cross-tenant GET → 404 (AC3), list tenant-scoped (AC4), department filter (AC5), non-owner/non-builder PATCH → 403 FORBIDDEN (AC6), builder-in-dept PATCH allowed, DELETE soft-delete + excluded from list + row still present in DB (AC7), non-builder POST → 403 (AC10)
  - [ ] T6.4 `test_agent_audit.py` — assert one `audit_trail` row per CRUD op with the right `type` (AC8)
- [ ] **T7 — Green run + DoD evidence** (AC: all)
  - [ ] T7.1 `uv run alembic upgrade head` against running Postgres 18; `uv run pytest`; `uv run ruff check app tests alembic`
  - [ ] T7.2 Record test evidence (`file:line` PASSED + green output) and production code reference (`file:line`) per AR-14 Definition of Done

## Dev Notes

### Scope Boundaries — CRITICAL

**Story 2.1 is the Agent data + CRUD foundation. Do NOT implement:**
- Agent **list & detail UI**, tabs, dirty-state, search — **Story 2.2** (frontend)
- **Model/provider selection + prompt editor** tab and persistence of `{provider, model_name, parameters}` — **Story 2.3** (AD-7)
- **Knowledge Base** upload/storage/retrieval (`McpClientPort`, `department_id` scoping) — **Stories 2.4 / 2.5** (AD-11)
- **Per-Agent Tools** with input/output schemas — **Story 2.6**
- **API Integrations** — **Story 2.7**
- Orchestrator / Task dispatch consuming these Agents — **Epic 3**
- Any frontend changes — out of scope for 2.1

Keep the `Agent` model lean: identity fields only (`name`, `department_id`, `owner_id`, `system_prompt`, `status`, `version`). Do NOT pre-add `provider`/`model_name`/`tools` columns — those arrive with 2.3/2.6 and will get their own migrations. Avoid premature abstraction (consistency-conventions "No premature abstraction" / Rule of Three).

### Architecture Compliance

**AD-2 — Multi-tenant isolation via Postgres RLS** (load-bearing for AC3, AC4, AC9):
- `agents` carries `tenant_id UUID NOT NULL`; RLS policy `tenant_id = current_setting('app.tenant_id')::uuid` (USING + WITH CHECK), ENABLE **and** FORCE.
- RLS only bites under the `vaic_app` role (`[[rls-role-config-dependency]]`): in production the runtime DSN connects as `vaic_app`; in tests the superuser `vaic` must `SET LOCAL ROLE vaic_app` first — see `tenant/routes.py:83-98` (`_assume_app_role`). Without dropping to `vaic_app`, the superuser bypasses RLS even with FORCE.
- Application code NEVER filters `tenant_id` in Python. The `department_id` filter in `list_agents` is a domain filter, not a tenant filter — that's allowed. Cross-tenant "not found" (AC3) falls out of RLS returning zero rows → `NotFoundError` → 404.

**AD-1 — Hexagonal Modular Monolith**:
- Domain decisions live in `agent_builder/service.py`. Routes are a thin adapter (parse request → call service → envelope). No SQL/business rules in routes.
- Cross-module access goes through public service interfaces, never another module's internal models (relevant to OQ-2 — don't import `tenant/routes.py` internals; promote the shared session dep to `core`).

**AD-4 — Single audit sink, append-only, failure crashes the caller** (AC8):
- CRUD audit MUST go through `AuditPort.log()` (`core/ports/audit.py:63`) implemented by `PostgresAuditSink` (`core/adapters/audit_postgres.py:55`). It is the ONLY writer to `audit_trail`. If `log()` raises, the operation must fail — do not swallow (audit completeness outranks the write). Since `PostgresAuditSink` reads `tenant_context.get()` internally, ensure the contextvar is set (it is, on authenticated paths).

**AD-7 — Model Layer is a port (informational, NOT this story)**: the Agent record will store `{provider, model_name, parameters}` as *data* — but that is Story 2.3. 2.1 only lays the identity columns.

**AR-14 — Consistency Conventions** (relevant slices):
- Entity IDs UUID v7 via `app.core.ids.uuid7` (never autoincrement); timestamps `timestamptz` UTC ISO 8601 ms.
- Error shape `{error: {code, message, details, trace_id}}`; success envelope `{data, error, meta}` (`tenant/routes.py:55-72`).
- Function hard ceiling 50 lines. Definition of Done = test `file:line` + green output AND production `file:line`.
- File naming: Python `snake_case`, routes `kebab-case` (prefix `/agents`).

**AR-13 — Pinned Stack** (rely on this; no web research): Python 3.13, FastAPI 0.139.x, SQLAlchemy 2.x sync, Pydantic 2.x, Alembic latest, PostgreSQL 18, psycopg3. No new dependencies are needed for this story.

### Epic-1 Contract Base (what to reuse, with file:line)

- **Auth / tenant context (Story 1.3)**: `AuthMiddleware` decodes the JWT and populates `tenant_context` + `request.state.{user_id,tenant_id,department_id,role}` — `backend/app/core/auth.py:173-226`. Read the principal from `request.state`, not by re-decoding.
- **Tenant-scoped DB session (Story 1.3)**: `get_tenant_session` + `_assume_app_role` + `set_tenant_session_var` — `backend/app/modules/tenant/routes.py:83-117`. This is the pattern to reuse/promote (OQ-2).
- **Error / success envelope (Story 1.4)**: `DomainError` hierarchy + `register_error_handlers` — `backend/app/core/errors.py:75-238`. Raise `NotFoundError` (404), `AuthorizationError(code="FORBIDDEN")` (403), `ValidationError` (400); the handler renders the envelope. Success `_ok`/`_err` helpers in `tenant/routes.py:55-72`.
- **Audit sink (Story 1.5)**: `AuditEntry` + `PostgresAuditSink.log()` — `backend/app/core/ports/audit.py:23-68`, `backend/app/core/adapters/audit_postgres.py:71-134`.
- **Tenant models (Story 1.2)**: `Tenant`, `Department`, `User` (roles stored in `users.role String(64)`) — `backend/app/modules/tenant/models.py:30-101`.
- **RLS migration reference (Story 1.2 / 1.5)**: `agents` DDL should mirror `backend/alembic/versions/34cd8281e2b3_create_audit_trail_table.py:48-125`.

### File Structure Changes

```
backend/
├── alembic/
│   └── versions/
│       └── <rev>_create_agents_rls.py        # NEW — table + RLS + grants
├── app/
│   ├── core/
│   │   └── deps.py                            # NEW (recommended, OQ-2) — shared get_tenant_session + Principal
│   ├── main.py                                # UPDATED — include agents router
│   └── modules/
│       └── agent_builder/
│           ├── models.py                      # FILLED — Agent
│           ├── service.py                     # FILLED — create/get/list/update/soft_delete + authz + audit
│           └── routes.py                      # FILLED — /agents CRUD
└── tests/
    └── integration/
        ├── conftest.py                        # UPDATED — builder/operator users, 2nd department
        ├── test_agents_rls.py                 # NEW — AC9
        ├── test_agents_api.py                 # NEW — AC1–AC7, AC10
        └── test_agent_audit.py                # NEW — AC8
```

### Testing Requirements

- RLS + CRUD tests require a running Postgres (integration, not unit) — same discipline as Story 1.2's `tests/integration/`.
- Seed data via `AdminSessionLocal` (BYPASSRLS); assert via a `vaic_app`-role session (`SET LOCAL ROLE vaic_app` + `set_config('app.tenant_id', ...)`), reusing the `_assume_app_role`/`app_session` machinery from Story 1.2's conftest.
- Authorization matrix to cover explicitly: (owner+builder ✓), (non-owner but builder in same dept ✓), (builder in different dept, non-owner ✗ 403), (operator/manager ✗ 403 on create+mutate).
- Soft-delete assertion: after `DELETE`, the row still exists in `agents` (query with `is_deleted=true` under admin) but is absent from `GET`/list.
- Cross-tenant: TenantB `GET /agents/{tenantA_agent_id}` → 404 with `code: "not_found"` (NOT 403).
- Audit: exactly one `audit_trail` row per CRUD op, correct `type`.

### Anti-Patterns to Avoid

1. **Do NOT filter `tenant_id` in Python** — RLS owns tenant isolation (AD-2). Only `department_id` and `is_deleted` are legitimate domain filters.
2. **Do NOT return 403 for cross-tenant reads** — AC3 requires 404 to avoid confirming existence. Let RLS hide the row; raise `NotFoundError`.
3. **Do NOT hard-delete** — soft-delete via `is_deleted`/`deleted_at` (AC7). The migration REVOKEs `DELETE` from `vaic_app` so a stray hard delete fails at the DB.
4. **Do NOT write `audit_trail` directly** (raw SQL/ORM) — route through `AuditPort`/`PostgresAuditSink` only (AD-4). Do NOT swallow an audit failure.
5. **Do NOT trust `tenant_id`/`owner_id` from the request body** — derive `tenant_id` from `tenant_context.get()` and `owner_id` from `request.state.user_id`.
6. **Do NOT add model/tool/KB columns now** — out of scope; they get their own migrations in 2.3/2.6.
7. **Do NOT import `tenant/routes.py` internals from `agent_builder`** — AD-1. Promote the shared session dependency to `core` (OQ-2).
8. **Do NOT skip `FORCE ROW LEVEL SECURITY`** — the table owner bypasses RLS without it (Story 1.2 lesson).
9. **Do NOT exceed 50 lines per function** (AR-14) — split the authz guard, serialization, and audit emission into helpers.

### Open Questions (for the human — see Report)

- **OQ-1 (audit shape for non-Run CRUD)**: `AuditEntry` is Run-centric — `run_id` and `step_id` are required, non-null UUIDs (`ports/audit.py:42-49`; migration `NOT NULL`). Agent CRUD is not part of a Workflow Run, so there is no natural `run_id`. Stopgap in T4.2 uses `run_id = agent.id`, `step_id = uuid7()`. **Confirm** this convention or decide whether to relax the audit contract / add a dedicated admin-audit type. This affects every module's config-time audit (2.4 KB uploads hit the same question).
- **OQ-2 (shared tenant-session dependency)**: `get_tenant_session` lives in `tenant/routes.py`. Reusing across modules argues for promoting it to `app/core/deps.py` (Rule of Three now met). **Confirm** the promotion vs. duplicating the small dependency per module.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.1 L662–L682] ACs verbatim
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-2] RLS invariant (load-bearing)
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-1] Hexagonal modular monolith
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-4] Single audit sink, append-only
- [Source: ARCHITECTURE-SPINE/consistency-conventions.md] UUID v7, timestamptz, tenant context, envelopes, 50-line ceiling, DoD
- [Source: ARCHITECTURE-SPINE/stack.md] Pinned versions (AR-13)
- [Source: backend/app/core/auth.py:173-226] AuthMiddleware — principal on request.state
- [Source: backend/app/modules/tenant/routes.py:83-117] get_tenant_session / _assume_app_role pattern
- [Source: backend/app/core/errors.py:75-238] DomainError hierarchy + envelope handlers
- [Source: backend/app/core/ports/audit.py:23-68 + backend/app/core/adapters/audit_postgres.py:55-134] AuditPort + PostgresAuditSink
- [Source: backend/app/modules/tenant/models.py:30-101] Tenant/Department/User + role column
- [Source: backend/alembic/versions/34cd8281e2b3_create_audit_trail_table.py:48-125] RLS + grant DDL pattern to mirror
- [Source: _bmad-output/implementation-artifacts/1-2-multi-tenant-data-layer-postgres-rls.md] Story 1.2 (RLS base, [[rls-role-config-dependency]])

## Change Log

- 2026-07-17: Story 2.1 spec authored by story-context engine. Status: ready-for-dev.
