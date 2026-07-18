"""arq worker entrypoints — Workflow Run lifecycle (Story 3.2).

`run_workflow` — dispatched by `POST /workflows/{id}/runs`. Wrapped in
`@tenant_aware_job` (`app/core/jobs.py`) — the ESTABLISHED codebase idiom
— rather than the spec-literal raw `async def run_workflow(ctx, *, run_id,
tenant_id)`. The enqueue side calls `enqueue_job_with_context(pool,
"run_workflow", run_id=...)`, which materializes `_tenant_id`
automatically from `tenant_context.get()` (AD-10); the decorator pops it,
re-hydrates `tenant_context`, and stashes an RLS-scoped session on
`ctx["session"]`. This reuses Story 1.7's tenant-boundary machinery
instead of re-deriving it here.

`resume_orphaned_runs` — startup poller (AC8). Enumerates
`workflow_runs WHERE status='running'` under BYPASSRLS (crash recovery —
these Runs were mid-flight when a prior worker process died) and
re-enqueues each via the same `run_workflow` job name, materializing
`_tenant_id` directly (mirrors `run_schedule_trigger_fanout`'s fan-out
pattern in `app/core/jobs.py` — no caller contextvar exists in this
administrative sweep). The re-enqueue passes `resume=True` — a resumed
Run is ALREADY `status='running'` (that's the whole reason it's orphaned),
so `run_workflow` must skip the `pending -> running` CAS for this call and
proceed straight into the worker body instead of losing the CAS race and
silently abandoning the Run forever (the bug this kwarg fixes).

Story 3.2 proved CAS `pending -> running` then a stub `running ->
completed`. Story 3.3/3.4 replace that stub with `orchestrate_run` —
decomposition, Task dispatch, aggregation — imported from
`app.modules.orchestrator.service`. Do NOT inline that logic here (Dev
Notes "Scope Boundaries") — this module owns only the state-machine
skeleton + tenant/RLS bootstrap around it.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from arq.connections import ArqRedis
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from app.core.deps import assume_app_role
from app.core.jobs import TENANT_ID_KWARG, WorkerConfig, tenant_aware_job
from app.core.tenant_context import (
    set_tenant_context,
    set_tenant_session_var,
    tenant_context,
)
from app.modules.orchestrator.service import orchestrate_run
from app.modules.orchestrator.state import transition_and_audit

logger = logging.getLogger(__name__)

__all__ = ["run_workflow", "resume_orphaned_runs", "worker_config"]


def _transition(
    session: Any, tenant_id: uuid.UUID, run_id: str, from_status: str, to_status: str
) -> bool:
    """Re-apply `SET LOCAL ROLE` + tenant RLS var, then CAS + audit.

    `transition_and_audit` commits internally (each CAS is its own
    transaction) — Postgres `SET LOCAL` is transaction-scoped, so the role
    drop and `app.tenant_id` GUC set by `@tenant_aware_job` at job entry
    do NOT survive past that first commit. This helper re-applies both
    immediately before every subsequent statement on the same session
    within one job execution (AD-2/AD-10 correctness, not just at entry).

    Runs on a `run_in_executor` thread — `contextvars` set in the calling
    async task do NOT propagate to executor threads (unlike the asyncio
    Task itself). `transition_and_audit` -> `PostgresAuditSink.log()`
    reads `tenant_context.get()` directly, so it must be re-set HERE, on
    this thread, immediately before the call — not just passed as a plain
    argument.
    """
    set_tenant_context(tenant_id)
    assume_app_role(session)
    set_tenant_session_var(session, tenant_id)
    return transition_and_audit(
        session,
        kind="run",
        entity_id=run_id,
        run_id=run_id,
        from_status=from_status,
        to_status=to_status,
    )


@tenant_aware_job
async def run_workflow(ctx: dict[str, Any], *, run_id: str, resume: bool = False) -> None:
    """Worker entrypoint for a Run — CAS `pending -> running` (AC4, AC5).

    `resume=False` (default, fresh dispatch from `POST /runs`): the Run is
    `pending`; CAS `pending -> running` before proceeding. Losing the CAS
    race (rowcount==0) is a legitimate no-op — someone else already claimed
    it.

    `resume=True` (crash recovery, `resume_orphaned_runs`): the Run is
    ALREADY `running` — that's the definition of "orphaned". Attempting
    the `pending -> running` CAS here would always lose the race (the row
    is not `pending`) and silently abandon the Run forever. Skip straight
    to the worker body instead; no re-transition into `running` needed.
    """
    session = ctx["session"]
    tenant_id = tenant_context.get()
    if tenant_id is None:
        # Defensive — `@tenant_aware_job` always sets this before calling us.
        raise RuntimeError("run_workflow: tenant_context unset at job entry")
    loop = asyncio.get_running_loop()

    if not resume:
        won = await loop.run_in_executor(
            None, _transition, session, tenant_id, run_id, "pending", "running"
        )
        if not won:
            logger.debug("run_workflow: lost pending->running race run_id=%s", run_id)
            return

    # Story 3.3/3.4: decomposition, Task dispatch, aggregation. Runs directly
    # on the event loop (not `run_in_executor`) so the `tenant_context`
    # contextvar set above stays visible to `orchestrate_run`'s internal RLS
    # re-assertions (executor threads would NOT see it — see `_transition`).
    # Both the fresh-dispatch and `resume=True` paths funnel into this same
    # call — `decompose_run` is idempotent (skips Task creation if Tasks
    # already exist for `run_id`), so a resumed Run re-entering here never
    # duplicates its dispatched Tasks.
    await orchestrate_run(session, run_id)


async def resume_orphaned_runs(ctx: dict[str, Any]) -> None:
    """AC8 — startup poller. Re-enqueues Runs orphaned by a crashed worker.

    Runs under BYPASSRLS (`AdminSessionLocal`) to enumerate ACROSS
    tenants by design (Dev Notes anti-pattern #4) — then re-dispatches
    each orphaned Run through the normal `run_workflow` job path, which
    sets tenant context from the row's own materialized `tenant_id`
    before touching any Run-specific data.
    """
    # arq's real `Worker.run()` populates `ctx["redis"]` (see arq/worker.py
    # `self.ctx['redis'] = self.pool`), not `arq_redis` -- accept both so a
    # live worker process (real key) and existing tests (which stub the
    # `arq_redis` key directly) both work without duplicating fixtures.
    pool: ArqRedis | None = ctx.get("arq_redis") or ctx.get("redis")
    if pool is None:
        raise RuntimeError(
            "resume_orphaned_runs requires `arq_redis`/`redis` in ctx (arq "
            "injects `redis` automatically; tests must provide one of these)."
        )

    loop = asyncio.get_running_loop()

    def _find_orphaned() -> list[tuple[uuid.UUID, uuid.UUID]]:
        with AdminSessionLocal() as s:
            rows = s.execute(
                text("SELECT id, tenant_id FROM workflow_runs WHERE status='running'")
            ).fetchall()
            return [(row[0], row[1]) for row in rows]

    orphaned = await loop.run_in_executor(None, _find_orphaned)
    logger.info("resume_orphaned_runs: found %d orphaned Run(s)", len(orphaned))

    enqueued: list[Any] = []
    for run_id, tid in orphaned:
        job = await pool.enqueue_job(
            "run_workflow",
            run_id=str(run_id),
            resume=True,
            **{TENANT_ID_KWARG: str(tid)},
        )
        if job is not None:
            enqueued.append(job)
    ctx["enqueued_jobs"] = enqueued


# Bundled `arq.Worker` config for a real deployment entrypoint — pass
# `worker_config.build_worker(on_startup=resume_orphaned_runs)` to wire the
# AC8 poller into an actual `arq worker` process.
worker_config = WorkerConfig(functions=[run_workflow])
