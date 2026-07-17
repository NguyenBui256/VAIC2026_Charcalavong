---
baseline_commit: 9ad9a118ddae0027006eb8a296792fe98d4282c9
---

# Story 1.3: Auth & Tenant Context Middleware

Status: done

## Story

As a **backend developer**,
I want **FastAPI middleware that authenticates requests and sets the tenant contextvar from the JWT**,
so that **downstream domain code can read `tenant_context.get()` without passing `tenant_id` as a function argument**.

## Acceptance Criteria

(Sourced verbatim from `_bmad-output/planning-artifacts/epics.md` L435–L447, expanded with test coverage notes.)

1. **AC1 — Valid login returns JWT with required claims**: `POST /auth/login` with valid email+password returns a JWT carrying `user_id`, `tenant_id`, `department_id`, `role`. (epics.md L435–L437)
2. **AC2 — JWT expires per configurable TTL**: `exp - iat == settings.jwt_ttl_minutes * 60`. (epics.md L438)
3. **AC3 — Protected endpoint without Authorization → 401 envelope**: `{error: {code: "UNAUTHENTICATED", message, details, trace_id}}`. (epics.md L439–L443)
4. **AC4 — Protected endpoint with expired/invalid JWT → 401 envelope**: same shape as AC3. (epics.md L444)
5. **AC5 — Protected endpoint with valid JWT → handler sees `tenant_context.get()` populated**: `GET /auth/me` returns the user's profile sourced from the tenant-scoped session. (epics.md L440–L441)
6. **AC6 — Middleware sets the RLS session var on the DB connection**: querying a tenant-scoped table from inside a protected handler returns only same-tenant rows. (epics.md L441, AD-2, AD-10)
7. **AC7 — Password hashing uses Argon2**: `hash_password(plain).startswith("$argon2")`. (epics.md L435)
8. **AC8 — `tenant_context` is reset between requests**: ContextVar default is `None` after a request completes. (Story 1.2 invariant — Story 1.3 enforces it.)
9. **AC9 — Deactivated user → 401 with `code: "ACCOUNT_DEACTIVATED"`**: `is_active=false` blocks login. (epics.md L444–L445)
10. **AC10 — `GET /auth/me` returns the User profile**: `{id, email, tenant_id, department_id, role}`. (epics.md L446)
11. **AC11 — Two JWTs never cross tenant boundaries**: alice (TenantA) and bob (TenantB) tokens cannot see each other's users. (epics.md L447)

## Tasks / Subtasks

- [x] **T1 — Migration: add users columns** (AC: #7, #9)
  - [x] T1.1 `alembic revision -m "add users password hash is_active updated_at"` → `ec784b72f20c`
  - [x] T1.2 `upgrade()`: adds `password_hash VARCHAR(255) NULL`, `is_active BOOLEAN NOT NULL DEFAULT true`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - [x] T1.3 `upgrade()`: creates `users_set_updated_at()` plpgsql function + `BEFORE UPDATE` trigger
  - [x] T1.4 `downgrade()`: drops trigger, function, columns (in that order)
- [x] **T2 — Model update** (AC: #7, #9)
  - [x] T2.1 `app/modules/tenant/models.py:User`: added `password_hash: Mapped[str | None]`, `is_active: Mapped[bool]`, `updated_at: Mapped[datetime]`
- [x] **T3 — Auth core** (AC: #1, #2, #3, #4, #7, #8)
  - [x] T3.1 `app/core/auth.py`: `hash_password`/`verify_password` via passlib[argon2]
  - [x] T3.2 `app/core/auth.py`: `create_access_token(claims, ttl_minutes)` adds `iat`+`exp`, encodes HS256 via python-jose
  - [x] T3.3 `app/core/auth.py`: `decode_access_token(token)` verifies signature + exp; raises `AuthError` on any failure
  - [x] T3.4 `app/core/auth.py:AuthError(Exception)` — minimal `{code, message, details, http_status}` until Story 1.4's shared envelope lands
  - [x] T3.5 `app/core/auth.py:AuthMiddleware(BaseHTTPMiddleware)` — ASGI middleware: extracts Bearer token, decodes JWT, sets `tenant_context.ContextVar`, resets on teardown
  - [x] T3.6 `app/core/auth.py:PUBLIC_PATHS` — `/health`, `/ready`, `/auth/login`, `/auth/refresh`, `/openapi.json`, `/docs`, `/redoc`
  - [x] T3.7 Error envelope shape: `{error: {code, message, details, trace_id}}` per AR-14
- [x] **T4 — Service layer** (AC: #1, #9, #10)
  - [x] T4.1 `app/modules/tenant/service.py:hash_password` re-export
  - [x] T4.2 `app/modules/tenant/service.py:authenticate(session, email, password)` — SELECT user (via AdminSessionLocal/BYPASSRLS), verify Argon2, raise `AuthError(UNAUTHENTICATED)` or `AuthError(ACCOUNT_DEACTIVATED)`
  - [x] T4.3 `app/modules/tenant/service.py:issue_token(user)` — build claims, call `create_access_token`
  - [x] T4.4 `app/modules/tenant/service.py:user_profile(user)` — serialize to response shape (no `password_hash`)
  - [x] T4.5 `app/modules/tenant/service.py:list_tenant_users(session)` — list under current RLS context (no Python-side filter)
- [x] **T5 — HTTP routes** (AC: #1, #3, #5, #6, #10)
  - [x] T5.1 `app/modules/tenant/routes.py:POST /auth/login` — public; uses `AdminSessionLocal` to look up user before tenant is known
  - [x] T5.2 `app/modules/tenant/routes.py:POST /auth/refresh` — public; re-issues JWT from valid claims
  - [x] T5.3 `app/modules/tenant/routes.py:GET /auth/me` — protected; reads `request.state.user_id` set by middleware; uses tenant-scoped session
  - [x] T5.4 `app/modules/tenant/routes.py:GET /auth/users` — protected; proves RLS isolation (AC6)
  - [x] T5.5 `app/modules/tenant/routes.py:get_tenant_session()` — FastAPI dep: opens runtime session, `SET LOCAL ROLE vaic_app` + `set_config('app.tenant_id', ...)`; enforces RLS even when runtime DSN is superuser
  - [x] T5.6 Success envelope `{data, error: null, meta: {}}` per AR-14
- [x] **T6 — Wire up middleware + router** (AC: all)
  - [x] T6.1 `app/main.py`: `from app.core.auth import AuthMiddleware` + `app.add_middleware(AuthMiddleware)`
  - [x] T6.2 `app/main.py`: `from app.modules.tenant.routes import router as tenant_router` + `app.include_router(tenant_router)`
  - [x] T6.3 Preserved Story 1.1's `/health` and Story 1.2's `/ready` untouched
- [x] **T7 — Tests (TDD)** (AC: all)
  - [x] T7.1 RED: wrote 13 tests in `tests/integration/test_auth.py`; confirmed they failed with `ImportError` before implementation
  - [x] T7.2 GREEN: implemented auth.py / service.py / routes.py until all 13 passed
  - [x] T7.3 `tests/integration/conftest.py`: added `auth_seed` (session-scoped; updates `password_hash` on seeded users) and `api_client` (function-scoped; resets `tenant_context` before/after) fixtures. Preserved Story 1.2's `_migrations_applied` and `seed_data`.
- [x] **T8 — Apply migration + run tests (green)** (AC: all)
  - [x] T8.1 `uv run alembic upgrade head` succeeded against `vaic_13`
  - [x] T8.2 `uv run pytest` → **31 passed in 3.20s** (1 health, 2 ready, 8 RLS from 1.2; 7 unit ids; 13 auth from 1.3)
  - [x] T8.3 `uv run ruff check app tests alembic` → All checks passed
  - [x] T8.4 Idempotency: `alembic upgrade head` twice → second is a no-op (AC from 1.2 carried forward)
- [x] **T9 — Definition of Done evidence** (AC: all)
  - [x] T9.1 Test evidence: `tests/integration/test_auth.py:62 test_login_returns_jwt_with_required_claims PASSED`; full output in Debug Log
  - [x] T9.2 Production code reference: `backend/app/core/auth.py` (middleware + JWT + Argon2), `backend/app/modules/tenant/routes.py` (HTTP endpoints), `backend/app/modules/tenant/service.py` (domain logic), `backend/alembic/versions/ec784b72f20c_add_users_password_hash_is_active_.py` (migration)

## Dev Notes

### Scope Boundaries — CRITICAL

**Story 1.3 is auth middleware + JWT issuance + tenant contextvar population. Do NOT implement:**
- Shared error envelope module (`app/core/errors.py`) → **Story 1.4** (parallel). 1.3 defines a minimal `AuthError` in `app/core/auth.py`; the coordinator reconciles at merge.
- Port interfaces → **Story 1.4**
- Audit sink → **Story 1.5**
- LLM adapters → **Story 1.6**
- arq worker tenant context re-set → **Story 1.7** (AD-10)
- Frontend → out of scope

### Architecture Compliance

- **AD-2 (RLS)**: The middleware sets `tenant_context.ContextVar`. Routes convert it to `app.tenant_id` via `set_tenant_session_var()` on the request's DB session. RLS policies from Story 1.2 enforce isolation. No Python-side `WHERE tenant_id = ...` filter.
- **AD-10 (tenant context materialization)**: Story 1.3 implements the HTTP-path half. The arq-worker half (deserialize `tenant_id` from job kwargs) is Story 1.7.
- **AR-14 (error envelope + success envelope)**: every response — success or failure — uses `{data, error, meta}` / `{error: {code, message, details, trace_id}}`.
- **AR-14 (function size ≤ 50 lines)**: longest function is `dispatch()` in `AuthMiddleware` at ~30 lines.

### Key Design Decisions

1. **Login uses `AdminSessionLocal` (BYPASSRLS)**: the user's tenant is unknown until AFTER the lookup — RLS would block the SELECT. This is the one path that legitimately bypasses RLS, and only to authenticate.
2. **`SET LOCAL ROLE vaic_app` on runtime sessions**: in tests the runtime DSN connects via the superuser `vaic`. Production should connect via a non-superuser role directly. `routes._assume_app_role(session)` checks `settings.app_db_role` and issues `SET LOCAL ROLE` if non-empty, making tests exercise real RLS while keeping production code identical.
3. **Minimal `AuthError` until Story 1.4 lands**: defined in `app/core/auth.py` with `.code`, `.message`, `.details`, `.http_status`. The coordinator reconciles with Story 1.4's `DomainError`/`AuthenticationError` at merge time.
4. **`trace_id` is a fresh UUID per request**: generated in `AuthMiddleware.dispatch` and stashed on `request.state.trace_id`. Not yet threaded through arq jobs (Story 1.7).

### Library/Framework Requirements

- **passlib[argon2] >=1.7**: `CryptContext(schemes=["argon2"])`. Hashes start with `$argon2id$`.
- **python-jose[cryptography] >=3.3**: `jwt.encode/decode` with HS256.
- **Starlette BaseHTTPMiddleware**: cleanest ASGI middleware pattern for FastAPI 0.139.

### Anti-Patterns Avoided

1. **No `tenant_id` as a function argument** — domain code reads `tenant_context.get()` exclusively.
2. **No Python-side `WHERE tenant_id = ...` filter** — RLS does it.
3. **No password storage in plaintext** — Argon2 only; `verify_password` returns False on any error.
4. **No JWT in URL query strings** — `Authorization: Bearer <token>` header only.
5. **No shared mutable state between requests** — `tenant_context` is a `ContextVar` and is explicitly reset in a `finally` block.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story-1.3` L427–L447] ACs verbatim
- [Source: `ARCHITECTURE-SPINE/invariants-rules.md#AD-2`] RLS invariant
- [Source: `ARCHITECTURE-SPINE/invariants-rules.md#AD-10`] Tenant context materialization (HTTP half)
- [Source: `ARCHITECTURE-SPINE/consistency-conventions.md`] Error envelope shape, tenant context convention
- [Source: `_bmad-output/implementation-artifacts/1-2-multi-tenant-data-layer-postgres-rls.md`] Baseline (RLS + contextvar + session-var helper)
- [Source: `backend/pyproject.toml`] Pinned `passlib[argon2]>=1.7`, `python-jose[cryptography]>=3.3`

## Dev Agent Record

### Agent Model Used

Claude (via Claude Code, glm-5.2[1m] backend session).

### Debug Log References

- **RLS bypass via superuser connection**: First GREEN run had 11/13 tests passing; the 2 RLS-isolation tests failed because `bob@tenantb.example` was visible under alice's token. Root cause: the runtime DSN connects via `vaic` (the docker postgres superuser), which bypasses RLS implicitly — same issue Story 1.2's tests solved with `SET LOCAL ROLE vaic_app`. Fix: added `routes._assume_app_role(session)` which issues `SET LOCAL ROLE vaic_app` when `settings.app_db_role` is set. Production should connect via `vaic_app` directly (no SET ROLE needed).
- **Migration `DROP ROLE vaic_app` fails at teardown**: pre-existing issue. `downgrade()` in `a466fb9b53c6` tries to drop the shared `vaic_app` role, but other parallel streams' databases (`vaic_14`, `vaic_17`) have granted objects to it. Not a Story 1.3 defect — affects only test teardown. Documented here for the coordinator.
- **Ruff B008 on `Depends()` in default arg**: FastAPI idiom; suppressed with a per-line `# noqa: B008 -- FastAPI idiom`.
- **Ruff I001 forced aliased import split**: `from app.core.auth import (AuthError, create_access_token, hash_password as _hash_password, verify_password)` triggers `I001`; ruff wants the aliased import in a separate `from` block. Auto-fixed.
- **31/31 tests green** in 3.20s; ruff clean; migration idempotent.

### Completion Notes List

- **AC1 ✅**: `test_login_returns_jwt_with_required_claims` decodes the JWT and asserts all 4 claims. PASSED.
- **AC2 ✅**: `test_jwt_has_configurable_expiration` asserts `exp - iat == settings.jwt_ttl_minutes * 60`. PASSED.
- **AC3 ✅**: `test_protected_endpoint_without_auth_header_returns_401_envelope` asserts 401 + envelope shape + `trace_id` parses as UUID. PASSED.
- **AC4 ✅**: `test_protected_endpoint_with_invalid_jwt_returns_401_envelope` (garbage token) + `test_protected_endpoint_with_expired_jwt_returns_401_envelope` (hand-crafted expired JWT). Both PASSED.
- **AC5 ✅**: `test_protected_endpoint_sees_tenant_context` calls `GET /auth/me` and asserts the profile fields sourced from the tenant-scoped session. PASSED.
- **AC6 ✅**: `test_protected_endpoint_enforces_rls_isolation` calls `GET /auth/users` under TenantA's token and asserts TenantB's user is invisible. PASSED.
- **AC7 ✅**: `test_password_hash_uses_argon2` calls `service.hash_password(...)` and asserts the hash starts with `$argon2`. PASSED.
- **AC8 ✅**: `test_tenant_context_resets_between_requests` asserts `tenant_context.get() is None` after a request completes. PASSED.
- **AC9 ✅**: `test_deactivated_user_login_returns_401_account_deactivated` flips `is_active=false`, attempts login, asserts `code: "ACCOUNT_DEACTIVATED"`, restores the row. PASSED.
- **AC10 ✅**: `test_auth_me_returns_user_profile` asserts the response contains `{id, email, tenant_id, department_id, role}`. PASSED.
- **AC11 ✅**: `test_two_jwts_never_cross_tenant_boundaries` logs in as both alice and bob, calls `/auth/users` under each, asserts emails are disjoint. PASSED.
- **Scope discipline**: No port interfaces, no audit sink, no LLM adapter, no arq wiring, no domain modules beyond `tenant/`. Frontend untouched. Story 1.2's RLS migration untouched.
- **DoD**: test evidence (`tests/integration/test_auth.py:62` PASSED, 31 tests in 3.20s), production code reference (`backend/app/core/auth.py`, `backend/app/modules/tenant/routes.py`, `backend/app/modules/tenant/service.py`, `backend/alembic/versions/ec784b72f20c_...`).

### File List

**Created (new):**
- `backend/app/core/auth.py` — JWT encode/decode, Argon2 hashing, `AuthMiddleware`, `AuthError`, `PUBLIC_PATHS`
- `backend/alembic/versions/ec784b72f20c_add_users_password_hash_is_active_.py` — adds `password_hash`, `is_active`, `updated_at` + `BEFORE UPDATE` trigger
- `backend/tests/integration/test_auth.py` — 13 tests covering AC1–AC11
- `backend/.env.example` — documented env vars for Story 1.3
- `_bmad-output/implementation-artifacts/1-3-auth-tenant-context-middleware.md` — this file

**Modified (existing):**
- `backend/app/modules/tenant/models.py` — added `password_hash`, `is_active`, `updated_at` columns on `User`
- `backend/app/modules/tenant/routes.py` — populated with `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`, `GET /auth/users`; `get_tenant_session` dep + `_assume_app_role` helper
- `backend/app/modules/tenant/service.py` — `authenticate`, `issue_token`, `user_profile`, `list_tenant_users`, `hash_password`
- `backend/app/main.py` — added `AuthMiddleware` + tenant router (kept `/health` + `/ready` untouched)
- `backend/tests/integration/conftest.py` — extended with `auth_seed` (password hashing) and `api_client` (TestClient + contextvar reset) fixtures; preserved `_migrations_applied` and `seed_data`

**Auto-generated (git-ignored):**
- `backend/.env` — Story 1.3 test config (DB = `vaic_13`)

## Change Log

- 2026-07-17: Story 1.3 spec authored. Status: ready-for-dev → in-progress.
- 2026-07-17: Story 1.3 implementation complete — 31/31 tests green, ruff clean, migration idempotent. Status: in-progress → review.
