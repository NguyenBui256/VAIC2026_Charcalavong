---
baseline_commit: a89a914525c5776c30fb97ff94cbbf2a56fb97a7
---

# Story 1.5: Audit Sink & Append-Only Trail

Status: done

## Story

As a **backend developer**,
I want **a single audit sink that is the only path to write `audit_trail` and that crashes the calling Run on failure**,
so that **trace completeness outranks Run completion per the banking-audit obligation**.

## Acceptance Criteria

1. **AC1 -- audit_trail table exists with correct columns**: `{id, tenant_id, run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}`. `id` is PK (UUID v7). (epics.md L476, FR-21)
2. **AC2 -- RLS enabled + forced on audit_trail**: Policy: `tenant_id = current_setting('app.tenant_id')::uuid` (USING + WITH CHECK). (epics.md L486, AD-2)
3. **AC3 -- vaic_app has INSERT only**: UPDATE, DELETE, TRUNCATE all revoked. Attempting each operation as `vaic_app` raises `InsufficientPrivilege`. (epics.md L477-478, AD-4)
4. **AC4 -- audit.log(entry) is the ONLY path to write**: `PostgresAuditSink.log()` exists, implements `AuditPort`, and is registered as the audit sink. (epics.md L479)
5. **AC5 -- When log() fails, it RAISES**: DB failure (DB down, constraint violation, RLS rejection) propagates -- caller's Run transitions to `failed`, never silently drops. (epics.md L480-481, AD-4)
6. **AC6 -- Pre-crash log() calls are persisted**: Each call commits independently -- durability. Two calls succeed, caller crashes, both rows present in DB. (epics.md L483-484)
7. **AC7 -- Every entry has UTC ISO 8601 timestamp with millisecond precision**: `ts` column is `timestamptz`; stored value is timezone-aware UTC with millisecond precision. (epics.md L485, AR-14)
8. **AC8 -- Every entry has UUID v7 step_id**: Assert version nibble = 7. (epics.md L485, AR-14)
9. **AC9 -- audit_trail is tenant-scoped via RLS**: TenantA cannot read TenantB's audit rows; cross-tenant SELECT returns empty. (epics.md L486, AD-2)

## Tasks / Subtasks

- [x] **T1 -- Alembic migration: create audit_trail table** (AC: #1, #2, #3)
  - [x] T1.1 `uv run alembic revision -m "create audit_trail table"` -> revision `34cd8281e2b3`
  - [x] T1.2 `upgrade()`: creates `audit_trail` with FR-21 columns + `id` PK (UUID v7) + `tenant_id` NOT NULL + indexes (`run_id, ts` and `tenant_id, ts`)
  - [x] T1.3 RLS: `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` + policy `tenant_isolation_policy` (USING + WITH CHECK on `tenant_id = current_setting('app.tenant_id')::uuid`)
  - [x] T1.4 Grants: `GRANT SELECT, INSERT` to `vaic_app`; `REVOKE UPDATE, DELETE, TRUNCATE` from `vaic_app` (append-only enforcement at DB level)
  - [x] T1.5 `downgrade()`: drops policy, disables RLS, drops table
- [x] **T2 -- PostgresAuditSink adapter** (AC: #4, #5, #6)
  - [x] T2.1 `app/core/adapters/audit_postgres.py`: `PostgresAuditSink(AuditPort)` with `log(entry: AuditEntry) -> None`
  - [x] T2.2 `log()` resolves `tenant_id` from `tenant_context` ContextVar (AD-2), sets GUC via `set_tenant_session_var()`
  - [x] T2.3 `log()` INSERTs into `audit_trail`, commits immediately (durability)
  - [x] T2.4 `log()` on failure: `session.rollback()`, `logger.exception(...)`, `raise` -- AD-4 NEVER swallows
  - [x] T2.5 Each `log()` call uses its own session (independent commit) when no session is provided
  - [x] T2.6 `id` is UUID v7 via `uuid7()`; `agent_id` and `model` nullable in DB
- [x] **T3 -- Integration tests** (AC: all)
  - [x] T3.1 `tests/integration/test_audit_sink.py::TestAuditTrailTable` -- table exists, columns present, `id` is PK (3 tests)
  - [x] T3.2 `tests/integration/test_audit_sink.py::TestAuditTrailRLS` -- RLS enabled, forced, policy uses `tenant_id` (3 tests)
  - [x] T3.3 `tests/integration/test_audit_sink.py::TestAppendOnlyPrivileges` -- UPDATE/DELETE/TRUNCATE rejected as `vaic_app`; grant check (4 tests)
  - [x] T3.4 `tests/integration/test_audit_sink.py::TestPostgresAuditSink` -- implements AuditPort, INSERT succeeds, null agent_id (3 tests)
  - [x] T3.5 `tests/integration/test_audit_sink.py::TestAuditSinkFailureCrashes` -- log() raises on DB failure, raises on constraint violation (2 tests)
  - [x] T3.6 `tests/integration/test_audit_sink.py::TestAuditDurability` -- entries persist before crash (1 test)
  - [x] T3.7 `tests/integration/test_audit_sink.py::TestTimestampFormat` -- ts is timestamptz, stores UTC with ms precision (2 tests)
  - [x] T3.8 `tests/integration/test_audit_sink.py::TestUUIDv7StepId` -- step_id version nibble = 7 (1 test)
  - [x] T3.9 `tests/integration/test_audit_sink.py::TestAuditTrailTenantIsolation` -- cross-tenant SELECT empty both directions, RLS rejects wrong-tenant INSERT (3 tests)
- [x] **T4 -- Run full suite (GREEN)** (AC: all)
  - [x] T4.1 `uv run pytest -v` -- **120 passed** in 5.13s (98 existing + 22 new)
  - [x] T4.2 `uv run ruff check app tests alembic` -- **All checks passed!**
  - [x] T4.3 `uv run alembic upgrade head` -- succeeds; second run is no-op (idempotent)
- [x] **T5 -- Definition of Done evidence** (AC: all)
  - [x] T5.1 Test evidence: `tests/integration/test_audit_sink.py::TestPostgresAuditSink::test_log_inserts_entry_successfully` PASSED
  - [x] T5.2 Production code reference: `backend/app/core/adapters/audit_postgres.py:55` (PostgresAuditSink), `backend/alembic/versions/34cd8281e2b3_create_audit_trail_table.py:48` (table creation)

## Dev Notes

### Scope Boundaries -- CRITICAL

**Story 1.5 delivers the audit sink adapter + migration + tests. Do NOT implement:**
- Audit routes / Trace Dashboard / audit export -- **future stories** (FR-22..FR-24)
- Wiring `PostgresAuditSink` into `main.py` as a route -- deferred to the Orchestrator/Agent stories
- Redis fallback queue (divergence-6 proposed it; AD-4 as written mandates crash-on-failure)
- LLM adapter -- **Story 1.6**
- Changes to `ports/audit.py` (owned by 1-4), `db.py`, `settings.py`, `ids.py`, `tenant_context.py`, `jobs.py`, `auth.py`, `errors.py`
- Frontend changes -- out of scope

### Design Decisions

1. **AD-4 takes precedence over divergence-6**: The divergence-6 doc proposed a Redis fallback for audit failures (swallow + retry later). AD-4 in `invariants-rules.md` (the authoritative source) explicitly mandates: "If an `audit.log()` call fails, the calling Workflow Run transitions to `failed` -- never silently drop an entry." The story instructions also mandate crash-on-failure. This implementation follows AD-4 strictly: `log()` raises on ALL failures.

2. **`PostgresAuditSink` uses `SessionLocal` (runtime engine)**: The runtime engine is subject to RLS. This is correct -- audit writes must go through the same tenant-scoping as all other writes (AD-2). Each `log()` call creates its own session so each entry commits independently (durability: a crash after N successful calls leaves N rows).

3. **`agent_id` and `model` are nullable in DB**: Per the `AuditEntry` model, `agent_id` can be empty string (orchestrator steps) and `model` can be empty string (non-LLM steps). In the DB, both map to NULL. This avoids ambiguity between "no agent" (empty) and "agent present" (UUID).

4. **`id` (row PK) is generated as UUID v7 inside `log()`**: The `step_id` comes from the caller (already UUID v7 per FR-21). The row `id` is a separate UUID v7 generated at INSERT time for indexing.

5. **`SELECT` granted in addition to `INSERT`**: The Trace Dashboard (future story) needs to read `audit_trail`. Granting `SELECT` now with RLS enforcement means reads are tenant-scoped. `UPDATE`/`DELETE`/`TRUNCATE` are explicitly revoked -- append-only at the DB level.

6. **JSONB for `input`/`output`**: Postgres `jsonb` columns with `'{}'::jsonb` server default. This enables JSON-path queries in the Trace Dashboard without schema migrations.

### Architecture Compliance

- **AD-1 (Hexagonal)**: `PostgresAuditSink` is an adapter in `core/adapters/`. It implements `AuditPort` (Protocol in `core/ports/`). Domain code imports the port, never the adapter.
- **AD-2 (Multi-tenant RLS)**: `audit_trail` carries `tenant_id UUID NOT NULL`. RLS policy enforces `tenant_id = current_setting('app.tenant_id')::uuid`. Both USING and WITH CHECK.
- **AD-4 (Single audit sink, append-only, crash on failure)**: `PostgresAuditSink.log()` is the ONLY write path. INSERT-only grants (UPDATE/DELETE/TRUNCATE revoked). `log()` raises on failure -- never swallows.
- **AR-14 (Consistency Conventions)**: UUID v7 IDs, `timestamptz` timestamps with milliseconds, `snake_case` file naming.
- **Function size**: All functions under 50 lines (verified).

### File Structure Changes

```
backend/
├── alembic/versions/
│   └── 34cd8281e2b3_create_audit_trail_table.py   # NEW -- table + RLS + grants
├── app/core/adapters/
│   ├── __init__.py                                 # UPDATED -- docstring
│   └── audit_postgres.py                           # NEW -- PostgresAuditSink
├── tests/integration/
│   └── test_audit_sink.py                          # NEW -- 22 tests
└── .env                                            # NEW -- vaic_15 DB config
```

### Anti-Patterns to Avoid

1. **Do NOT swallow errors in `log()`**. AD-4 mandates crash-on-failure. The `except` block logs and re-raises -- it never returns normally.
2. **Do NOT use `BYPASSRLS` for audit writes**. Audit entries must be tenant-scoped like everything else.
3. **Do NOT grant UPDATE or DELETE on `audit_trail`**. Append-only is enforced at the DB, not just by convention.
4. **Do NOT share a session across multiple `log()` calls** unless you explicitly want transactional batching. By default, each call uses its own session for durability.
5. **Do NOT use `uuid.uuid4()` for `id` or `step_id`**. AR-14 mandates UUID v7.

### References

- [Source: epics.md#Story-1.5 L468-486] ACs verbatim
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-4] Single audit sink, append-only, crash on failure (load-bearing)
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-2] Multi-tenant RLS isolation
- [Source: ARCHITECTURE-SPINE/consistency-conventions.md] Audit entry shape `{run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}`
- [Source: ARCHITECTURE-SPINE/divergence-6-audit-sink-failure-semantics-are-undefined.md] Proposed Redis fallback (NOT adopted -- AD-4 takes precedence)
- [Source: prd-VAIC-2026-07-17/prd/4-features.md#FR-21] Per-step Audit Trail logging
- [Source: _bmad-output/implementation-artifacts/1-4-core-ports-api-error-envelope.md] AuditPort definition (used as-is)
- [Source: _bmad-output/implementation-artifacts/1-2-multi-tenant-data-layer-postgres-rls.md] RLS patterns (mirrored)

## Dev Agent Record

### Agent Model Used

Claude (via Claude Code, glm-5.2[1m] backend session)

### Debug Log References

- **Worktree base verified**: `git log --oneline -5` shows stories 1-1 through 1-4 + 1-7 as review. Base is current.
- **`pg_policy` vs `pg_policies` view**: Initial test used `pg_policy.polqual` which stores the internal parse tree (not a readable string). Fixed by querying `pg_policies` view which exposes `qual` and `with_check` as text. Column names are `policyname` (not `polname`).
- **RLS violation message format**: The `test_rls_rejects_wrong_tenant_insert` assertion initially checked for `"check"` or `"row level"` (no hyphen). Postgres 18 returns `"row-level security policy"` (with hyphen). Fixed assertion to match `"row-level security"`.
- **`ruff B017`**: `pytest.raises(Exception)` is flagged as "blind exception". Resolved by adding `as exc_info` + a post-raise assertion verifying the error message content (RLS-specific text).
- **`ruff SIM117`**: Nested `with` statements for `patch()` + `pytest.raises()`. Resolved by combining into a single `with` statement using Python 3.10+ parenthesized context managers.
- **120/120 tests green** in 5.13s; ruff clean; migration idempotent (second `upgrade head` is no-op).

### Completion Notes List

- **AC1 ✅**: `audit_trail` created with columns `{id, tenant_id, run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}`. `id` is PK. Proven by `test_audit_trail_has_expected_columns` + `test_audit_trail_id_is_primary_key`.
- **AC2 ✅**: RLS ENABLE + FORCE + policy `tenant_isolation_policy` with `tenant_id = current_setting('app.tenant_id')::uuid` (USING + WITH CHECK). Proven by `test_rls_enabled_on_audit_trail`, `test_rls_forced_on_audit_trail`, `test_rls_policy_uses_tenant_id`.
- **AC3 ✅**: `vaic_app` has INSERT + SELECT only. UPDATE, DELETE, TRUNCATE all raise `InsufficientPrivilege`. Proven by `test_vaic_app_cannot_update_audit_trail`, `test_vaic_app_cannot_delete_audit_trail`, `test_vaic_app_cannot_truncate_audit_trail`, `test_vaic_app_grants_audit_trail`.
- **AC4 ✅**: `PostgresAuditSink(AuditPort)` with `log(entry) -> None`. `isinstance(sink, AuditPort)` passes. Proven by `test_postgres_audit_sink_implements_audit_port`.
- **AC5 ✅**: `log()` raises `ConnectionError` on DB failure, `RuntimeError` on constraint violation. Proven by `test_log_raises_on_db_failure`, `test_log_raises_on_constraint_violation`.
- **AC6 ✅**: Two `log()` calls succeed, caller crashes, both rows present in DB (read via admin connection). Proven by `test_entries_persist_before_crash`.
- **AC7 ✅**: `ts` column is `timestamp with time zone`. Stored value is timezone-aware UTC with `.microsecond == 789000` (millisecond precision). Proven by `test_ts_is_timestamptz_type`, `test_log_stores_utc_timestamp`.
- **AC8 ✅**: `step_id` in DB has version nibble 7. Proven by `test_step_id_is_uuid_v7`.
- **AC9 ✅**: TenantA cannot read TenantB's audit rows; TenantB cannot read TenantA's; RLS WITH CHECK rejects cross-tenant INSERT. Proven by `test_tenant_a_cannot_read_tenant_b_audit_rows`, `test_tenant_b_cannot_read_tenant_a_audit_rows`, `test_rls_rejects_wrong_tenant_insert`.
- **Scope discipline**: No audit routes, no main.py changes, no Redis fallback, no LLM adapter, no frontend changes.
- **DoD**: test evidence (`tests/integration/test_audit_sink.py` PASSED, 120 tests in 5.13s), production code reference (`backend/app/core/adapters/audit_postgres.py`, `backend/alembic/versions/34cd8281e2b3_create_audit_trail_table.py`).

### File List

**Created (new):**
- `backend/alembic/versions/34cd8281e2b3_create_audit_trail_table.py` -- migration: audit_trail table + RLS + INSERT-only grants
- `backend/app/core/adapters/audit_postgres.py` -- `PostgresAuditSink(AuditPort)` with `log(entry) -> None`; raises on failure (AD-4)
- `backend/tests/integration/test_audit_sink.py` -- 22 tests covering all 9 ACs
- `backend/.env` -- vaic_15 test DB configuration

**Modified (existing):**
- `backend/app/core/adapters/__init__.py` -- updated docstring to mention PostgresAuditSink

## Change Log

- 2026-07-17: Story 1.5 spec authored. Status: ready-for-dev -> in-progress.
- 2026-07-17: Story 1.5 implementation complete -- 120/120 tests green, ruff clean, migration idempotent. Status: in-progress -> review.
