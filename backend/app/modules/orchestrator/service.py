"""Orchestrator service layer — Workflow CRUD (3.1) + Run lifecycle (3.2-3.4).

`decompose_run`/`execute_task_row`/`aggregate_run`/`orchestrate_run` (Story
3.3/3.4) implement decomposition, per-Task CAS-claim + dispatch to the
Specialist Agent, and result aggregation — the `run_workflow` arq worker's
extension point after CAS `pending -> running` (Story 3.2).

Domain functions read `tenant_context.get()` (via RLS on the session) —
NEVER accept `tenant_id` as an argument (consistency-conventions "Tenant
context"). `description` is treated as opaque text everywhere in this
module (AC2) — no decomposition/templating logic exists here.

Every CRUD write emits exactly one audit entry through `AuditPort` (AD-4) —
never direct SQL/ORM to `audit_trail` (AC8). Reuses the `crud_audit_ids`
stopgap (OQ-1) verbatim, per Story 3.1 Dev Notes AD-4.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.adapters.registry import select_llm_adapter
from app.core.deps import assume_app_role, crud_audit_ids
from app.core.errors import AuthorizationError, NotFoundError
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.ports.llm import Message, ModelRef
from app.core.tenant_context import set_tenant_session_var, tenant_context
from app.modules.agent_builder.agent_executor import AgentExecutor
from app.modules.agent_builder.service import get_agent, list_routable_agents
from app.modules.orchestrator.models import Task, Workflow, WorkflowRun
from app.modules.orchestrator.schemas import TaskSchemaModel
from app.modules.orchestrator.state import (
    transition_and_audit,
    transition_task_status,
)

__all__ = [
    "Principal",
    "create_workflow",
    "get_workflow",
    "list_workflows",
    "update_workflow",
    "serialize_workflow",
    "create_run",
    "serialize_run",
    "decompose_run",
    "execute_task_row",
    "aggregate_run",
    "orchestrate_run",
]

# TODO(settings): move to config. Cheap model for dev; swap to a premium
# model for the demo run. Injected as `llm=` in every call site that needs
# determinism (tests use a FakeLlm; no live API key required for tests).
ORCHESTRATOR_MODEL = ModelRef(provider="anthropic", model_name="claude-haiku-4-5-20251001")


@dataclass(frozen=True)
class Principal:
    """The caller's identity, as extracted from `request.state` by routes."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


def _emit_audit(
    audit: AuditPort, workflow: Workflow, entry_type: str, payload: dict
) -> None:
    """Emit one audit entry for a CRUD write (AC8). Never swallows (AD-4)."""
    run_id, step_id = crud_audit_ids(str(workflow.id))
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(workflow.id),
            ts=utcnow_iso_ms(),
            type=entry_type,
            input=payload,
            output={"workflow_id": str(workflow.id), "version": workflow.version},
            latency_ms=0,
            model="",
        )
    )


def create_workflow(
    session: Session,
    *,
    owner_id: uuid.UUID,
    role: str,
    name: str,
    description: str,
    constraints: list[str] | None = None,
    audit: AuditPort | None = None,
) -> Workflow:
    """Create a scoped Workflow (AC1, AC10). Requires builder role."""
    if role != "builder":
        raise AuthorizationError(
            "builder role required to create a Workflow", code="FORBIDDEN"
        )

    tenant_id = tenant_context.get()
    workflow = Workflow(
        id=uuid7(),
        tenant_id=tenant_id,
        owner_id=owner_id,
        name=name,
        description=description,
        constraints=constraints or [],
        version=1,
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)

    _emit_audit(
        audit or PostgresAuditSink(),
        workflow,
        "workflow.created",
        {"name": name},
    )
    return workflow


def get_workflow(session: Session, workflow_id: uuid.UUID) -> Workflow:
    """Fetch a single Workflow. RLS hides cross-tenant rows (AC4)."""
    workflow = session.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    ).scalar_one_or_none()
    if workflow is None:
        raise NotFoundError("Workflow not found")
    return workflow


def list_workflows(
    session: Session, *, search: str | None = None, owner_id: uuid.UUID | None = None
) -> list[Workflow]:
    """List Workflows. Tenant scoping is RLS-only (AC3)."""
    stmt = select(Workflow)
    if search:
        stmt = stmt.where(Workflow.name.ilike(f"%{search}%"))
    if owner_id is not None:
        stmt = stmt.where(Workflow.owner_id == owner_id)
    return list(session.execute(stmt).scalars().all())


def _authorize_mutation(principal: Principal) -> None:
    """Guard for PATCH (AC10).

    Workflows have no department scope — any builder in the tenant may
    edit any Workflow (simpler than Agent's dept-based rule, per T3.5).
    """
    if principal.role != "builder":
        raise AuthorizationError(
            "builder role required to update a Workflow", code="FORBIDDEN"
        )


def update_workflow(
    session: Session,
    workflow_id: uuid.UUID,
    principal: Principal,
    *,
    audit: AuditPort | None = None,
    **changes: object,
) -> Workflow:
    """Update mutable fields on a Workflow, bumping `version` (AC6, AC8)."""
    workflow = get_workflow(session, workflow_id)
    _authorize_mutation(principal)

    allowed_fields = {
        "name",
        "description",
        "constraints",
        "confidence_threshold",
        "escalation_timeout_seconds",
    }
    applied: dict[str, object] = {}
    for key, value in changes.items():
        if key not in allowed_fields or value is None:
            continue
        setattr(workflow, key, value)
        applied[key] = value

    workflow.version += 1
    workflow.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(workflow)

    _emit_audit(audit or PostgresAuditSink(), workflow, "workflow.updated", applied)
    return workflow


def create_run(
    session: Session,
    workflow_id: uuid.UUID,
    *,
    role: str,
    input: dict[str, Any] | None = None,
) -> WorkflowRun:
    """Create a `pending` Run for a Workflow (AC2). Requires builder role (M-9).

    `get_workflow` 404s on a missing/cross-tenant `workflow_id` (RLS-backed)
    before any Run row is created. No arq enqueue happens here — that is
    the route's responsibility (AC3), since only the route has access to
    the arq pool dependency (AD-1: service stays transport-agnostic).

    Mirrors `create_workflow`'s builder-only gate (AC10) — triggering a Run
    is a mutation with real cost (LLM decomposition + Agent dispatch), so
    the same role restriction applies.
    """
    if role != "builder":
        raise AuthorizationError(
            "builder role required to create a Run", code="FORBIDDEN"
        )
    workflow = get_workflow(session, workflow_id)
    tenant_id = tenant_context.get()
    run = WorkflowRun(
        id=uuid7(),
        tenant_id=tenant_id,
        workflow_id=workflow.id,
        status="pending",
        input=input or {},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def serialize_run(run: WorkflowRun) -> dict:
    """Response payload shape for a Run (AR-14: ISO 8601 ms timestamps)."""
    return {
        "id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "workflow_id": str(run.workflow_id),
        "status": run.status,
        "input": run.input or {},
        "result": run.result,
        "started_at": (
            run.started_at.isoformat(timespec="milliseconds")
            if run.started_at
            else None
        ),
        "ended_at": (
            run.ended_at.isoformat(timespec="milliseconds") if run.ended_at else None
        ),
        "created_at": run.created_at.isoformat(timespec="milliseconds"),
    }


def _reassert_rls(session: Session) -> None:
    """Re-apply role drop + tenant RLS var on `session` (AD-10).

    `assume_app_role`/`set_tenant_session_var` are transaction-scoped (`SET
    LOCAL`/`set_config(..., true)`) — each `session.commit()` performed by
    the CAS helpers ends that scope. Every RLS-scoped statement that follows
    a commit within the same job MUST re-apply both before running (mirrors
    `orchestrator_worker._transition`). Reads `tenant_context.get()` (the
    contextvar `@tenant_aware_job` sets at job entry) — no-op outside a job
    (e.g. integration tests driving `app_session` directly, which assert
    their own RLS context via raw SQL).
    """
    tenant_id = tenant_context.get()
    if tenant_id is None:
        return
    assume_app_role(session)
    set_tenant_session_var(session, tenant_id)


def _orchestrator_llm():
    return select_llm_adapter(ORCHESTRATOR_MODEL.provider)


def _decomposition_prompt(workflow: Workflow, candidates: list[dict]) -> list[Message]:
    roster = "\n".join(f"- {c['id']} | {c['name']} | dept={c['department_id']}" for c in candidates)
    sys = (
        "You are a banking Workflow Orchestrator. Decompose the request into <=5 Tasks. "
        "Return ONLY a JSON array; each item = "
        "{task:{summary}, target_agent_id, input, output, expected:[...], criteria:{}}. "
        "target_agent_id MUST be one of the agent ids below."
    )
    usr = f"REQUEST: {workflow.description}\nCONSTRAINTS: {workflow.constraints}\nAGENTS:\n{roster}"
    return [Message(role="system", content=sys), Message(role="user", content=usr)]


def _audit(session: Session | None, entry_kwargs: dict[str, Any]) -> None:
    PostgresAuditSink(session).log(AuditEntry(ts=utcnow_iso_ms(), **entry_kwargs))


def _safe_json_array(content: str) -> list:
    try:
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _validate_and_route_task(
    session: Session,
    run: WorkflowRun,
    item: Any,
    valid_ids: dict[str, dict],
) -> Task | None:
    """Validate one decomposition `item` against `TaskSchemaModel` and route
    it to a known Agent. Returns `None` (after auditing the drop) on either
    failure — never raises (T3.2's per-item audit trail, not a hard abort).
    """
    try:
        ts = TaskSchemaModel(**item)
    except (TypeError, ValueError):
        _reassert_rls(session)
        _audit(
            session,
            dict(
                run_id=str(run.id), step_id=str(uuid7()), agent_id="",
                type="task.dropped_invalid", input={"item": item}, output={}, latency_ms=0,
            ),
        )
        return None
    if ts.target_agent_id not in valid_ids:
        _reassert_rls(session)
        _audit(
            session,
            dict(
                run_id=str(run.id), step_id=str(uuid7()), agent_id="",
                type="task.routing_rejected", input={"target": ts.target_agent_id},
                output={}, latency_ms=0,
            ),
        )
        return None
    return Task(
        id=uuid7(), tenant_id=run.tenant_id, run_id=run.id,
        target_agent_id=uuid.UUID(ts.target_agent_id), status="pending",
        schema_payload=ts.model_dump(),
    )


def decompose_run(
    session: Session, run_id: uuid.UUID | str, *, llm: Any | None = None, max_tasks: int = 5
) -> list[Task]:
    """LLM-decompose a Run into <=`max_tasks` schema-valid, routed Tasks (FR-8).

    Idempotent: if Tasks already exist for `run_id` (e.g. the `resume=True`
    worker path re-enters the same job body after a crash), returns the
    existing rows WITHOUT calling the LLM or inserting duplicates.
    """
    _reassert_rls(session)
    existing = list(
        session.execute(select(Task).where(Task.run_id == run_id)).scalars().all()
    )
    if existing:
        return existing
    run = session.get(WorkflowRun, run_id)
    if run is None:
        raise NotFoundError("WorkflowRun not found")
    workflow = session.get(Workflow, run.workflow_id)
    if workflow is None:
        raise NotFoundError("Workflow not found")
    candidates = list_routable_agents(session)
    valid_ids = {c["id"]: c for c in candidates}
    llm = llm or _orchestrator_llm()
    completion = llm.complete(
        _decomposition_prompt(workflow, candidates), ORCHESTRATOR_MODEL, {"temperature": 0.3}
    )
    raw = _safe_json_array(completion.content)

    tasks = [
        task
        for item in raw[:max_tasks]
        if (task := _validate_and_route_task(session, run, item, valid_ids)) is not None
    ]

    _reassert_rls(session)
    session.add_all(tasks)
    session.commit()
    _reassert_rls(session)
    _audit(
        session,
        dict(
            run_id=str(run_id), step_id=str(uuid7()), agent_id="",
            type="orchestrator.decomposed",
            input={"request": workflow.description, "workflow_description": workflow.description},
            output={"task_ids": [str(t.id) for t in tasks]},
            latency_ms=completion.latency_ms, model=completion.model,
        ),
    )
    return tasks


def _task_department(session: Session, task: Task) -> uuid.UUID:
    """Resolve the target Agent's `department_id` (public service call, AD-1)."""
    return get_agent(session, task.target_agent_id).department_id


async def _run_with_retry(
    executor: Any, task: Task, dept_id: uuid.UUID, timeout_s: int, retries: int
):
    delay = 2
    for attempt in range(retries + 1):
        try:
            return await asyncio.wait_for(
                executor.execute_task(
                    task.target_agent_id, task.schema_payload,
                    tenant_id=task.tenant_id, department_id=dept_id,
                ),
                timeout=timeout_s,
            )
        except Exception:
            if attempt == retries:
                raise
            await asyncio.sleep(delay)
            delay *= 4  # 2s, 8s (FR-9)


async def execute_task_row(
    session: Session, task: Task, *, executor: Any | None = None,
    timeout_s: int = 60, retries: int = 2,
) -> None:
    """CAS-claim + run + complete/fail one Task (Story 3.4a). AD-6: caller
    never proceeds on a lost CAS race."""
    _reassert_rls(session)
    if not transition_task_status(session, task.id, from_status="pending", to_status="claimed"):
        return  # lost race / not pending (AD-6)

    _reassert_rls(session)
    executor = executor or AgentExecutor(session)
    try:
        dept_id = _task_department(session, task)
        res = await _run_with_retry(executor, task, dept_id, timeout_s, retries)
        _reassert_rls(session)
        transition_task_status(
            session, task.id, from_status="claimed", to_status="completed",
            extra_cols={"result": json.dumps(res.model_dump())},
        )
        _reassert_rls(session)
        _audit(
            session,
            dict(
                run_id=str(task.run_id), step_id=str(uuid7()),
                agent_id=str(task.target_agent_id), type="task.executed",
                input=task.schema_payload, output=res.model_dump(), latency_ms=0,
            ),
        )
    except Exception as exc:
        _reassert_rls(session)
        transition_task_status(
            session, task.id, from_status="claimed", to_status="failed",
            extra_cols={"result": json.dumps({"error": str(exc)})},
        )
        _reassert_rls(session)
        _audit(
            session,
            dict(
                run_id=str(task.run_id), step_id=str(uuid7()),
                agent_id=str(task.target_agent_id), type="task.failed",
                input=task.schema_payload, output={"error": str(exc)}, latency_ms=0,
            ),
        )


def aggregate_run(session: Session, run_id: uuid.UUID | str) -> dict:
    """Merge all Task results for `run_id` into the Run's aggregate shape.

    `populate_existing()` is required here (M-3): the identity-mapped
    `Task` objects `execute_task_row` mutated via raw-SQL CAS commits get
    expired-then-silently-repopulated-then-re-expired across the audit
    commit right after each CAS (per-attribute expiry ordering quirk) --
    without it, this SELECT can return a stale cached `status` (e.g.
    `pending`) even though the row's `result` column reads fresh, corrupting
    the succeeded-task count `orchestrate_run` relies on.
    """
    _reassert_rls(session)
    stmt = select(Task).where(Task.run_id == run_id).execution_options(populate_existing=True)
    rows = session.execute(stmt).scalars().all()
    return {
        "tasks": [
            {
                "task_id": str(t.id), "target_agent_id": str(t.target_agent_id),
                "status": t.status, "result": t.result,
            }
            for t in rows
        ]
    }


def _has_succeeded_task(result: dict) -> bool:
    """True iff >=1 Task in `aggregate_run`'s output actually succeeded (M-3).

    A Task counts as succeeded only when `status=='completed'` AND its
    stored `result.success` is truthy -- a `status=='failed'` Task (infra
    error/timeout) or a `completed` Task whose Agent/tool reported
    `success=False` (M-4) does NOT count.
    """
    return any(
        t["status"] == "completed" and (t.get("result") or {}).get("success")
        for t in result["tasks"]
    )


async def orchestrate_run(
    session: Session, run_id: uuid.UUID | str, *,
    llm: Any | None = None, executor: Any | None = None,
) -> None:
    """Decompose -> sequentially dispatch -> aggregate (Story 3.3/3.4 entrypoint).

    The single entrypoint the `run_workflow` worker calls after CAS
    `pending -> running`. Safe to re-enter on the `resume=True` path
    (`decompose_run` is idempotent, see its docstring).
    """
    tasks = decompose_run(session, run_id, llm=llm)
    if not tasks:
        _reassert_rls(session)
        transition_and_audit(
            session, kind="run", entity_id=run_id, run_id=run_id,
            from_status="running", to_status="failed",
        )
        return

    for task in tasks:
        await execute_task_row(session, task, executor=executor)

    _reassert_rls(session)
    result = aggregate_run(session, run_id)
    to_status = "completed" if _has_succeeded_task(result) else "failed"
    _reassert_rls(session)
    if not transition_and_audit(
        session, kind="run", entity_id=run_id, run_id=run_id,
        from_status="running", to_status=to_status,
        extra_cols={"result": json.dumps(result)},
    ):
        return  # lost race (AD-6) — do not overwrite a Run someone else transitioned
    _reassert_rls(session)
    _audit(
        session,
        dict(
            run_id=str(run_id), step_id=str(uuid7()), agent_id="",
            type="orchestrator.aggregated", input={}, output=result, latency_ms=0,
        ),
    )


def serialize_workflow(workflow: Workflow) -> dict:
    """Response payload shape (AR-14: ISO 8601 ms timestamps)."""
    return {
        "id": str(workflow.id),
        "tenant_id": str(workflow.tenant_id),
        "owner_id": str(workflow.owner_id),
        "name": workflow.name,
        "description": workflow.description,
        "constraints": workflow.constraints or [],
        "confidence_threshold": workflow.confidence_threshold,
        "escalation_timeout_seconds": workflow.escalation_timeout_seconds,
        "version": workflow.version,
        "created_at": workflow.created_at.isoformat(timespec="milliseconds"),
        "updated_at": workflow.updated_at.isoformat(timespec="milliseconds"),
    }
