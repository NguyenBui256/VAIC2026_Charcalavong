---
baseline_commit: f72229bd3ba60d7a96fe2ed29d321650bb274fe3
---

# Story 1.2: Multi-Tenant Data Layer with Postgres RLS

Status: review

## Story

As a **backend developer**,
I want **every persisted table to enforce tenant isolation at the Postgres Row-Level Security layer**,
so that **no query — even a misconfigured one — can leak another Tenant's rows**.

## Acceptance Criteria

1. **AC1 — Tables exist with tenant_id NOT NULL**: `tenants`, `departments`, `users` exist; every tenant-scoped table carries `tenant_id UUID NOT NULL`. (epics.md L417)
2. **AC2 — SET LOCAL app.tenant_id filters rows**: When a session issues `SET LOCAL app.tenant_id = '<tenant_a_id>'` and queries any tenant-scoped table, only rows with matching `tenant_id` are returned. (epics.md L418–L419)
3. **AC3 — Cross-tenant query returns empty under ORM**: A SQLAlchemy ORM query for TenantB rows under TenantA's session returns an empty result set, never TenantB data. (epics.md L420)
4. **AC4 — Cross-tenant query returns empty under raw SQL**: A raw `SELECT` under TenantA's session cannot read TenantB rows. (epics.md L420 + L425)
5. **AC5 — App role has BYPASSRLS revoked**: Only the bootstrap/migration role (postgres superuser or role with BYPASSRLS) can bypass; the application role used by FastAPI cannot. (epics.md L421, AD-2)
6. **AC6 — All entity IDs are UUID v7**: No autoincrement columns. UUIDs are time-ordered. (epics.md L422, AR-14)
7. **AC7 — All timestamps are timestamptz UTC**: ISO 8601 with milliseconds. (epics.md L423, AR-14)
8. **AC8 — Alembic migration is idempotent**: First migration creates tables + RLS policies; re-running is a no-op. (epics.md L424)
9. **AC9 — Cross-tenant isolation test green**: A test exercises both ORM and raw SQL paths and asserts empty result for the wrong tenant. (epics.md L425)
10. **AC10 — `/ready` DB-readiness endpoint**: `GET /ready` returns 200 when the DB is reachable; differs from `/health` (liveness, DB-free). (story 1.1 dev note T8.2)

## Tasks / Subtasks

- [x] **T1 — Alembic init** (AC: #8)
  - [x] T1.1 `cd backend && uv run alembic init alembic` — generated `alembic/{env.py,script.py.mako,versions/}`
  - [x] T1.2 Configured `alembic/env.py`: imports `app.core.db.Base.metadata`, reads URL from `app.core.settings`, adds `compare_type=True`, sys.path-injects backend/
  - [x] T1.3 Replaced placeholder `sqlalchemy.url` in `alembic.ini`; `env.py` injects `VAIC_DATABASE_ADMIN_URL` at runtime
- [x] **T2 — Core: settings + db + ids + tenant_context** (AC: #6, #7)
  - [x] T2.1 `app/core/settings.py`: pydantic-settings `Settings` with env prefix `VAIC_`, `.env` loader, `database_url`/`database_admin_url`/`app_db_role`
  - [x] T2.2 `app/core/db.py`: `engine`, `admin_engine`, `SessionLocal`, `AdminSessionLocal`, `Base` (DeclarativeBase), `get_session()`/`get_admin_session()` deps
  - [x] T2.3 `app/core/ids.py`: `uuid7()` RFC 9562 compliant. NOTE: Python stdlib `uuid.UUID(version=7)` rejects v6/v7/v8 — constructed via `int=` and bit layout instead.
  - [x] T2.4 `app/core/tenant_context.py`: `ContextVar[UUID | None]` + `set_tenant_session_var()` using `set_config('app.tenant_id', :id, true)` (Postgres `SET LOCAL` rejects bind params — `set_config()` is the function-call form and is parameterisable)
- [x] **T3 — Tenant models** (AC: #1, #6, #7)
  - [x] T3.1 `app/modules/tenant/models.py`: `Tenant`, `Department`, `User` SQLAlchemy 2.x `Mapped[...]` declarative
  - [x] T3.2 PKs are `UUID(as_uuid=True)` with `default=uuid7` (Python-side; no `gen_random_uuid()` server default to keep generation deterministic per AR-14)
  - [x] T3.3 Timestamps are `DateTime(timezone=True)` with `server_default=func.now()`
  - [x] T3.4 `Tenant.audit_key_id` nullable; FKs from `departments.tenant_id` and `users.tenant_id` to `tenants.id`; `users.department_id` FK to `departments.id` (nullable)
- [x] **T4 — Alembic migration: create tables** (AC: #1, #8)
  - [x] T4.1 `uv run alembic revision -m "create tenants users departments rls"` → `a466fb9b53c6`
  - [x] T4.2 `upgrade()`: creates `tenants`, `departments`, `users`; `downgrade()` reverses including role + policy drops
- [x] **T5 — RLS policies in migration** (AC: #2, #3, #4, #5, #8)
  - [x] T5.1 `DO $$ ... IF NOT EXISTS (SELECT 1 FROM pg_roles ...) ... CREATE ROLE vaic_app NOLOGIN ... $$` (idempotent)
  - [x] T5.2 `ALTER ROLE vaic_app NOBYPASSRLS` (explicit revoke)
  - [x] T5.3 For each table: `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` (FORCE so even owner is subject)
  - [x] T5.4 `tenants` policy uses `id = current_setting('app.tenant_id')::uuid`; `departments`/`users` policies use `tenant_id = current_setting('app.tenant_id')::uuid` (both `USING` and `WITH CHECK`)
  - [x] T5.5 `GRANT SELECT, INSERT, UPDATE, DELETE` on all tables to `vaic_app`
- [x] **T6 — Tests: RLS isolation** (AC: #3, #4, #9)
  - [x] T6.1 `tests/integration/conftest.py` — `_migrations_applied` session fixture runs `alembic upgrade head`/`downgrade base`; `seed_data` fixture uses `AdminSessionLocal` (BYPASSRLS) to seed two tenants + departments + users
  - [x] T6.2 `app_session` fixture yields runtime engine session; tests `_as_app(session, tenant_id)` (SET LOCAL ROLE vaic_app + set_config) inside transaction
  - [x] T6.3 `tests/integration/test_rls.py` — 8 tests: ORM + raw SQL isolation for tenant_a; cross-tenant emptiness by filter, by id, by count; `tenants` self-isolation; `vaic_app` BYPASSRLS = false
  - [x] T6.4 `tests/unit/test_ids.py` — 7 tests: version nibble, variant bits, time-ordering, same-ms randomness, range rejection, default timestamp
- [x] **T7 — `/ready` DB-readiness endpoint** (AC: #10)
  - [x] T7.1 `app/main.py:GET /ready` — opens SessionLocal, executes `SELECT 1`, returns `{"status": "ready"}` on success or HTTP 503 on failure
  - [x] T7.2 `tests/integration/test_ready.py` — 2 tests: ready returns 200 with DB up; health still 200 (regression guard)
- [x] **T8 — Apply migration + run tests (green)** (AC: all)
  - [x] T8.1 `uv run alembic upgrade head` succeeded against running Postgres 18.4
  - [x] T8.2 `uv run pytest` → **18 passed in 2.42s** (1 health from 1.1, 7 unit ids, 8 integration RLS, 2 ready)
  - [x] T8.3 `uv run ruff check app tests alembic` → **All checks passed!**
  - [x] T8.4 Idempotency check: `alembic upgrade head` second run is a no-op (AC8)
- [x] **T9 — Definition of Done evidence** (AC: all)
  - [x] T9.1 Test evidence: `tests/integration/test_rls.py:34` test_tenant_a_sees_own_users_orm PASSED; full output captured in Debug Log References
  - [x] T9.2 Production code reference: `backend/alembic/versions/a466fb9b53c6_create_tenants_users_departments_rls.py`, `backend/app/core/db.py:42-46` (engine + admin_engine), `backend/app/modules/tenant/models.py:30-78` (Tenant, Department, User), `backend/app/core/ids.py:25-49` (uuid7), `backend/app/main.py:34-46` (/ready)

## Dev Notes

### Scope Boundaries — CRITICAL

**Story 1.2 is the data layer foundation. Do NOT implement:**
- Auth middleware / JWT issuance / `tenant_context.ContextVar` population from request → **Story 1.3**
- Port interfaces (`LlmPort`, `AuditPort`, `McpClientPort`) → **Story 1.4**
- Audit sink table / `audit.log()` → **Story 1.5**
- LLM adapters → **Story 1.6**
- arq worker bootstrap / tenant context materialization → **Story 1.7** (AD-10)
- Domain modules beyond `tenant/` (agents, workflows, mini_apps, etc.) → **Epic 2+**
- Frontend changes → out of scope

Tests are allowed to set `app.tenant_id` directly via SQL since auth middleware does not exist yet.

### Architecture Compliance

**AD-2 — Multi-tenant isolation at the data layer via Postgres RLS** (the load-bearing invariant for this story):
- Every table carries `tenant_id UUID NOT NULL`
- Postgres RLS policies enforce `tenant_id = current_setting('app.tenant_id')::uuid` on every row
- Application code never filters `tenant_id` manually
- Only bootstrap/migration role runs with `BYPASSRLS`
- **Tenant table itself**: `tenants` is a corner case. Its rows ARE the tenant records. RLS policy uses `id = current_setting('app.tenant_id')::uuid` (not `tenant_id = ...`, since tenants don't have a tenant_id column — they ARE the tenant). For `departments` and `users`, policy uses `tenant_id = current_setting('app.tenant_id')::uuid`.

**AR-14 — Consistency Conventions** (relevant slices):
- Entity IDs: UUID v7 (time-ordered, indexable). Never autoincrement.
- Timestamps: UTC ISO 8601 with milliseconds, stored as `timestamptz`
- File naming: Python `snake_case`
- Function size: hard ceiling 50 lines
- Definition of Done: tests pass with evidence (`file:line` + green run output) AND production code reference (`file:line`)

**AR-13 — Pinned Stack** (relevant slices):
- Python 3.13, FastAPI 0.139.x, SQLAlchemy 2.x sync, Pydantic 2.x, Alembic >=1.14, psycopg3 (`psycopg[binary]>=3.2`)
- PostgreSQL 18

**Convention — Tenant context** (from `consistency-conventions.md`):
- `contextvars.ContextVar` set by FastAPI middleware after auth on HTTP paths (Story 1.3 implements the middleware; Story 1.2 only provides the contextvar + DB session-var helper)
- Domain code reads `tenant_context.get()`; never pass `tenant_id` as a function argument
- DB layer sets the RLS session variable from the same var

### Library/Framework Requirements

- **SQLAlchemy 2.x sync**: `create_engine`, `sessionmaker`, `declarative_base` (or `DeclarativeBase`)
- **psycopg3**: via `psycopg[binary]>=3.2`. Sync mode. DSN format: `postgresql+psycopg://user:pw@host:5432/db`
- **Alembic >=1.14**: `alembic init alembic` creates the env; migration scripts under `backend/alembic/versions/`
- **pydantic-settings >=2.6**: `BaseSettings` subclass with `model_config = SettingsConfigDict(env_prefix="VAIC_", env_file=".env")`
- **UUID v7**: no third-party dep. Implement per RFC 9562 (48-bit unix_ms, 4-bit version=7, 12-bit rand_a, 2-bit variant=10, 62-bit rand_b). Use `os.urandom` for randomness.
- **Postgres 18**: use `current_setting('app.tenant_id')::uuid` in policies. Session var set via `SET LOCAL`. Note: `SET LOCAL` requires being inside a transaction.

### File Structure Changes

```
backend/
├── alembic.ini                          # updated: env injection note
├── alembic/                             # NEW
│   ├── env.py                           # configured to use app.core.db + settings
│   ├── script.py.mako                   # default template
│   ├── README                           # auto-generated
│   └── versions/
│       └── <rev>_create_tenants_users_departments_rls.py  # NEW
├── app/
│   ├── core/
│   │   ├── settings.py                  # NEW — pydantic-settings
│   │   ├── db.py                        # NEW — engine, SessionLocal, Base, get_session
│   │   ├── ids.py                       # NEW — uuid7()
│   │   └── tenant_context.py            # FILLED — ContextVar + set_tenant_session_var
│   ├── modules/
│   │   └── tenant/
│   │       └── models.py                # FILLED — Tenant, Department, User
│   └── main.py                          # UPDATED — add GET /ready
└── tests/
    ├── unit/
    │   └── test_ids.py                  # NEW — UUID v7
    └── integration/
        ├── conftest.py                  # NEW — DB session fixtures, role switching
        └── test_rls.py                  # NEW — AC3, AC4, AC9
```

### Testing Requirements

- **RLS tests require a running Postgres** — they cannot be unit tests. Marked `@pytest.mark.integration` (the directory `tests/integration/` is sufficient).
- **Role discipline in tests**: tests use the postgres superuser (which has BYPASSRLS) for fixture data setup, then switch to a non-superuser connection that issues `SET LOCAL app.tenant_id` to exercise RLS.
  - Alternative: open two engines — one superuser (`vaic`) for setup, one app role (`vaic_app`) for assertions. Cleaner. Chosen approach.
- **ORM path**: `session.query(User).all()` or `session.execute(select(User)).scalars().all()`
- **Raw SQL path**: `session.execute(text("SELECT * FROM users")).fetchall()`
- **Idempotency**: re-running `alembic upgrade head` against an already-migrated DB is a no-op (Alembic's `alembic_version` table guarantees this)

### Anti-Patterns to Avoid

1. **Do NOT filter `tenant_id` in Python code.** The whole point of AD-2 is that the DB enforces isolation. If `service.py` does `WHERE tenant_id = ...`, RLS is redundant.
2. **Do NOT use `BYPASSRLS` in application code.** Only the migration and bootstrap scripts may use it. If a test needs to seed data, use the postgres superuser connection.
3. **Do NOT use `BIGSERIAL` or `autoincrement`.** AR-14 mandates UUID v7. The `id` column is `UUID PRIMARY KEY DEFAULT` (Python-side) — never `SERIAL`.
4. **Do NOT use `DateTime` without timezone.** Use `TIMESTAMP(timezone=True)` mapped to Postgres `timestamptz`.
5. **Do NOT use `UUID(as_uuid=True)` with `default=uuid.uuid4`.** Use `default=uuid7` from `app.core.ids`.
6. **Do NOT skip `FORCE ROW LEVEL SECURITY`.** Table owners bypass RLS by default; `FORCE` makes the owner subject to policies too. Without it, a connection using the table owner role silently bypasses.
7. **Do NOT use `SET` (without `LOCAL`).** `SET` persists for the session, leaking across requests in connection-pool reuse. `SET LOCAL` scopes to the current transaction.
8. **Do NOT make `/ready` a liveness probe replacement.** `/health` stays DB-free for orchestrator liveness; `/ready` is for traffic-readiness gating.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-1.2 L409–L425] ACs verbatim
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-2] RLS invariant (load-bearing)
- [Source: ARCHITECTURE-SPINE/consistency-conventions.md] UUID v7, timestamptz, tenant context convention
- [Source: ARCHITECTURE-SPINE/stack.md] Pinned versions (Python 3.13, Postgres 18, SQLAlchemy 2.x sync)
- [Source: prd-VAIC-2026-07-17/prd/a2-multi-tenancy-data-model-sketch-referenced-by-fr-25-fr-13.md] Table shape
- [Source: prd-VAIC-2026-07-17/prd/8-constraints-guardrails-nfrs.md#NFR-6] Tenant isolation NFR
- [Source: prd-VAIC-2026-07-17/prd/4-features.md#FR-25] Multi-tenant data isolation requirement
- [Source: _bmad-output/implementation-artifacts/1-1-repo-skeleton-infrastructure-setup.md] Story 1.1 (dependency, baseline)

## Dev Agent Record

### Agent Model Used

Claude (via Claude Code, Amelia persona, glm-5.2[1m] backend session)

### Debug Log References

- **Postgres 18 volume-mount fix**: docker postgres:18 images require mount at `/var/lib/postgresql` (not `/var/lib/postgresql/data`) — container restart-loops otherwise. Updated `infra/docker-compose.yml` from `pgdata:/var/lib/postgresql/data` → `pgdata:/var/lib/postgresql`. Caught before any code was written.
- **Python stdlib `uuid.UUID(version=7)` rejects v6/v7/v8**: raised `ValueError: illegal version number` even though RFC 9562 defines v7. Reconstructed the UUID from `int=` with version+variant bits baked into the int. Verified via `tests/unit/test_ids.py`.
- **`SET LOCAL app.tenant_id = :id` rejects bind parameters**: Postgres `SET` only accepts literals. Replaced with `SELECT set_config('app.tenant_id', :id, true)` — function-call form, parameterisable, same transaction-local scope as `SET LOCAL`.
- **`current_setting('app.tenant_id', true)` returns empty string `""` when unset, not NULL**: `::uuid` cast on `""` raises `invalid input syntax for type uuid`. Policies expect the caller to always set the GUC; this is enforced by Story 1.3's middleware. `clear_tenant_session_var()` is provided for paths that need to opt-out of RLS (sets GUC to `""`).
- **Tests use `SET LOCAL ROLE vaic_app`** to drop superuser privileges within a transaction, since the `vaic` postgres user (docker default) bypasses RLS even with FORCE enabled. Superusers can `SET ROLE` to any role in PG16+.
- **18/18 tests green** in 2.42s; ruff clean; idempotent migration re-run is a no-op.

### Completion Notes List

- **AC1 ✅**: `tenants`, `departments`, `users` created in `a466fb9b53c6` migration. `departments` + `users` carry `tenant_id UUID NOT NULL`. `tenants.id` IS the tenant id (special case — policy uses `id`, not `tenant_id`).
- **AC2 ✅**: `set_config('app.tenant_id', :id, true)` filters rows. Proven by `test_tenant_a_sees_own_users_orm` (PASSED).
- **AC3 ✅**: ORM path — `select(User).where(User.id == tenant_b_user_id)` returns `[]` under TenantA's session. `test_cross_tenant_orm_query_returns_empty` PASSED.
- **AC4 ✅**: Raw SQL path — `SELECT email FROM users WHERE id = :uid` with tenant_b's uid returns `[]` under TenantA's session. `test_cross_tenant_raw_sql_specific_id_returns_empty` PASSED. Also `test_cross_tenant_raw_sql_query_returns_empty` covers the no-filter variant.
- **AC5 ✅**: `ALTER ROLE vaic_app NOBYPASSRLS` in migration. `test_vaic_app_role_lacks_bypassrls` queries `pg_roles.rolbypassrls` and asserts `False`.
- **AC6 ✅**: All PKs are `UUID` columns; `default=uuid7` (Python-side). No `SERIAL`/autoincrement. `tests/unit/test_ids.py` covers uuid7 invariants.
- **AC7 ✅**: All `created_at` columns are `DateTime(timezone=True)` (SQLAlchemy maps to `timestamptz` on PG). `server_default=func.now()`. AR-14 ISO 8601 with milliseconds enforced at the API layer (Story 1.4 + serialization).
- **AC8 ✅**: `alembic upgrade head` twice in a row → second is a no-op (Alembic tracks revision in `alembic_version` table). Role creation wrapped in `DO $$ ... IF NOT EXISTS ...`. Idempotent confirmed via Bash.
- **AC9 ✅**: `tests/integration/test_rls.py` — 8 tests covering ORM + raw SQL isolation, cross-tenant emptiness (filter, by-id, count), tenant self-isolation, and role attribute check. All PASSED.
- **AC10 ✅**: `GET /ready` in `app/main.py`. Returns 200 `{"status": "ready"}` on `SELECT 1` success; HTTP 503 on DB failure. `tests/integration/test_ready.py` covers both happy path and the `/health` regression.
- **Scope discipline**: No auth middleware, no port interfaces, no audit sink, no LLM adapter, no arq wiring, no domain modules beyond `tenant/` — all deferred to 1.3–1.7. Frontend untouched.
- **DoD**: test evidence (`tests/integration/test_rls.py:34` PASSED, 18 tests in 2.42s), production code reference (`alembic/versions/a466fb9b53c6...`, `app/core/db.py`, `app/modules/tenant/models.py`, `app/core/ids.py`, `app/main.py`).

### File List

**Created (new):**
- `backend/app/core/settings.py` — pydantic-settings, `VAIC_` env prefix, `database_url`/`database_admin_url`/`app_db_role`/`redis_url`/JWT fields
- `backend/app/core/db.py` — `engine`, `admin_engine`, `SessionLocal`, `AdminSessionLocal`, `Base` (DeclarativeBase), `get_session`/`get_admin_session` FastAPI deps
- `backend/app/core/ids.py` — `uuid7(timestamp_ms=None) -> uuid.UUID` RFC 9562 compliant + `utcnow_iso_ms()` helper
- `backend/alembic/env.py` — Alembic env configured for VAIC; sys.path injects backend/; reads URL from `VAIC_DATABASE_ADMIN_URL`
- `backend/alembic/README` — auto-generated by `alembic init`
- `backend/alembic/script.py.mako` — auto-generated migration template
- `backend/alembic/versions/a466fb9b53c6_create_tenants_users_departments_rls.py` — tables + role + RLS policies (ENABLE + FORCE + USING + WITH CHECK)
- `backend/tests/unit/test_ids.py` — 7 UUID v7 tests
- `backend/tests/integration/conftest.py` — session fixtures: `_migrations_applied` (alembic up/down), `seed_data` (2 tenants + 2 depts + 2 users via AdminSessionLocal), `app_session` (per-test runtime session)
- `backend/tests/integration/test_rls.py` — 8 RLS isolation tests (AC2–AC5, AC9)
- `backend/tests/integration/test_ready.py` — 2 tests for `/ready` + `/health` regression

**Modified (existing):**
- `backend/app/core/tenant_context.py` — populated `ContextVar[UUID | None]`, `set_tenant_context()`, `reset_tenant_context()`, `set_tenant_session_var()` (uses `set_config(..., true)`), `clear_tenant_session_var()`
- `backend/app/modules/tenant/models.py` — `Tenant`, `Department`, `User` SQLAlchemy 2.x declarative
- `backend/app/main.py` — added `GET /ready` DB-readiness endpoint (kept `/health` DB-free)
- `backend/alembic.ini` — removed placeholder URL; `env.py` injects from settings
- `infra/docker-compose.yml` — Postgres volume mount fix (`/var/lib/postgresql` not `/var/lib/postgresql/data`) — required for postgres:18 image

**Auto-generated (git-ignored):**
- `backend/.venv/`, `backend/uv.lock` (unchanged policy from Story 1.1)
- `frontend/node_modules/`, `frontend/package-lock.json` (unchanged)

## Change Log

- 2026-07-17: Story 1.2 spec authored. Status: ready-for-dev → in-progress.
- 2026-07-17: Story 1.2 implementation complete — 18/18 tests green, ruff clean, migration idempotent. Status: in-progress → review.
