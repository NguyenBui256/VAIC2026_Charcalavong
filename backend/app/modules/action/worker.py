"""ARQ worker — Action/Event dispatch.

`dispatch_action_events_fanout` (cron, BYPASSRLS) enumerates tenants that have
pending events OR dispatched-but-not-yet-completion-notified events, and enqueues
one per-tenant `process_tenant_action_events` job (mirrors run_schedule_trigger_fanout).

`process_tenant_action_events` (@tenant_aware_job) resolves bindings, creates +
enqueues WorkflowRun(s), creates notifications, and sweeps completed runs.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from arq.connections import ArqRedis
from arq.cron import cron
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from app.core.jobs import TENANT_ID_KWARG, enqueue_job_with_context, tenant_aware_job
from app.core.tenant_context import tenant_context
from app.modules.action.service import (
    claim_agent_task,
    dispatch_pending_events,
    finalize_agent_event,
    notify_completed_events,
)

logger = logging.getLogger(__name__)

__all__ = [
    "dispatch_action_events_fanout",
    "process_tenant_action_events",
    "run_agent_task",
    "action_cron_jobs",
]


async def dispatch_action_events_fanout(ctx: dict[str, Any]) -> None:
    """Cron entrypoint — enumerate tenants with work, enqueue one job per tenant."""
    pool: ArqRedis | None = ctx.get("arq_redis") or ctx.get("redis")
    if pool is None:
        raise RuntimeError("dispatch_action_events_fanout requires `arq_redis`/`redis` in ctx.")

    loop = asyncio.get_running_loop()

    def _tenants_with_work() -> list[uuid.UUID]:
        with AdminSessionLocal() as s:  # BYPASSRLS cross-tenant enumeration (AD-9)
            rows = s.execute(
                text(
                    "SELECT DISTINCT tenant_id FROM action_events "
                    "WHERE status = 'pending' "
                    "   OR (status = 'dispatched' AND completed_notified = false)"
                )
            ).scalars().all()
            return [uuid.UUID(str(r)) for r in rows]

    tenant_ids = await loop.run_in_executor(None, _tenants_with_work)
    if tenant_ids:
        logger.info("action dispatch fan-out: %d tenant(s) with work", len(tenant_ids))
    for tid in tenant_ids:
        # No caller contextvar in cron — materialize `_tenant_id` directly.
        await pool.enqueue_job("process_tenant_action_events", **{TENANT_ID_KWARG: str(tid)})


@tenant_aware_job
async def process_tenant_action_events(ctx: dict[str, Any]) -> None:
    """Per-tenant: dispatch pending events (+ enqueue runs), then completion sweep."""
    session = ctx["session"]
    tenant_id = tenant_context.get()
    if tenant_id is None:
        raise RuntimeError("process_tenant_action_events: tenant_context unset at entry")
    pool: ArqRedis | None = ctx.get("redis") or ctx.get("arq_redis")
    loop = asyncio.get_running_loop()

    # Sync DB work (create runs + notifications) on the executor thread.
    outcome = await loop.run_in_executor(
        None, dispatch_pending_events, session, tenant_id
    )

    # Enqueue each created workflow run + each agent task.
    if pool is not None:
        for run_id in outcome.run_ids:
            await enqueue_job_with_context(pool, "run_workflow", run_id=run_id)
        for task in outcome.agent_tasks:
            await enqueue_job_with_context(
                pool, "run_agent_task",
                event_id=task["event_id"], binding_id=task["binding_id"],
            )

    # Completion sweep (sync).
    await loop.run_in_executor(None, notify_completed_events, session, tenant_id)


@tenant_aware_job
async def run_agent_task(ctx: dict[str, Any], *, event_id: str, binding_id: str) -> None:
    """Run one Specialist Agent for one dispatched action_event, then log + notify."""
    from app.modules.agent_builder.agent_executor import AgentExecutor

    session = ctx["session"]
    tenant_id = tenant_context.get()
    if tenant_id is None:
        raise RuntimeError("run_agent_task: tenant_context unset at entry")
    loop = asyncio.get_running_loop()

    output: dict[str, Any] = {}
    confidence, rationale, success, error = 0.0, "", False, ""
    try:
        spec = await loop.run_in_executor(
            None, lambda: claim_agent_task(session, tenant_id, event_id=event_id, binding_id=binding_id)
        )
        result = await AgentExecutor(session).execute_task(
            spec.agent_id, spec.payload, tenant_id=tenant_id, department_id=spec.department_id
        )
        output, confidence, rationale = result.output, result.confidence, result.rationale
        success, error = result.success, result.error
    except Exception as exc:  # noqa: BLE001 — record + notify failure, never leave the event stuck
        logger.exception("run_agent_task failed for event %s", event_id)
        output, confidence, rationale, success, error = {}, 0.0, "", False, str(exc)

    await loop.run_in_executor(
        None,
        lambda: finalize_agent_event(
            session, tenant_id, event_id=event_id, binding_id=binding_id,
            output=output, confidence=confidence, rationale=rationale,
            success=success, error=error,
        ),
    )


# Cron cadence — poll every 5s for snappy demo dispatch. `unique=True` prevents
# overlap; `run_at_startup=False` keeps tests quiet.
action_cron_jobs = [
    cron(
        dispatch_action_events_fanout,
        name="action_events_fanout",
        second=set(range(0, 60, 5)),
        run_at_startup=False,
        unique=True,
    ),
]
