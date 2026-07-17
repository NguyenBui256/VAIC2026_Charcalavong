---
baseline_commit: 9ad9a118ddae0027006eb8a296792fe98d4282c9
---

# Story 1.7: arq Background Job Foundation

Status: review

## Story

As a **backend developer building Orchestrator, Actions, or Triggers**,
I want **arq worker infrastructure with tenant context materialized across the worker boundary**,
so that **background jobs run with correct RLS isolation and don't crash on missing tenant context**.

## Acceptance Criteria

Source: `_bmad-output/planning-artifacts/epics.md` L509–L528.

1. **AC1 — WorkerSettings connects to Redis**: When Redis 7.4+ is configured, running the arq WorkerSettings connects to Redis and begins polling for jobs.
2. **AC2 — `enqueue_job_with_context()` captures tenant_id**: When domain code enqueues a background job, the enqueuer captures `tenant_id` (and `department_id` if relevant) from the current contextvar and serializes them into the arq job kwargs (AD-10).
3. **AC3 — Worker function re-sets contextvar + DB RLS var**: When the arq worker dequeues a job, the worker function's first action deserializes `tenant_id` from kwargs, sets `tenant_context.ContextVar`, and issues `SET LOCAL app.tenant_id` on its DB connection before any domain work (AD-10).
4. **AC4 — Missing tenant_id raises at entry**: If the payload is missing `tenant_id`, the worker raises immediately with a structured error and does not execute domain code.
5. **AC5 — cron_jobs entrypoint fan-out**: When a job is configured as a `cron_jobs` entrypoint (Schedule Trigger fan-out pattern), the cron job runs under `BYPASSRLS`, enumerates matching tenants, and enqueues one per-tenant job with materialized `tenant_id` for each (AD-10).
6. **AC6 — No cross-tenant leak back-to-back**: A test verifies that two jobs from different tenants enqueued back-to-back do not leak tenant context to each other.
7. **AC7 — arq only, no Celery/APScheduler/threads**: No Celery, APScheduler, or background threads exist in domain code — arq is the only async job system (AR-14).

## Tasks / Subtasks

- [x] **T1 — `app/core/jobs.py` skeleton + types** (AC: #2, #3, #4)
  - [x] T1.1 `MissingTenantContextError(RuntimeError)` with structured `where` arg
  - [x] T1.2 `TENANT_ID_KWARG = "_tenant_id"` constant — reserved key
- [x] **T2 — Enqueue path: `enqueue_job_with_context()`** (AC: #2, #4)
  - [x] T2.1 Reads `tenant_context.get()`; raises `MissingTenantContextError` if `None` (fail-fast at enqueue, not silently at worker)
  - [x] T2.2 Refuses explicit `_tenant_id` kwarg — reserved for this function
  - [x] T2.3 Serializes tenant UUID as `_tenant_id` into arq kwargs
  - [x] T2.4 Pass-through for `job_id`, queue_name, and other kwargs
- [x] **T3 — Worker path: `@tenant_aware_job` decorator** (AC: #3, #4)
  - [x] T3.1 Pops `_tenant_id` from kwargs; raises `MissingTenantContextError` on missing/empty
  - [x] T3.2 Validates UUID; raises `MissingTenantContextError` on invalid format
  - [x] T3.3 Calls `set_tenant_context(tenant_id)` to re-hydrate contextvar
  - [x] T3.4 Opens `SessionLocal()`, stashes on `ctx["session"]`
  - [x] T3.5 Issues `SET LOCAL ROLE <app_db_role>` if `settings.app_db_role` is set (drops superuser privileges so RLS policies bite — needed for dev/test where `database_url` authenticates as a superuser)
  - [x] T3.6 Calls `set_tenant_session_var(session, tenant_id)` — issues `set_config('app.tenant_id', ..., true)`
  - [x] T3.7 Calls wrapped `fn(ctx, **kwargs)` (without `_tenant_id`)
  - [x] T3.8 On exception: `session.rollback()` + re-raise (arq marks job failed)
  - [x] T3.9 `finally`: close session, `reset_tenant_context()` to prevent leak
- [x] **T4 — Schedule Trigger fan-out** (AC: #5)
  - [x] T4.1 `run_schedule_trigger_fanout(ctx)` — cron entrypoint
  - [x] T4.2 Requires `arq_redis` in `ctx` (arq injects automatically)
  - [x] T4.3 BYPASSRLS read via `AdminSessionLocal` enumerates all tenants (placeholder query — Epic 5 refines)
  - [x] T4.4 For each tenant: `pool.enqueue_job("schedule_trigger_per_tenant", _tenant_id=str(tid))`
  - [x] T4.5 Stashes enqueued jobs on `ctx["enqueued_jobs"]` for test inspection
  - [x] T4.6 Registered in `cron_jobs` list (placeholder `hour={0}` schedule — Epic 5 refines)
- [x] **T5 — WorkerConfig dataclass** (AC: #1)
  - [x] T5.1 `functions`, `redis_settings` (from `settings.redis_url`), `cron_jobs_list`, `max_jobs`, `job_timeout`
  - [x] T5.2 `build_worker(**overrides)` returns configured `arq.Worker`
- [x] **T6 — Tests: AD-10 holds** (AC: all)
  - [x] T6.1 `tests/integration/test_arq_tenant_context.py` — 11 tests
  - [x] T6.2 `test_enqueue_captures_tenant_id_from_contextvar` — payload inspection via redis (AC2)
  - [x] T6.3 `test_enqueue_without_tenant_context_raises` — fail-fast (AC4 enqueue side)
  - [x] T6.4 `test_enqueue_rejects_explicit_tenant_id_kwarg` — reserved key enforcement
  - [x] T6.5 `test_tenant_aware_job_re_sets_contextvar` — contextvar re-hydration (AC3)
  - [x] T6.6 `test_tenant_aware_job_missing_tenant_id_raises` — corrupt payload (AC4 worker side)
  - [x] T6.7 `test_tenant_aware_job_invalid_uuid_raises` — corrupt UUID format
  - [x] T6.8 `test_tenant_aware_job_enforces_rls_on_users` — RLS isolation holds inside the job (AC3 load-bearing)
  - [x] T6.9 `test_schedule_fan_out_enqueues_per_tenant_jobs` — fan-out pattern (AC5)
  - [x] T6.10 `test_schedule_fan_out_requires_pool_in_ctx` — defensive error
  - [x] T6.11 `test_e2e_worker_runs_job_with_correct_tenant_context` — REAL arq Worker + Redis + Postgres, two back-to-back jobs, no leak (AC6, AD-10 load-bearing)
  - [x] T6.12 `test_e2e_corrupt_payload_marks_job_failed` — real Worker fails the job on missing `_tenant_id` (AC4 end-to-end)
- [x] **T7 — Apply migration + run tests (green)** (AC: all)
  - [x] T7.1 `alembic upgrade head` against `vaic_17` succeeded (reuses Story 1.2 migration — no schema changes in 1.7)
  - [x] T7.2 `uv run pytest` → **29 passed** (18 prior + 11 new)
  - [x] T7.3 `uv run ruff check app tests alembic` → **All checks passed!**
- [x] **T8 — Definition of Done evidence** (AC: all)
  - [x] T8.1 Test evidence: `tests/integration/test_arq_tenant_context.py:359` test_e2e_worker_runs_job_with_correct_tenant_context PASSED; full output 29/29 in 5.55s
  - [x] T8.2 Production code reference: `backend/app/core/jobs.py:109-142` (enqueue_job_with_context), `backend/app/core/jobs.py:150-213` (@tenant_aware_job), `backend/app/core/jobs.py:221-269` (run_schedule_trigger_fanout), `backend/app/core/jobs.py:279-287` (cron_jobs registry)

## Dev Notes

### Scope Boundaries — CRITICAL

**Story 1.7 is the background-job foundation. Do NOT implement:**
- Concrete domain jobs (Workflow Run, Schedule Trigger query logic, Event Trigger) → **Epics 3 & 5**
- FastAPI middleware to set `tenant_context` from JWT → **Story 1.3**
- Port interfaces (`AuditPort`, `LlmPort`, `McpClientPort`) → **Story 1.4**
- Audit sink writes → **Story 1.5**
- `app/main.py` worker startup wiring → **Coordinator (Stories 1.3 + 1.4 are touching it)**
- Any alembic migrations → 1.7 has no DB changes (reuses 1.2 schema)
- Frontend

### Architecture Compliance

**AD-10 — Tenant context materialized in job payloads and re-set at worker entry** (the load-bearing invariant for this story):
- Enqueue path captures `tenant_context.get()` and serializes as `_tenant_id` in arq kwargs
- Worker entry: `@tenant_aware_job` decorator re-sets contextvar, opens session, sets RLS var
- Schedule Triggers fan out per-tenant from a single `cron_jobs` entrypoint under BYPASSRLS
- "Never assume a worker inherits context from anywhere" — divergence-1 design constraint

**AD-2 — Multi-tenant isolation at the data layer via Postgres RLS** (interplay):
- The worker session MUST drop superuser privileges via `SET LOCAL ROLE <app_db_role>` when the runtime `database_url` authenticates as a Postgres superuser (the dev/test default).
- This is governed by `settings.app_db_role` (default `""` → no role switch; production uses a non-superuser DSN directly).
- Without this role switch, RLS policies are silently bypassed because `vaic` (docker postgres default user) has implicit BYPASSRLS even with FORCE ROW LEVEL SECURITY.
- The same pattern is used in Story 1.2's tests via the `_as_app(session, tenant_id)` helper.

**AD-9 — Schedule Triggers fan out per-tenant from a single cron_jobs entrypoint**:
- `run_schedule_trigger_fanout` is registered in `cron_jobs`
- Uses `AdminSessionLocal` (BYPASSRLS) for the single sanctioned runtime cross-tenant read
- Per-tenant enqueues bypass `enqueue_job_with_context` (cron has no contextvar set) and call `pool.enqueue_job` directly with `_tenant_id` materialized

**AR-14 — Consistency Conventions** (relevant slices):
- Async jobs: "arq only — both Schedule Triggers (via `cron_jobs`) and background Workflow Run execution. No Celery, no APScheduler, no background threads for domain work."
- Background jobs: "Tenant context is materialized in job kwargs at enqueue time; the worker re-sets contextvar + DB session var at entry (AD-10). Schedule Triggers fan out per-tenant from a single `cron_jobs` entrypoint."

**Convention — Tenant context** (extended for arq):
- HTTP path: FastAPI middleware sets the contextvar (Story 1.3)
- Background path: `@tenant_aware_job` re-sets contextvar from `_tenant_id` in the payload (this story)
- Schedule Trigger path: BYPASSRLS read + per-tenant enqueue loop (this story)
- Domain code reads `tenant_context.get()` — never pass `tenant_id` as a function argument

### Library/Framework Requirements

- **arq 0.28.0** (latest): `arq.connections.create_pool()` for client; `arq.worker.Worker` for worker; `arq.cron.cron()` for cron entries.
- Worker function signature: `async def fn(ctx, **kwargs)` — `ctx` is a dict populated by arq with `arq_redis`, `job_id`, `job_try`, etc.
- `Worker.run_check(retry_jobs=None, max_burst_jobs=None)` — async coroutine that runs the worker until the queue is drained, then raises `FailedJobs` if any job failed. Perfect for tests.
- arq serializes jobs with msgpack if available, else **pickle**. Our test environment does not install msgpack → pickle is used. The job payload keys in the serialized dict are `t` (try), `f` (function name), `a` (args, always empty for us), `k` (kwargs), `et` (enqueue_time). Tests use pickle for payload inspection.
- Cron jobs expose the coroutine under `.coroutine` (NOT `.func`) and name under `.name` (auto-prefixed with `cron:`).

### File Structure Changes

```
backend/
├── .env                                  # NEW (story-local test config)
├── app/
│   └── core/
│       └── jobs.py                       # NEW — WorkerConfig, enqueue_job_with_context,
│                                          #         @tenant_aware_job, cron_jobs,
│                                          #         MissingTenantContextError,
│                                          #         run_schedule_trigger_fanout
└── tests/
    └── integration/
        └── test_arq_tenant_context.py    # NEW — 11 AD-10 tests
```

### Testing Requirements

- **Real Redis (localhost:6379/0)** and **real Postgres (vaic_17)** required — no fakes.
- Tests flush the redis DB before AND after each test to ensure isolation.
- The e2e test (`test_e2e_worker_runs_job_with_correct_tenant_context`) is the load-bearing AD-10 proof: real `arq.Worker`, real `create_pool`, real pickle-serialized payloads, real RLS queries.
- Pickle is used for payload inspection (arq's default serializer when msgpack isn't installed).

### Anti-Patterns Avoided

1. **Do NOT assume contextvars propagate across `loop.run_in_executor`.** Python's `contextvars` propagate across `asyncio.create_task` boundaries but NOT to `ThreadPoolExecutor` threads. Tests capture the tenant_id in the async task BEFORE calling `run_in_executor`.
2. **Do NOT skip the `SET LOCAL ROLE` step in the worker.** Dev/test environments connect as a Postgres superuser, which silently bypasses RLS even with `FORCE ROW LEVEL SECURITY`. The decorator checks `settings.app_db_role` and issues `SET LOCAL ROLE` if set.
3. **Do NOT enqueue cron-fan-out jobs via `enqueue_job_with_context`.** The cron path has no contextvar set — bypassing the safe enqueue is correct there. `_tenant_id` is materialized directly into the payload.
4. **Do NOT return `None` for "queue full" silently.** arq's `enqueue_job` returns `None` if a job with the same ID is already queued (dedup). The cron fan-out preserves this contract but exposes enqueued jobs on `ctx["enqueued_jobs"]` for inspection.
5. **Do NOT let the wrapped function see `_tenant_id` in kwargs.** The decorator `pop`s the key — domain code must never accidentally depend on it.
6. **Do NOT reset the contextvar without closing the session.** Order in `finally`: close session first, then reset contextvar. Otherwise an in-flight query could lose its RLS context mid-flight.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-1.7 L509–L528] ACs verbatim
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-10] Tenant context materialization (load-bearing)
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-2] RLS invariant (interplay)
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-9] App Events + Schedule Triggers
- [Source: ARCHITECTURE-SPINE/divergence-1-tenant-contextvar-does-not-survive-the-arq-worker-boundary.md] Divergence design
- [Source: ARCHITECTURE-SPINE/divergence-2-schedule-trigger-fires-without-tenant-context.md] Fan-out design
- [Source: ARCHITECTURE-SPINE/consistency-conventions.md#async-jobs] arq-only convention
- [Source: _bmad-output/implementation-artifacts/1-2-multi-tenant-data-layer-postgres-rls.md] Story 1.2 (dependency, baseline)

## Dev Agent Record

### Agent Model Used

Claude (via Claude Code, glm-5.2[1m] backend session)

### Debug Log References

- **arq uses pickle, not msgpack, when msgpack is not installed**: discovered by enqueueing a job and scanning redis keys (`arq:job:<job_id>` prefix). The serialized payload dict has keys `t` (try), `f` (function name), `a` (args tuple), `k` (kwargs dict), `et` (enqueue_time). Tests use `pickle.loads()` for inspection. msgpack would have used different key names. Caught during TDD red phase.
- **`contextvars.ContextVar` does NOT propagate to `ThreadPoolExecutor` threads**: confirmed via a minimal repro (`asyncio.run(run_in_executor(...))` with a contextvar set on the async task). The executor thread sees the default. Tests capture the tenant_id in the async task BEFORE calling `run_in_executor`, and rely on the decorator having already set the RLS session var on the session's connection (which IS thread-safe — it's just a SQL `set_config` call scoped to the transaction).
- **`vaic` superuser silently bypasses RLS even with FORCE ROW LEVEL SECURITY**: discovered during TDD when `test_tenant_aware_job_enforces_rls_on_users` returned both tenants' rows. Postgres superusers have implicit BYPASSRLS that cannot be revoked. The fix: the decorator issues `SET LOCAL ROLE <app_db_role>` when `settings.app_db_role` is non-empty, mirroring the pattern from Story 1.2's `_as_app()` test helper. Production deployments using a non-superuser DSN leave `app_db_role=""` and skip the role switch (already subject to RLS).
- **`CronJob.coroutine` not `CronJob.func`**: arq 0.28.0 stores the cron function under `.coroutine`, not `.func`. Caught during TDD when `entry.func` raised `AttributeError`. Verified via `dir(CronJob)`.
- **arq `Worker` uses `coroutine.__qualname__` for function name lookup**: the test fixture `_capture_users` defined at module level registers as `_capture_users` (qualname). Tests pass `arq_func(_capture_users, name="_capture_users")` explicitly to be safe.
- **`run_check` raises `FailedJobs` if any job raised**: perfect for the corrupt-payload test — `pytest.raises(Exception, match="MissingTenantContextError|missing")` catches it. The match pattern accounts for arq's wrapping of the original exception.
- **29/29 tests green** in 5.55s; ruff clean; no DB migration needed (reuses Story 1.2 schema).

### Completion Notes List

- **AC1 ✅**: `WorkerConfig.build_worker()` (jobs.py:317-328) constructs a working `arq.Worker` connected to `settings.redis_url`. The e2e test starts it, runs jobs, asserts results.
- **AC2 ✅**: `enqueue_job_with_context()` (jobs.py:109-142) reads `tenant_context.get()`, serializes as `_tenant_id`. `test_enqueue_captures_tenant_id_from_contextvar` inspects the redis payload and asserts the value round-tripped.
- **AC3 ✅**: `@tenant_aware_job` decorator (jobs.py:150-213) re-sets contextvar + opens session + sets RLS var + drops role. `test_tenant_aware_job_enforces_rls_on_users` queries `users` and asserts only the materialized tenant's rows are returned — the load-bearing RLS proof.
- **AC4 ✅**: Two failure paths. Enqueue side: `enqueue_job_with_context` raises `MissingTenantContextError` if contextvar is `None` (`test_enqueue_without_tenant_context_raises`). Worker side: `@tenant_aware_job` raises on missing or invalid `_tenant_id` (`test_tenant_aware_job_missing_tenant_id_raises`, `test_tenant_aware_job_invalid_uuid_raises`). End-to-end: `test_e2e_corrupt_payload_marks_job_failed` confirms the real Worker marks the job failed.
- **AC5 ✅**: `run_schedule_trigger_fanout` (jobs.py:221-269) runs under BYPASSRLS via `AdminSessionLocal`, enumerates tenants, enqueues one per-tenant job with materialized `_tenant_id`. Registered in `cron_jobs`. `test_schedule_fan_out_enqueues_per_tenant_jobs` verifies two distinct materialized tenant_ids.
- **AC6 ✅**: `test_e2e_worker_runs_job_with_correct_tenant_context` (the load-bearing test) enqueues TenantA's job, immediately enqueues TenantB's job, resets the caller's contextvar, runs the Worker, and asserts each job saw only its own tenant's rows.
- **AC7 ✅**: Only arq is used (`pyproject.toml` deps: `arq>=0.26`, `redis>=5.2`). No Celery, APScheduler, or background threads in `jobs.py` or any domain code. `loop.run_in_executor(None, ...)` is used ONLY to bridge sync SQLAlchemy inside the async worker — this is the sanctioned pattern per AR-13 (sync SQLAlchemy) and is not a domain-work thread.
- **Scope discipline**: No concrete domain jobs (Workflow Run, Schedule/Event Trigger logic), no auth middleware, no port interfaces, no audit writes, no main.py wiring, no DB migrations, no frontend.
- **DoD**: test evidence (`tests/integration/test_arq_tenant_context.py:359` PASSED, 29 tests in 5.55s), production code reference (`backend/app/core/jobs.py`).

### File List

**Created (new):**
- `backend/app/core/jobs.py` — `MissingTenantContextError`, `TENANT_ID_KWARG`, `enqueue_job_with_context()`, `@tenant_aware_job` decorator, `run_schedule_trigger_fanout()`, `cron_jobs` registry, `WorkerConfig` dataclass
- `backend/tests/integration/test_arq_tenant_context.py` — 11 AD-10 tests (8 unit-level + 3 end-to-end via real arq Worker)
- `backend/.env` — story-local test env (VAIC_DATABASE_URL=vaic_17, VAIC_APP_DB_ROLE=vaic_app)

**Modified (existing):**
- None. `tenant_context.py`, `db.py`, `settings.py`, `ids.py`, `main.py`, alembic migrations, frontend — all untouched per scope rules.

**Auto-generated (git-ignored):**
- `backend/.venv/`, `backend/uv.lock` (unchanged policy from Story 1.1)

## Change Log

- 2026-07-17: Story 1.7 spec authored. Status: ready-for-dev → in-progress.
- 2026-07-17: Story 1.7 implementation complete — 29/29 tests green, ruff clean. Status: in-progress → review.
