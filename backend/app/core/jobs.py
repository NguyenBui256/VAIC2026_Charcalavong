"""arq background-job infrastructure — materializes tenant context (AD-10).

Story 1.7 delivers the worker bootstrap + job dispatch + tenant context
re-hydration. Concrete domain jobs (Workflow Run, Schedule Trigger, Event
Trigger) arrive in Epics 3 and 5.

AD-10 invariant
---------------
`contextvars.ContextVar` set by FastAPI middleware does **not** survive the
arq worker process boundary. This module provides:

- `enqueue_job_with_context()` — reads `tenant_context.get()`, serializes
  the value as `_tenant_id` in the arq job kwargs. Raises
  `MissingTenantContextError` immediately if no tenant is set.
- `@tenant_aware_job` decorator — wraps an `async def fn(ctx, **kwargs)`
  worker function. The decorator (1) pulls `_tenant_id` from kwargs
  (raising `MissingTenantContextError` on corrupt/missing payload),
  (2) re-sets the `tenant_context` contextvar, (3) opens a sync DB
  session, (4) issues `set_config('app.tenant_id', ...)` on that session,
  and (5) stashes the session on the arq `ctx` dict so the wrapped
  function can read via `ctx["session"]`.
- `cron_jobs` — list of arq cron entries. Story 1.7 ships one placeholder
  Schedule Trigger fan-out entrypoint (`run_schedule_trigger_fanout`)
  that runs under BYPASSRLS, enumerates tenants, and enqueues one
  per-tenant job with materialized `_tenant_id` for each. The actual
  schedule-query logic lands in Epic 5; the fan-out *pattern* is proven
  here.
- `WorkerConfig` — dataclass bundling the recommended `Worker` kwargs
  (functions list, redis settings, etc.) so Stories 3+/5+ can build a
  worker uniformly.
- `MissingTenantContextError` — structured error raised at enqueue time
  AND at worker entry when tenant context is missing.

Test coverage: see `tests/integration/test_arq_tenant_context.py`.
"""

from __future__ import annotations

import functools
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from arq.connections import ArqRedis, RedisSettings
from arq.cron import cron
from sqlalchemy import select, text

from app.core.db import AdminSessionLocal, SessionLocal
from app.core.settings import get_settings
from app.core.tenant_context import (
    reset_tenant_context,
    set_tenant_context,
    set_tenant_session_var,
    tenant_context,
)
from app.modules.tenant.models import Tenant

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

__all__ = [
    "MissingTenantContextError",
    "WorkerConfig",
    "cron_jobs",
    "enqueue_job_with_context",
    "run_schedule_trigger_fanout",
    "tenant_aware_job",
]

_logger = logging.getLogger(__name__)

# Kwarg key used to serialize `tenant_id` into the arq payload.
TENANT_ID_KWARG = "_tenant_id"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MissingTenantContextError(RuntimeError):
    """Raised when tenant context is missing at a critical point.

    - At enqueue time (`enqueue_job_with_context`): the caller's
      `tenant_context` contextvar is `None` — the calling code forgot to
      run inside FastAPI middleware scope, or called from a cron path
      without first setting context.
    - At worker entry (`@tenant_aware_job`): the deserialized job payload
      is missing the `_tenant_id` key. Indicates either a corrupt
      payload or a job enqueued via a path that bypassed
      `enqueue_job_with_context`.
    """

    def __init__(self, where: str) -> None:
        super().__init__(
            f"Missing tenant context ({where}). Background jobs require a "
            f"materialized `{TENANT_ID_KWARG}` kwarg — see AD-10."
        )
        self.where = where


# ---------------------------------------------------------------------------
# Enqueue path — materialize contextvar into payload
# ---------------------------------------------------------------------------


async def enqueue_job_with_context(
    pool: ArqRedis,
    job_name: str,
    *,
    job_id: str | None = None,
    _queue_name: str | None = None,
    **kwargs: Any,
) -> Any:
    """Enqueue an arq job with `tenant_context` materialized into kwargs.

    Reads `tenant_context.get()`; if `None`, raises `MissingTenantContextError`
    immediately (fail-fast at enqueue, not silently at worker entry). On
    success, the tenant UUID is serialized as the `_tenant_id` kwarg.

    Returns the `arq.jobs.Job` instance (or `None` if a job with the same
    id is already queued — arq's dedup contract).
    """
    tenant_id = tenant_context.get()
    if tenant_id is None:
        raise MissingTenantContextError("enqueue_job_with_context")
    if TENANT_ID_KWARG in kwargs:
        # Caller passed _tenant_id explicitly — refuse; we own this key.
        raise ValueError(
            f"`{TENANT_ID_KWARG}` is reserved for `enqueue_job_with_context` "
            "and may not be passed explicitly."
        )
    payload = {**kwargs, TENANT_ID_KWARG: str(tenant_id)}
    _logger.debug(
        "arq enqueue job_name=%s tenant_id=%s kwargs_keys=%s",
        job_name,
        tenant_id,
        sorted(kwargs.keys()),
    )
    return await pool.enqueue_job(job_name, _job_id=job_id, **payload)


# ---------------------------------------------------------------------------
# Worker path — decorator re-sets contextvar + DB RLS var
# ---------------------------------------------------------------------------


def tenant_aware_job(
    fn: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """Decorator: re-hydrate `tenant_context` and set DB RLS var at entry.

    Wraps an arq worker function with signature
    `async def fn(ctx, **kwargs) -> Any`. Before calling `fn`, the decorator:

    1. Reads `_tenant_id` from `kwargs`. If missing/empty → raise
       `MissingTenantContextError` (worker entry). arq will mark the job
       failed (AD-10 load-bearing).
    2. Sets `tenant_context` contextvar to the deserialized UUID.
    3. Opens a sync SQLAlchemy `SessionLocal()`, issues
       `set_config('app.tenant_id', ...)` on it, and stashes the session
       on `ctx["session"]`. The wrapped function reads via `ctx["session"]`.
    4. Commits/rolls back + closes the session after `fn` returns or raises.
    5. Resets `tenant_context` at exit so a subsequent job on the same
       worker task does not inherit context.

    The wrapped function NEVER receives `_tenant_id` in its visible kwargs
    — that key is consumed by the decorator.

    The wrapped function may run sync SQLAlchemy queries on `ctx["session"]`
    via `loop.run_in_executor` — sync driver inside async worker.
    """

    @functools.wraps(fn)
    async def wrapper(ctx: dict[str, Any], **kwargs: Any) -> Any:
        raw = kwargs.pop(TENANT_ID_KWARG, None)
        if not raw:
            raise MissingTenantContextError(f"worker entry:{fn.__name__}")
        try:
            tenant_id = uuid.UUID(str(raw))
        except (ValueError, TypeError) as e:
            raise MissingTenantContextError(
                f"worker entry:{fn.__name__} (invalid uuid: {raw!r})"
            ) from e

        set_tenant_context(tenant_id)
        session: Session = SessionLocal()
        ctx = {**ctx, "session": session}
        try:
            # Drop superuser privileges if configured. The runtime DB role
            # (e.g. `vaic_app`) is NOBYPASSRLS — required for RLS policies
            # to bite. If `database_url` already authenticates as a
            # non-superuser, leave `app_db_role` empty (SET LOCAL ROLE is
            # a no-op then).
            role = get_settings().app_db_role
            if role:
                session.execute(text(f"SET LOCAL ROLE {role}"))
            # set_config('app.tenant_id', ..., true) — must run inside txn
            set_tenant_session_var(session, tenant_id)
            return await fn(ctx, **kwargs)
        except Exception:
            session.rollback()
            raise
        finally:
            try:
                session.close()
            except Exception:  # noqa: BLE001
                _logger.exception("session.close() failed during worker teardown")
            reset_tenant_context()

    return wrapper


# ---------------------------------------------------------------------------
# Schedule Trigger fan-out (BYPASSRLS enumerate + per-tenant enqueue)
# ---------------------------------------------------------------------------


async def run_schedule_trigger_fanout(ctx: dict[str, Any]) -> None:
    """Cron entrypoint — enumerate tenants, enqueue one job per tenant.

    Runs under BYPASSRLS using `AdminSessionLocal` (the only sanctioned
    runtime BYPASSRLS read path per AD-9 Rule addition). For each tenant
    found, enqueues a per-tenant job named `schedule_trigger_per_tenant`
    with materialized `_tenant_id`.

    Story 1.7 ships only the fan-out *skeleton* — the actual
    schedule_triggers row query lands in Epic 5. The skeleton enumerates
    ALL active tenants (placeholder for "tenants with due schedules").

    The job dispatch target (`schedule_trigger_per_tenant`) is registered
    by Epic 5; Story 1.7 only proves the fan-out pattern. Tests verify
    that two enqueued jobs carry distinct materialized tenant_ids.
    """
    pool: ArqRedis | None = ctx.get("arq_redis")
    if pool is None:
        raise RuntimeError(
            "run_schedule_trigger_fanout requires `arq_redis` in ctx "
            "(arq injects this automatically; tests must provide it)."
        )

    # BYPASSRLS read: enumerate tenants. This is the single sanctioned
    # runtime cross-tenant read (AD-9 Rule addition).
    import asyncio

    loop = asyncio.get_running_loop()

    def _enum_tenants() -> list[uuid.UUID]:
        with AdminSessionLocal() as s:
            rows = s.execute(select(Tenant.id)).scalars().all()
            return [uuid.UUID(str(r)) for r in rows]

    tenant_ids = await loop.run_in_executor(None, _enum_tenants)
    _logger.info("schedule fan-out enumerated %d tenants", len(tenant_ids))

    enqueued: list[Any] = []
    for tid in tenant_ids:
        # Per-tenant enqueue — materialize `_tenant_id` directly. We bypass
        # `enqueue_job_with_context` because cron has no contextvar set.
        job = await pool.enqueue_job(
            "schedule_trigger_per_tenant",
            **{TENANT_ID_KWARG: str(tid)},
        )
        if job is not None:
            enqueued.append(job)
    # Expose the list for test inspection; arq cron functions ignore return.
    ctx["enqueued_jobs"] = enqueued


# ---------------------------------------------------------------------------
# Cron jobs registry
# ---------------------------------------------------------------------------

# Placeholder for Epic 5. Registered now so the fan-out pattern is testable
# and so the WorkerConfig wiring is non-trivial. `run_at_startup=False`,
# so this never fires automatically during tests.
cron_jobs = [
    cron(
        run_schedule_trigger_fanout,
        name="schedule_trigger_fanout",
        hour={0},  # daily at midnight — placeholder; Epic 5 refines
        run_at_startup=False,
        unique=True,
    ),
]


# ---------------------------------------------------------------------------
# Worker config bundle
# ---------------------------------------------------------------------------


def _redis_settings_from_url() -> RedisSettings:
    """Build RedisSettings from settings.redis_url."""
    return RedisSettings.from_dsn(get_settings().redis_url)


@dataclass
class WorkerConfig:
    """Recommended `arq.Worker` configuration.

    Stories 3+/5+ build the worker like:

        from app.core.jobs import WorkerConfig
        cfg = WorkerConfig(functions=[run_workflow, ...])
        worker = cfg.build_worker()
    """

    functions: list[Any] = field(default_factory=list)
    redis_settings: RedisSettings = field(default_factory=_redis_settings_from_url)
    cron_jobs_list: list[Any] = field(default_factory=lambda: list(cron_jobs))
    max_jobs: int = 10
    job_timeout: int = 300

    def build_worker(self, **overrides: Any) -> Any:
        """Construct an `arq.Worker` from this config."""
        from arq import Worker

        return Worker(
            functions=self.functions,
            redis_settings=self.redis_settings,
            cron_jobs=self.cron_jobs_list,
            max_jobs=self.max_jobs,
            job_timeout=self.job_timeout,
            **overrides,
        )
