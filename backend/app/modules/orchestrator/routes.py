"""Orchestrator HTTP routes — /workflows CRUD (Story 3.1).

Thin adapter: parse request -> call service -> envelope (AD-1). No SQL or
business rules live here. `DomainError` subclasses raised by the service
flow through the registered exception handlers (`core/errors.py`).

Success envelope: `{data, error: null, meta: {}}` (AR-14).

Run lifecycle route (`POST /workflows/{id}/runs`) added in Story 3.2 —
creates a `pending` Run and enqueues `run_workflow` via the arq pool.
"""

from __future__ import annotations

import uuid
from typing import Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.arq_pool import get_arq_pool
from app.core.deps import get_tenant_session
from app.core.jobs import enqueue_job_with_context
from app.modules.orchestrator.service import (
    Principal,
    create_run,
    create_workflow,
    list_workflows,
    serialize_run,
    serialize_workflow,
    update_workflow,
)
from app.modules.orchestrator.service import get_workflow as get_workflow_service

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CreateWorkflowRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    constraints: list[str] | None = None


class UpdateWorkflowRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    constraints: list[str] | None = None
    confidence_threshold: float | None = None
    escalation_timeout_seconds: int | None = None


class CreateRunRequest(BaseModel):
    input: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Envelope + principal helpers
# ---------------------------------------------------------------------------

def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _principal(request: Request) -> Principal:
    """Extract the caller's Principal from `request.state` (set by AuthMiddleware)."""
    return Principal(
        user_id=uuid.UUID(str(request.state.user_id)),
        tenant_id=uuid.UUID(str(request.state.tenant_id)),
        role=str(getattr(request.state, "role", "")),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("")
def create_workflow_route(
    body: CreateWorkflowRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008 -- FastAPI idiom
) -> JSONResponse:
    """POST /workflows — create a scoped Workflow (AC1, AC10)."""
    principal = _principal(request)
    workflow = create_workflow(
        session,
        owner_id=principal.user_id,
        role=principal.role,
        name=body.name,
        description=body.description,
        constraints=body.constraints,
    )
    return JSONResponse(status_code=201, content=_ok(serialize_workflow(workflow)))


@router.get("/{workflow_id}")
def get_workflow_route(
    workflow_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """GET /workflows/{id} — cross-tenant returns 404 via RLS (AC4)."""
    workflow = get_workflow_service(session, workflow_id)
    return JSONResponse(status_code=200, content=_ok(serialize_workflow(workflow)))


@router.get("")
def list_workflows_route(
    session: Session = Depends(get_tenant_session),  # noqa: B008
    search: str | None = None,
    owner_id: uuid.UUID | None = None,
) -> JSONResponse:
    """GET /workflows — tenant-scoped list, optional search/owner filter (AC3)."""
    workflows = list_workflows(session, search=search, owner_id=owner_id)
    return JSONResponse(
        status_code=200, content=_ok([serialize_workflow(w) for w in workflows])
    )


@router.patch("/{workflow_id}")
def update_workflow_route(
    workflow_id: uuid.UUID,
    body: UpdateWorkflowRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """PATCH /workflows/{id} — builder role only (AC8, AC10)."""
    principal = _principal(request)
    workflow = update_workflow(
        session,
        workflow_id,
        principal,
        **body.model_dump(exclude_unset=True),
    )
    return JSONResponse(status_code=200, content=_ok(serialize_workflow(workflow)))


@router.post("/{workflow_id}/runs")
async def create_run_route(
    workflow_id: uuid.UUID,
    body: CreateRunRequest,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> JSONResponse:
    """POST /workflows/{id}/runs — create a `pending` Run, enqueue `run_workflow`.

    AC2: creates the Run row FIRST (commits, so it's durable even if the
    enqueue fails). AC3: enqueues via `enqueue_job_with_context`, which
    materializes `tenant_context.get()` into the job payload (AD-10) — the
    codebase idiom, not a raw `tenant_id=` kwarg (see Story 3.2 Dev Notes).
    """
    run = create_run(session, workflow_id, input=body.input)
    await enqueue_job_with_context(pool, "run_workflow", run_id=str(run.id))
    return JSONResponse(status_code=201, content=_ok(serialize_run(run)))
