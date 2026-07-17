---
baseline_commit: 4e2c5ad3cb823b8edb5f8ce6d0ea8b3d94a4fd1c
---

# Story 2.7: Per-Agent API Integration Configuration

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user configuring a Specialist Agent**,
I want **to register reusable API Integrations that my Tools can call**,
so that **my Agent can interact with stubbed Gmail, Calendar, or bank-core endpoints without re-specifying the connection per Tool**.

This story adds the **API Integrations** surface to the Agent Builder (the 4th of the 6 tabs, UX-DR16): a per-Agent registry of named, reusable HTTP connections whose credentials are stored **encrypted at rest** and whose runtime calls are logged to `audit_trail` **without ever capturing the auth header**. Epic 1 is DONE and is the stable contract base — reuse its auth, RLS, error/success envelope, and the audit sink; do not re-implement them. Story 2.1 delivered the `agents` table + CRUD and Story 2.2 delivered the detail shell with the placeholder `ApiIntegrationsTab` this story fills in.

## Acceptance Criteria

Verbatim from [epics.md#Story-2.7 L801–L814].

1. **AC1 — POST registers an Integration with UUID v7 `integration_id`** (epics.md L803–805): Given an Agent exists and the user opens the API Integrations tab, when the user clicks "New Integration" and provides `{name, base_url, auth_header (stored, not displayed in full), schema}`, then the Integration is registered against the Agent with a UUID v7 `integration_id`.
2. **AC2 — `auth_header` stored ENCRYPTED at rest, never hard-coded** (epics.md L806, AR-14 stored credentials / NFR-6): The `auth_header` is stored encrypted at rest (per AR-14 stored credentials, never hard-coded). The plaintext is never persisted, never returned in full by any read/list endpoint (masked, e.g. `Bearer ••••abcd`), and never committed to source.
3. **AC3 — Integration selectable from any Tool via an "API Integration" dropdown** (epics.md L807): The Integration is selectable from any Tool on that Agent via an "API Integration" dropdown in the Tool editor (Story 2.6).
4. **AC4 — Runtime call hits `{base_url}/{path}` with the stored auth header attached** (epics.md L808–809): When a Tool invokes the Integration during a Workflow Run, the request is made to `{base_url}/{path}` with the (decrypted) stored auth header attached to the outbound request.
5. **AC5 — Call logged to `audit_trail` with `type: "integration.called"`** (epics.md L810, FR-21): The call is logged via `audit.log()` with `type: "integration.called"`, `input: {integration_id, path, method}`, `output: {status_code, latency_ms}`.
6. **AC6 — MVP Integrations point ONLY at stubbed FastAPI endpoints owned by the demo** (epics.md L811, FR-4, §5 non-goal): For MVP, Integrations point only at stubbed FastAPI endpoints owned by the demo. Live OAuth is out of scope — no OAuth token exchange, refresh, or third-party consent flow is built.
7. **AC7 — Auth header is NEVER logged in `audit_trail`** (epics.md L812, NFR-9): An Integration's auth header is never logged in `audit_trail` — only metadata (`integration_id`, `status`, `latency`) is captured. No log line, audit entry, error message, or trace anywhere may contain the header value.
8. **AC8 — API Integrations tab lists integrations with name, truncated base_url, last-used timestamp** (epics.md L813): The API Integrations tab UI lists all integrations with name, `base_url` (truncated), and last-used timestamp.
9. **AC9 — "Test Integration" affordance pings health and shows connected/disconnected** (epics.md L814): A "Test Integration" affordance pings `GET {base_url}/health` (or equivalent) and shows connected/disconnected status.

## Tasks / Subtasks

- [ ] **T1 — Encryption helper (stored-credential crypto)** (AC: #2, #7)
  - [ ] T1.1 `app/core/crypto.py` (NEW) — symmetric encrypt/decrypt for stored credentials using `cryptography` Fernet (already transitively available via `python-jose[cryptography]`; add `cryptography` as a direct dependency in `pyproject.toml` if not resolvable). Functions: `encrypt_secret(plaintext: str) -> str` and `decrypt_secret(ciphertext: str) -> str`; keep each ≤ 50 lines.
  - [ ] T1.2 Add `encryption_key: str` to `app/core/settings.py` (`VAIC_ENCRYPTION_KEY`, a urlsafe base64 32-byte Fernet key). Follow the LLM-key convention: a missing/blank key surfaces a **clear error when encrypt/decrypt is called**, not at import time. Document in `.env.example` (never commit a real key — NFR-6).
  - [ ] T1.3 `mask_secret(plaintext: str) -> str` helper — returns a display-safe mask (e.g. last 4 chars, `Bearer ••••abcd`). Used by serialization so full auth_header never leaves the backend (AC2).
- [ ] **T2 — `api_integrations` model** (AC: #1, #2)
  - [ ] T2.1 Add `ApiIntegration(Base)` to `app/modules/agent_builder/models.py` — SQLAlchemy 2.x `Mapped[...]` declarative, `__tablename__ = "api_integrations"`.
  - [ ] T2.2 Columns: `id` (`UUID`, PK, `default=uuid7` from `app.core.ids`), `tenant_id UUID NOT NULL` (FK `tenants.id`, `ondelete="CASCADE"`), `agent_id UUID NOT NULL` (FK `agents.id`, `ondelete="CASCADE"`), `name String(255) NOT NULL`, `base_url String(2048) NOT NULL`, `auth_header_encrypted Text NOT NULL` (ciphertext only — NEVER a plaintext column), `schema JSONB` (the integration schema payload), `last_used_at DateTime(timezone=True) nullable`, `is_deleted`/`deleted_at` (soft-delete, mirror `Agent`), `created_at`/`updated_at` (`server_default=func.now()`).
  - [ ] T2.3 Derive `tenant_id` from `tenant_context`/`agent.tenant_id` — never from the request body (mirror Story 2.1 T3).
- [ ] **T3 — Alembic migration: create `api_integrations` + RLS** (AC: #1, #2)
  - [ ] T3.1 `cd backend && uv run alembic revision -m "create api_integrations rls"` — `down_revision` MUST be the current head (the `create agents rls` migration from Story 2.1; confirm with `uv run alembic heads`).
  - [ ] T3.2 `upgrade()`: `op.create_table("api_integrations", ...)`; index `ix_api_integrations_tenant_id` and `ix_api_integrations_agent_id`.
  - [ ] T3.3 RLS DDL — copy the exact pattern from the audit_trail / agents migration: `ENABLE` + `FORCE ROW LEVEL SECURITY` + `CREATE POLICY tenant_isolation_policy ON api_integrations USING (tenant_id = current_setting('app.tenant_id')::uuid) WITH CHECK (...)`.
  - [ ] T3.4 Grants: `GRANT SELECT, INSERT, UPDATE ON api_integrations TO vaic_app;` + `REVOKE DELETE, TRUNCATE ON api_integrations FROM vaic_app;` (soft-delete-only at the DB, mirror agents).
  - [ ] T3.5 `downgrade()`: drop policy, `NO FORCE`/`DISABLE` RLS, drop table. Idempotency: `uv run alembic upgrade head` twice is a no-op.
- [ ] **T4 — Service layer** (AC: #1, #2, #8, #9)
  - [ ] T4.1 `create_integration(session, *, agent_id, role, name, base_url, auth_header, schema) -> ApiIntegration` — assert `role == "builder"` (else `AuthorizationError(code="FORBIDDEN")`); `encrypt_secret(auth_header)` before INSERT; `tenant_id`/`agent_id` scope derived from context/agent record.
  - [ ] T4.2 `list_integrations(session, agent_id) -> list[ApiIntegration]`, `get_integration(session, integration_id)`, `update_integration(...)`, `soft_delete_integration(...)` — reuse the `_authorize_mutation` guard pattern from Story 2.1; NEVER filter `tenant_id` in Python (RLS owns it).
  - [ ] T4.3 `serialize_integration(i) -> dict` — `{id, agent_id, name, base_url, auth_header_masked: mask_secret(...), schema, last_used_at, created_at}`. **NEVER include the decrypted or ciphertext auth_header** in the response (AC2).
  - [ ] T4.4 `test_integration(session, integration_id) -> {status: "connected"|"disconnected", status_code, latency_ms}` — pings `GET {base_url}/health` with the decrypted header via the runtime client (T6); does NOT return the header (AC9).
- [ ] **T5 — Routes** (AC: #1, #2, #8, #9)
  - [ ] T5.1 Fill/extend `app/modules/agent_builder/routes.py` (or a nested router) with `APIRouter(prefix="/agents/{agent_id}/integrations", tags=["integrations"])`; register in `app/main.py`.
  - [ ] T5.2 Pydantic schemas: `CreateIntegrationRequest{name, base_url, auth_header, schema?}`, `UpdateIntegrationRequest{name?, base_url?, auth_header?, schema?}`. Response uses `serialize_integration` (masked header).
  - [ ] T5.3 Endpoints: `POST ""` (201), `GET ""` (list), `GET "/{integration_id}"`, `PATCH "/{integration_id}"`, `DELETE "/{integration_id}"` (soft-delete), `POST "/{integration_id}/test"` (AC9). Use the tenant-scoped session dep + `Principal` from `request.state`; success envelope `{data, error, meta}`; `DomainError` handlers own error rendering.
- [ ] **T6 — Runtime integration client + audit** (AC: #4, #5, #6, #7)
  - [ ] T6.1 `app/modules/agent_builder/integration_client.py` (NEW) — `call_integration(session, integration_id, *, path, method, body?) -> {status_code, latency_ms, response}`. Loads the Integration record, `decrypt_secret(auth_header_encrypted)`, issues the request to `{base_url}/{path}` with the header attached (httpx or the project's HTTP client). Update `last_used_at` on success (AC8).
  - [ ] T6.2 Emit `audit.log(AuditEntry(type="integration.called", input={integration_id, path, method}, output={status_code, latency_ms}, ...))` after the call (AC5). Compute `latency_ms` from a monotonic clock around the request.
  - [ ] T6.3 **NFR-9 guard**: the auth header value must NEVER appear in `input`, `output`, exception messages, or any log. Attach it only to the outbound request object; never place it in a dict that flows to `audit.log()` or a logger. Add a defensive assertion/test.
  - [ ] T6.4 Expose `call_integration` so a Tool (Story 2.6) selecting this Integration can dispatch through it. This story provides the callable; the Tool→Integration wiring detail is shared with 2.6 — see Dependencies.
- [ ] **T7 — Frontend: API Integrations tab** (AC: #1, #2, #8, #9)
  - [ ] T7.1 `src/lib/integrationsApi.ts` (NEW) — TS types (`ApiIntegration`, `CreateIntegrationInput`, `UpdateIntegrationInput`) + typed `apiFetch` wrappers: `listIntegrations(agentId)`, `createIntegration`, `updateIntegration`, `deleteIntegration`, `testIntegration`. Note the read shape returns `auth_header_masked`, never the full header.
  - [ ] T7.2 `src/hooks/useIntegrations.ts` + `useIntegrationMutations.ts` (NEW) — TanStack Query, keyed `["integrations", agentId]`; mutations invalidate on success. Mirror `useAgents`/`useAgentMutations` from Story 2.2.
  - [ ] T7.3 `src/components/agents/tabs/ApiIntegrationsTab.tsx` — replace the Story 2.2 placeholder. Lists integrations (name, truncated `base_url`, last-used timestamp — AC8) in the `Table` primitive; "New Integration" Primary CTA (UX-DR3) opens a form (`FormField`, UX-DR8): Name (required), Base URL (required), Auth Header (password-style input — value write-only, shown masked after save), Schema (JSON editor / textarea). Loading→`Skeleton`, error→`ErrorState`+retry, empty→`EmptyState` (UX-DR23).
  - [ ] T7.4 "Test Integration" affordance per row (AC9) — calls `testIntegration`, shows connected/disconnected status pill; use `semanticIcons.ApiIntegration` (Plug/Webhook, UX-DR10).
  - [ ] T7.5 Tab badge count (e.g. "2 integrations") surfaced to `AgentDetailShell` per UX-DR16; dirty-dot on unsaved form (reuse Story 2.2 pattern).
- [ ] **T8 — Tool editor "API Integration" dropdown** (AC: #3)
  - [ ] T8.1 In the Tool editor (Story 2.6 `ToolsTab`), add an "API Integration" dropdown populated from `listIntegrations(agentId)` so a Tool can reference an `integration_id`. **Coordinate with Story 2.6** — if 2.6 is not yet merged, deliver the reusable dropdown component (`IntegrationSelect.tsx`) + `useIntegrations` hook here and flag the wiring as a dependency (see Open Questions).
- [ ] **T9 — Tests** (AC: all)
  - [ ] T9.1 `tests/unit/test_crypto.py` — `encrypt_secret`/`decrypt_secret` round-trip; ciphertext ≠ plaintext; missing key raises a clear error; `mask_secret` never leaks more than the last 4 chars (AC2).
  - [ ] T9.2 `tests/integration/test_integrations_api.py` — POST 201 shape with UUID v7 id (AC1); response NEVER contains the plaintext/ciphertext auth_header, only masked (AC2); list shows name/base_url/last_used (AC8); RLS cross-tenant read empty; non-builder POST → 403; soft-delete excluded from list.
  - [ ] T9.3 `tests/unit/test_integration_client.py` — `call_integration` hits `{base_url}/{path}` with header attached (assert against a stub server / mocked transport, AC4/AC6); emits exactly one `audit.log()` with `type="integration.called"`, `input={integration_id, path, method}`, `output={status_code, latency_ms}` (AC5).
  - [ ] T9.4 **NFR-9 mandatory test** — assert the auth header value appears in NONE of: the `AuditEntry.input`, `AuditEntry.output`, the serialized API response, or captured log output (AC7). This is the load-bearing security test.
  - [ ] T9.5 `src/components/agents/tabs/ApiIntegrationsTab.test.tsx` — list renders (name/truncated URL/last-used), New Integration form validates on blur (UX-DR8), auth header input is write-only and shows masked after save, Test Integration shows connected/disconnected, empty/loading/error states (UX-DR23). Mock `integrationsApi` — no live network.
- [ ] **T10 — Green run + DoD evidence** (AC: all)
  - [ ] T10.1 Backend: `uv run alembic upgrade head` (Postgres 18); `uv run pytest`; `uv run ruff check app tests alembic`.
  - [ ] T10.2 Frontend: `npx tsc --noEmit` clean; `npx vitest run`; `npm run build`.
  - [ ] T10.3 Record test evidence (`file:line` PASSED + green output) and production `file:line` per AR-14 DoD. Explicitly cite the passing NFR-9 no-leak test (T9.4).

## Dev Notes

### Scope Boundaries — CRITICAL

**Story 2.7 delivers the per-Agent API Integration registry (backend model + CRUD + encryption + runtime call/audit) and the API Integrations tab UI. Do NOT:**
- Build live OAuth — no token exchange, refresh, or third-party consent flow. **MVP integrations point ONLY at stubbed FastAPI endpoints owned by the demo** (AC6, §5 non-goal). [epics.md L811]
- Re-implement the Agent model/CRUD (Story 2.1), the detail shell / 6-tab nav (Story 2.2), or the Tools schemas/sandbox (Story 2.6). This story consumes them.
- Implement the Orchestrator / Workflow Run loop that drives Tool→Integration calls at run time (Epic 3) — only PROVIDE the `call_integration` callable and log its invocation.
- Build the parallel-team MCP server. Integrations here are direct HTTP to demo stubs, distinct from MCP tools (AD-3).

### Architecture Compliance — load-bearing invariants

- **AR-14 stored credentials / NFR-6 — `auth_header` stored ENCRYPTED at rest, NEVER hard-coded** (AC2): The auth header is persisted only as ciphertext (`auth_header_encrypted`) via `app/core/crypto.py` (Fernet). No plaintext column exists; no secret is committed to source; the encryption key comes from `VAIC_ENCRYPTION_KEY` env (never `.env` committed — NFR-6). Read/list endpoints return a **masked** value only. [epics.md L806; L39 FR-4; L101 NFR-6]
- **NFR-9 — auth header NEVER logged to `audit_trail`; only metadata** (AC7): `audit.log()` for `type: "integration.called"` carries `input: {integration_id, path, method}` and `output: {status_code, latency_ms}` — and nothing else. The header is attached only to the outbound HTTP request; it must not enter any dict passed to `audit.log()`, any logger, or any exception message. This is enforced by the mandatory no-leak test (T9.4). [epics.md L812]
- **AD-4 — Single audit sink, append-only, failure crashes the caller** (AC5): The `integration.called` entry goes through `AuditPort.log()` (`core/ports/audit.py:63`) implemented by `PostgresAuditSink` (`core/adapters/audit_postgres.py:71`). It is the ONLY writer to `audit_trail`; never write raw SQL/ORM; never swallow a `log()` failure.
- **AD-2 — Multi-tenant isolation via RLS** (AC1 scoping): `api_integrations` carries `tenant_id`; RLS ENABLE + FORCE + `tenant_id = current_setting('app.tenant_id')::uuid` (USING + WITH CHECK). RLS only bites under the `vaic_app` role ([[rls-role-config-dependency]]) — tests must `SET LOCAL ROLE vaic_app`. Never filter `tenant_id` in Python.
- **AD-1 — Hexagonal modular monolith**: Domain logic in `agent_builder/service.py` + `integration_client.py`; routes are thin adapters; the crypto helper is a `core` utility. Cross-module reuse goes through public interfaces (reuse the promoted `get_tenant_session` dep from Story 2.1 OQ-2, do not import another module's internals).
- **AR-13 — Pinned stack** (rely on this; no web research): Python 3.13, FastAPI 0.139.x, SQLAlchemy 2.x sync, Pydantic 2.x, Alembic, PostgreSQL 18, psycopg3. Encryption uses `cryptography` (Fernet) — available via the existing `python-jose[cryptography]` dependency; declare it directly if the import does not resolve. The outbound HTTP client should be the project's existing choice (httpx if present) — do not add a redundant HTTP library.
- **AR-14 consistency conventions**: UUID v7 via `app.core.ids.uuid7`; `timestamptz` UTC ISO 8601 ms; success envelope `{data, error, meta}`; error shape `{error:{code,message,details,trace_id}}`; 50-line function ceiling; DoD = test `file:line` + green output AND production `file:line`.

### UX Compliance

- **UX-DR16 (Agent Builder Surface, API Integrations tab)** [epics.md L233]: The API Integrations tab is one of the locked 6 tabs (Identity, Knowledge Base, Tools, **API Integrations**, Prompt, Model). It lists registered connections (name, truncated base_url, last-used) and provides create/edit + Test Integration. Story 2.2 mounted this as a placeholder panel; this story fills it.
- **UX-DR8 (Form Patterns)** [epics.md L217]: Labels above inputs, required marked `*` in destructive color, inline validation on **blur not keystroke**. Reuse the `FormField` primitive (`src/components/ui/FormField.tsx`). The Auth Header input is write-only (password-style); after save it displays the masked value returned by the API.
- **UX-DR23 (Empty / Loading / Error)** [epics.md L247]: The tab and each async action define Empty (`EmptyState` + CTA), Loading (`Skeleton`, never a spinner), Error (`ErrorState` + retry). Follow the branch order from `RecentRuns.tsx`.
- **UX-DR10 (Iconography)** [epics.md L221, L584]: API Integration icon is locked to **Plug/Webhook** — use `semanticIcons.ApiIntegration` from `src/lib/icons.tsx`. lucide-react only, 1.5px stroke. No new icon library.
- **UX-DR3 (Buttons)**: "New Integration" is the single Primary CTA on the tab. Keep one Primary per view.

### Dependencies — CRITICAL

- **Story 2.1 (Agent record)** — `api_integrations.agent_id` FKs the `agents` table and derives `tenant_id` from the Agent record. At baseline the `Agent` model + `agents` table + CRUD are delivered by Story 2.1. Do NOT invent a competing Agent model. Reuse the `_authorize_mutation` guard and the tenant-session dependency introduced there.
- **Story 2.2 (Agent detail shell)** — the API Integrations tab replaces the placeholder `ApiIntegrationsTab` panel mounted by Story 2.2. Reuse `AgentDetailShell`, the dirty-dot/badge slots, `Toast`, `ConfirmDialog`, and the TanStack Query hook/test-mock patterns.
- **Story 2.6 (Per-Agent Tools)** — AC3 requires the Integration to be selectable from the Tool editor via an "API Integration" dropdown. This is the shared seam: this story provides `integration_id` + `listIntegrations` + a reusable `IntegrationSelect` component; Story 2.6 owns the Tool editor that hosts the dropdown. If 2.6 is not merged when this story runs, deliver the dropdown component and flag the final wiring (OQ-2). Runtime: a Tool selecting an Integration dispatches through `call_integration` (T6).
- **Epic 1 (DONE)** — reuse: `audit.log()` sink (Story 1.5) writing `type: "integration.called"` with `{integration_id, path, method, status_code, latency_ms}` but NEVER the auth header; the `settings.py` env-var convention (Story 1.6 LLM keys) for the new `VAIC_ENCRYPTION_KEY`; auth/tenant-context middleware (Story 1.3); the `{data,error,meta}` envelope + `DomainError` handlers (Story 1.4).

### Note on encryption — no crypto helper exists at baseline

`grep` confirms there is **no `app/core/crypto.py` at baseline** and `settings.py` has no `encryption_key` field — this story CREATES both. `cryptography` (Fernet) is pulled transitively by `python-jose[cryptography]` (`pyproject.toml:32`); import it directly and, if the direct import does not resolve, add `cryptography` as an explicit dependency. Follow the Story 1.6 LLM-key pattern: the key is read from env, and a missing/blank key raises a clear error **at call time**, not import time.

### File Structure Changes

```
backend/
├── alembic/
│   └── versions/
│       └── <rev>_create_api_integrations_rls.py   # NEW — table + RLS + grants
├── app/
│   ├── core/
│   │   ├── crypto.py                               # NEW — encrypt/decrypt/mask (Fernet)
│   │   └── settings.py                             # UPDATED — encryption_key (VAIC_ENCRYPTION_KEY)
│   ├── main.py                                     # UPDATED — include integrations router
│   └── modules/
│       └── agent_builder/
│           ├── models.py                           # UPDATED — ApiIntegration
│           ├── service.py                          # UPDATED — integration CRUD + test + serialize (masked)
│           ├── integration_client.py               # NEW — call_integration() + integration.called audit
│           └── routes.py                            # UPDATED — /agents/{agent_id}/integrations CRUD + /test
├── .env.example                                    # UPDATED — VAIC_ENCRYPTION_KEY (placeholder only)
└── tests/
    ├── unit/
    │   ├── test_crypto.py                          # NEW — round-trip, missing-key, mask
    │   └── test_integration_client.py              # NEW — call path, audit, NFR-9 no-leak
    └── integration/
        └── test_integrations_api.py               # NEW — CRUD, RLS, masked response, authz

frontend/
└── src/
    ├── lib/
    │   └── integrationsApi.ts                      # NEW — typed apiFetch wrappers
    ├── hooks/
    │   ├── useIntegrations.ts                      # NEW
    │   └── useIntegrationMutations.ts              # NEW
    └── components/
        └── agents/
            ├── tabs/ApiIntegrationsTab.tsx         # UPDATED — replaces 2.2 placeholder
            ├── IntegrationSelect.tsx               # NEW — reusable dropdown for Tool editor (AC3)
            └── tabs/ApiIntegrationsTab.test.tsx    # NEW
```

Reference (unchanged, cited): `backend/app/core/ports/audit.py`, `backend/app/core/adapters/audit_postgres.py`, `backend/app/core/settings.py`, `backend/app/modules/agent_builder/{models,service,routes}.py`, `backend/app/core/ports/tool.py`; `frontend/src/lib/api.ts`, `frontend/src/components/ui/*`, `frontend/src/lib/icons.tsx`.

### Testing

- Backend: `pytest` + `uv run pytest`. RLS/CRUD tests need a running Postgres 18 (integration); crypto + client tests are unit (no network — mock the HTTP transport / point at a local stub).
- **Mandatory NFR-9 no-leak test** (T9.4, AC7): assert the auth header value is absent from `AuditEntry.input`, `AuditEntry.output`, the serialized API response, and captured log output. This is the security-critical assertion — cite it in DoD evidence.
- **Encrypted-at-rest test** (AC2): assert the stored `auth_header_encrypted` ≠ plaintext, decrypts back to plaintext, and that no read endpoint returns the full header (masked only).
- **Runtime call test** (AC4/AC5/AC6): drive `call_integration` against a demo stub / mocked transport; assert the request targets `{base_url}/{path}` with the header attached and exactly one `integration.called` audit entry with the exact `input`/`output` shape.
- Frontend: Vitest + Testing Library; mock `integrationsApi` (no live network); wrap in `MemoryRouter` + fresh `QueryClientProvider`. Assert UX-DR8 blur validation, write-only masked header field, Test Integration status, and UX-DR23 states.
- Keep tests deterministic; no real network, no sleep.

### Anti-Patterns to Avoid

1. **Do NOT store the auth header in plaintext** — persist ciphertext only (`auth_header_encrypted` via `crypto.encrypt_secret`). No plaintext column, ever (AC2).
2. **Do NOT put the auth header anywhere near `audit.log()`, a logger, or an exception message** — attach it ONLY to the outbound request object. `input`/`output` carry metadata only (AC7/NFR-9).
3. **Do NOT return the full (or ciphertext) auth header from any read/list endpoint** — serialize a mask only (AC2).
4. **Do NOT hard-code any secret in source or commit `.env`** (NFR-6). The Fernet key comes from `VAIC_ENCRYPTION_KEY`.
5. **Do NOT build live OAuth / token refresh / consent flows** — MVP hits demo FastAPI stubs only (AC6, §5 non-goal).
6. **Do NOT write `audit_trail` directly** (raw SQL/ORM) or swallow an audit failure — route through `AuditPort`/`PostgresAuditSink` only (AD-4).
7. **Do NOT filter `tenant_id` in Python** — RLS owns tenant isolation (AD-2). Only `agent_id`/`is_deleted` are legitimate domain filters.
8. **Do NOT hard-delete** — soft-delete via `is_deleted`/`deleted_at`; the migration REVOKEs `DELETE` from `vaic_app`.
9. **Do NOT invent a competing Agent model or reach into another module's internals** — reuse Story 2.1's `Agent` + tenant-session dependency (AD-1).
10. **Do NOT add a new icon/toast/modal/HTTP library** — reuse `semanticIcons.ApiIntegration`, the Story 2.2 `Toast`/`ConfirmDialog`, and the project HTTP client.
11. **Do NOT exceed 50 lines per function** (AR-14) — split crypto, serialization (masking), the client call, and audit emission into helpers.
12. **Do NOT modify `sprint-status.yaml`** — the orchestrator owns it centrally.

### Open Questions (for the human — see Report)

- **OQ-1 (audit shape for non-Run integration calls)**: `AuditEntry` is Run-centric (`run_id`, `step_id` required non-null UUIDs — `ports/audit.py:42-49`). An `integration.called` event during a Workflow Run has a natural `run_id`/`step_id`; but a **Test Integration** ping (AC9) and config-time calls do not. Confirm whether Test pings emit an audit entry at all, and if so what `run_id`/`step_id` convention to use (same OQ-1 as Story 2.1's config-time CRUD audit). Recommended: Test pings are diagnostic and do NOT write `audit_trail`; only in-Run `integration.called` events do.
- **OQ-2 (Tool→Integration wiring seam with Story 2.6)**: AC3's "API Integration dropdown in the Tool editor" straddles this story and Story 2.6. Confirm whether 2.6 is merged first (this story just adds the dropdown to its `ToolsTab`) or whether this story delivers the reusable `IntegrationSelect` component and 2.6 consumes it. Also confirm where the Tool persists its selected `integration_id` (Tool model field — owned by 2.6).
- **OQ-3 (encryption key management)**: `VAIC_ENCRYPTION_KEY` is a single process-wide Fernet key for MVP. Confirm this is acceptable vs. per-tenant keys / key rotation (out of scope for MVP but flag for security review).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.7 L795–L814] — story + all acceptance criteria (verbatim)
- [Source: _bmad-output/planning-artifacts/epics.md L39] — FR-4 Per-Agent API Integration configuration
- [Source: _bmad-output/planning-artifacts/epics.md L101] — NFR-6 stored credentials, never hard-coded secrets
- [Source: _bmad-output/planning-artifacts/epics.md L233] — UX-DR16 Agent Builder surface, 6 tabs incl. API Integrations
- [Source: _bmad-output/planning-artifacts/epics.md L221, L584] — UX-DR10 icon lock: Plug/Webhook = API Integration
- [Source: _bmad-output/planning-artifacts/epics.md L217] — UX-DR8 form patterns
- [Source: _bmad-output/planning-artifacts/epics.md L247] — UX-DR23 empty/loading/error states
- [Source: _bmad-output/planning-artifacts/epics.md L258] — FR-4 traceability (Epic 2)
- [Source: backend/app/core/ports/audit.py:23-68] — `AuditEntry` FR-21 fields, `AuditPort.log`
- [Source: backend/app/core/adapters/audit_postgres.py:55-134] — `PostgresAuditSink` (the only audit writer, AD-4)
- [Source: backend/app/core/settings.py:45-59] — env-var convention (VAIC_ prefix, call-time key errors) to mirror for VAIC_ENCRYPTION_KEY
- [Source: backend/pyproject.toml:32] — `python-jose[cryptography]` (transitively provides Fernet)
- [Source: backend/app/modules/agent_builder/models.py] — Agent model (Story 2.1) that `ApiIntegration` FKs
- [Source: backend/app/core/ports/tool.py:21-67] — `ToolPort`/`ToolInvocation` (Story 2.6 seam for AC3)
- [Source: _bmad-output/implementation-artifacts/2-1-agent-crud-identity-department-scoping.md] — Agent model/CRUD, RLS + soft-delete + audit patterns, OQ-1/OQ-2
- [Source: _bmad-output/implementation-artifacts/2-2-agent-list-detail-shell-identity-tab.md] — detail shell, ApiIntegrationsTab placeholder, Toast/ConfirmDialog, TanStack Query + test-mock patterns
- [Source: frontend/src/lib/api.ts] — `apiFetch`, `ApiError`, envelope unwrap, header injection
- [Source: frontend/src/components/ui/index.ts + FormField.tsx] — reusable primitives (UX-DR8)
- [Source: frontend/src/lib/icons.tsx] — `semanticIcons.ApiIntegration` (Plug/Webhook)
- [Source: ARCHITECTURE-SPINE/stack.md] — pinned stack (AR-13)
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-2, AD-1, AD-4] — RLS, hexagonal, single audit sink
- [Source: memory/rls-role-config-dependency.md] — RLS only bites under the `vaic_app` role

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-07-17: Story 2.7 spec authored by story-context engine. Status: ready-for-dev.
