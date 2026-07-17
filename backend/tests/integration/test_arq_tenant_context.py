"""AD-10 — arq tenant-context rehydration across worker boundary.

Proves:
- `enqueue_job_with_context()` materializes `tenant_context.get()` into `_tenant_id`.
- `@tenant_aware_job` re-sets contextvar + DB RLS session var at worker entry.
- Enqueue without context fails fast (`MissingTenantContextError`).
- Worker corrupt payload (missing `_tenant_id` mid-flight) fails the job.
- Schedule Trigger fan-out: cron entrypoint runs under BYPASSRLS, enqueues
  one per-tenant job with materialized `_tenant_id`.
- End-to-end: a real arq Worker picks up a job, runs it under correct
  tenant context, RLS isolation holds, and two back-to-back jobs from
  different tenants do not leak context.

Real Redis (localhost:6379/0) and Postgres (vaic_17) are required.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from arq import Worker, create_pool
from arq import func as arq_func
from arq.connections import ArqRedis, RedisSettings
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import AdminSessionLocal
from app.core.jobs import (
    MissingTenantContextError,
    cron_jobs,
    enqueue_job_with_context,
    run_schedule_trigger_fanout,
    tenant_aware_job,
)
from app.core.tenant_context import reset_tenant_context, set_tenant_context, tenant_context
from app.modules.tenant.models import Department, Tenant, User

# Use the configured redis URL's db (0 in dev).
_REDIS_URL = "redis://localhost:6379/0"


def _redis() -> RedisSettings:
    return RedisSettings.from_dsn(_REDIS_URL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_two_tenants() -> dict[str, uuid.UUID]:
    """Seed two tenants + departments + users via the admin (BYPASSRLS) engine.

    Returns a dict of UUIDs. Idempotent: wipes prior rows first.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    dept_a = uuid.uuid4()
    dept_b = uuid.uuid4()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    with AdminSessionLocal() as s:
        s.execute(text("DELETE FROM users"))
        s.execute(text("DELETE FROM departments"))
        s.execute(text("DELETE FROM tenants"))
        s.commit()

        s.add(Tenant(id=tenant_a, name="Tenant A"))
        s.add(Tenant(id=tenant_b, name="Tenant B"))
        s.flush()
        s.add(Department(id=dept_a, tenant_id=tenant_a, name="Credit"))
        s.add(Department(id=dept_b, tenant_id=tenant_b, name="HR"))
        s.flush()
        s.add(
            User(
                id=user_a,
                tenant_id=tenant_a,
                department_id=dept_a,
                email="alice@tenanta.example",
                role="admin",
            )
        )
        s.add(
            User(
                id=user_b,
                tenant_id=tenant_b,
                department_id=dept_b,
                email="bob@tenantb.example",
                role="admin",
            )
        )
        s.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "dept_a": dept_a,
        "dept_b": dept_b,
        "user_a": user_a,
        "user_b": user_b,
    }


@pytest.fixture()
def seed() -> dict[str, uuid.UUID]:
    """Per-test seed — wipes and reseeds."""
    return _seed_two_tenants()


@pytest.fixture()
def _clean_tenant_context() -> Iterator[None]:
    """Ensure no leaked contextvar between tests."""
    reset_tenant_context()
    yield
    reset_tenant_context()


@pytest.fixture()
async def pool() -> Iterator[ArqRedis]:
    """Real arq redis pool, cleaned up after the test."""
    import redis.asyncio as aioredis

    # flush before so leftover jobs don't interfere
    r = aioredis.from_url(_REDIS_URL)
    await r.flushdb()
    await r.aclose()

    p = await create_pool(_redis())
    try:
        yield p
    finally:
        await p.aclose()
        r = aioredis.from_url(_REDIS_URL)
        await r.flushdb()
        await r.aclose()


# ---------------------------------------------------------------------------
# Unit-level ACs — enqueue + decorator mechanics
# ---------------------------------------------------------------------------


async def test_enqueue_captures_tenant_id_from_contextvar(
    pool: ArqRedis, seed: dict[str, uuid.UUID], _clean_tenant_context: None
) -> None:
    """enqueue_job_with_context reads tenant_context and injects `_tenant_id`."""
    set_tenant_context(seed["tenant_a"])
    job = await enqueue_job_with_context(pool, "test_probe", foo="bar")

    assert job is not None
    # Inspect the serialized payload in Redis to confirm `_tenant_id` round-tripped.
    import pickle  # noqa: S403 — test-only, our own payload

    import redis.asyncio as aioredis

    r = aioredis.from_url(_REDIS_URL)
    try:
        raw = await r.get(f"arq:job:{job.job_id}")
        assert raw is not None
        payload = pickle.loads(raw)  # noqa: S301 — test
        assert payload["k"]["_tenant_id"] == str(seed["tenant_a"])
        assert payload["k"]["foo"] == "bar"
    finally:
        await r.aclose()


async def test_enqueue_without_tenant_context_raises(
    pool: ArqRedis, _clean_tenant_context: None
) -> None:
    """No tenant in contextvar → MissingTenantContextError at enqueue time."""
    assert tenant_context.get() is None
    with pytest.raises(MissingTenantContextError):
        await enqueue_job_with_context(pool, "test_probe", x=1)


async def test_enqueue_rejects_explicit_tenant_id_kwarg(
    pool: ArqRedis, seed: dict[str, uuid.UUID], _clean_tenant_context: None
) -> None:
    """`_tenant_id` is reserved — explicit pass-through is a programmer error."""
    set_tenant_context(seed["tenant_a"])
    with pytest.raises(ValueError, match="_tenant_id"):
        await enqueue_job_with_context(pool, "p", _tenant_id="xyz")


# ---------------------------------------------------------------------------
# Decorator mechanics — re-set contextvar + DB session var
# ---------------------------------------------------------------------------


async def test_tenant_aware_job_re_sets_contextvar(seed: dict[str, uuid.UUID]) -> None:
    """Inside a decorated job, `tenant_context.get()` returns the materialized UUID."""
    captured: dict[str, Any] = {}

    @tenant_aware_job
    async def probe(ctx: dict[str, Any], **kwargs: Any) -> str:
        # Contextvar is set on the async task — safe to read here.
        captured["tenant_id"] = tenant_context.get()
        captured["kwargs"] = kwargs
        return "ok"

    reset_tenant_context()
    result = await probe({}, _tenant_id=str(seed["tenant_a"]), extra=1)
    assert result == "ok"
    assert captured["tenant_id"] == seed["tenant_a"]
    assert captured["kwargs"]["extra"] == 1


async def test_tenant_aware_job_missing_tenant_id_raises() -> None:
    """Corrupt payload (no `_tenant_id`) → MissingTenantContextError at entry."""

    @tenant_aware_job
    async def probe(ctx: dict[str, Any], **kwargs: Any) -> str:
        return "should-not-reach"

    reset_tenant_context()
    with pytest.raises(MissingTenantContextError):
        await probe({}, something="but-no-tenant")


async def test_tenant_aware_job_invalid_uuid_raises() -> None:
    """Corrupt `_tenant_id` (not a UUID) → MissingTenantContextError at entry."""

    @tenant_aware_job
    async def probe(ctx: dict[str, Any], **kwargs: Any) -> str:
        return "should-not-reach"

    reset_tenant_context()
    with pytest.raises(MissingTenantContextError):
        await probe({}, _tenant_id="not-a-uuid")


async def test_tenant_aware_job_enforces_rls_on_users(
    seed: dict[str, uuid.UUID],
) -> None:
    """Inside the job, SELECT against users returns only the materialized tenant's rows.

    The decorator sets the DB session var on `ctx["session"]`. We query
    via that session inside `loop.run_in_executor`, capturing the tenant_id
    in the async task BEFORE entering the executor (contextvars do not
    propagate to executor threads).
    """
    seen_emails: list[str] = []

    @tenant_aware_job
    async def probe(ctx: dict[str, Any], **kwargs: Any) -> None:
        from app.core.tenant_context import tenant_context as _tc
        from app.modules.tenant.models import User

        session: Session = ctx["session"]
        # Capture tenant_id in the async task BEFORE going to executor.
        tid = _tc.get()
        assert tid is not None
        loop = asyncio.get_running_loop()

        def _q() -> list[str]:
            # We are on an executor thread; the session already has the
            # RLS var set on its connection (transaction-scoped).
            rows = session.execute(select(User)).scalars().all()
            return [r.email for r in rows]

        emails = await loop.run_in_executor(None, _q)
        seen_emails.extend(emails)

    reset_tenant_context()
    await probe({}, _tenant_id=str(seed["tenant_a"]))
    assert seen_emails == ["alice@tenanta.example"]

    reset_tenant_context()
    seen_emails.clear()
    await probe({}, _tenant_id=str(seed["tenant_b"]))
    assert seen_emails == ["bob@tenantb.example"]


# ---------------------------------------------------------------------------
# Schedule Trigger fan-out — BYPASSRLS enumerate + per-tenant enqueue
# ---------------------------------------------------------------------------


async def test_schedule_fan_out_enqueues_per_tenant_jobs(
    pool: ArqRedis, seed: dict[str, uuid.UUID], _clean_tenant_context: None
) -> None:
    """The cron entrypoint runs under BYPASSRLS, enumerates tenants, enqueues one job each."""
    assert len(cron_jobs) >= 1, "cron_jobs must register at least one entry"
    entry = cron_jobs[0]
    # arq CronJob exposes the coroutine under `.coroutine` and name under `.name`.
    cron_fn = entry.coroutine

    # Pass the pool via the arq-standard `arq_redis` ctx key. The function
    # also stashes enqueued jobs under `enqueued_jobs` for test inspection.
    ctx: dict[str, Any] = {"arq_redis": pool, "enqueued_jobs": []}
    await cron_fn(ctx)

    enqueued = ctx["enqueued_jobs"]
    # Two tenants seeded → two per-tenant jobs enqueued.
    assert len(enqueued) == 2
    # Inspect enqueued payload via redis.
    import redis.asyncio as aioredis

    r = aioredis.from_url(_REDIS_URL)
    try:
        tenant_ids_seen: set[str] = set()
        import pickle  # noqa: S403 — test

        for job in enqueued:
            raw = await r.get(f"arq:job:{job.job_id}")
            assert raw is not None, f"job {job.job_id} missing from redis"
            payload = pickle.loads(raw)  # noqa: S301 — test
            tid = payload["k"].get("_tenant_id")
            assert tid is not None
            tenant_ids_seen.add(tid)
        assert str(seed["tenant_a"]) in tenant_ids_seen
        assert str(seed["tenant_b"]) in tenant_ids_seen
    finally:
        await r.aclose()


async def test_schedule_fan_out_requires_pool_in_ctx() -> None:
    """The cron function fails clearly if the arq pool is missing from ctx."""
    with pytest.raises(RuntimeError, match="arq_redis"):
        await run_schedule_trigger_fanout({})


# ---------------------------------------------------------------------------
# End-to-end — real arq Worker, real Redis, real Postgres
# ---------------------------------------------------------------------------


@tenant_aware_job
async def _capture_users(ctx: dict[str, Any], **kwargs: Any) -> str:
    """Test fixture job — returns JSON {tenant_id, emails} for assertion."""
    from app.core.tenant_context import tenant_context as _tc
    from app.modules.tenant.models import User

    session: Session = ctx["session"]
    tid = _tc.get()
    assert tid is not None
    loop = asyncio.get_running_loop()

    def _q() -> list[str]:
        rows = session.execute(select(User)).scalars().all()
        return [r.email for r in rows]

    emails = await loop.run_in_executor(None, _q)
    return json.dumps({"tenant_id": str(tid), "emails": emails})


@tenant_aware_job
async def _probe_no_tenant(ctx: dict[str, Any], **kwargs: Any) -> str:
    """Job that should never execute its body — used for corrupt payload test."""
    return "should-not-reach"


async def test_e2e_worker_runs_job_with_correct_tenant_context(
    seed: dict[str, uuid.UUID], _clean_tenant_context: None
) -> None:
    """The load-bearing AD-10 test.

    Start a real arq Worker, enqueue a job under TenantA's context, wait for
    completion, and assert the job saw only TenantA's rows. Then repeat for
    TenantB and confirm no leak.
    """
    import redis.asyncio as aioredis

    r = aioredis.from_url(_REDIS_URL)
    await r.flushdb()
    await r.aclose()

    p = await create_pool(_redis())
    try:
        # Enqueue under TenantA's context
        set_tenant_context(seed["tenant_a"])
        job_a = await enqueue_job_with_context(p, "_capture_users")
        assert job_a is not None

        # Enqueue under TenantB's context — back-to-back, no leak
        set_tenant_context(seed["tenant_b"])
        job_b = await enqueue_job_with_context(p, "_capture_users")
        assert job_b is not None

        # Reset caller context — workers must NOT inherit
        reset_tenant_context()

        # Run worker to completion (burst mode). Register the function by name.
        worker = Worker(
            functions=[arq_func(_capture_users, name="_capture_users")],
            redis_settings=_redis(),
            burst=True,
            max_jobs=2,
            job_timeout=30,
            max_tries=1,
        )
        await worker.run_check()

        res_a = await job_a.result(timeout=5)
        res_b = await job_b.result(timeout=5)

        data_a = json.loads(res_a)
        data_b = json.loads(res_b)

        assert data_a["tenant_id"] == str(seed["tenant_a"])
        assert data_a["emails"] == ["alice@tenanta.example"]
        assert data_b["tenant_id"] == str(seed["tenant_b"])
        assert data_b["emails"] == ["bob@tenantb.example"]
    finally:
        await p.aclose()
        r = aioredis.from_url(_REDIS_URL)
        await r.flushdb()
        await r.aclose()


async def test_e2e_corrupt_payload_marks_job_failed(
    seed: dict[str, uuid.UUID], _clean_tenant_context: None
) -> None:
    """A job enqueued without `_tenant_id` (simulated corrupt payload) fails
    with MissingTenantContextError at worker entry.
    """
    import redis.asyncio as aioredis

    r = aioredis.from_url(_REDIS_URL)
    await r.flushdb()
    await r.aclose()

    p = await create_pool(_redis())
    try:
        # Enqueue DIRECTLY (bypassing the safe enqueue path) — no _tenant_id.
        job = await p.enqueue_job("_probe_no_tenant")
        assert job is not None

        worker = Worker(
            functions=[arq_func(_probe_no_tenant, name="_probe_no_tenant")],
            redis_settings=_redis(),
            burst=True,
            max_jobs=1,
            job_timeout=10,
            max_tries=1,
        )
        with pytest.raises(Exception, match="MissingTenantContextError|missing"):
            await worker.run_check()
    finally:
        await p.aclose()
        r = aioredis.from_url(_REDIS_URL)
        await r.flushdb()
        await r.aclose()
