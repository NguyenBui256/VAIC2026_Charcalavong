"""Backend HTTP endpoints for graph run review + rollback (Sub-project 3B).

UI is 3C (this router is polled). Every state-changing endpoint records its
decision, audits it, and re-enqueues run_workflow(resume=True).
"""
from __future__ import annotations

import uuid
from typing import Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.arq_pool import get_arq_pool
from app.core.deps import get_tenant_session
from app.core.jobs import enqueue_job_with_context
from app.modules.orchestrator.graph_review import (
    ReviewError,
    confirm_rollback,
    list_run_nodes,
    record_decision,
)

router = APIRouter(prefix="/workflows", tags=["workflows-graph"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _err(message: str) -> dict[str, Any]:
    return {"data": None, "error": {"message": message}, "meta": {}}


def _actor_user_id(request: Request) -> uuid.UUID:
    return uuid.UUID(str(request.state.user_id))


class DecisionRequest(BaseModel):
    action: str
    guidance: str | None = None
    output: dict[str, Any] | None = None
    reason: str | None = None
    target_node_key: str | None = None


class ConfirmRequest(BaseModel):
    accept: bool


@router.get("/runs/{run_id}/nodes")
async def list_nodes_route(
    run_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    return JSONResponse(status_code=200, content=_ok(list_run_nodes(session, run_id)))


@router.post("/runs/{run_id}/nodes/{node_key}/decision")
async def node_decision_route(
    run_id: uuid.UUID,
    node_key: str,
    body: DecisionRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> JSONResponse:
    try:
        data = record_decision(
            session,
            run_id,
            node_key,
            action=body.action,
            actor_user_id=_actor_user_id(request),
            guidance=body.guidance,
            output=body.output,
            reason=body.reason,
            target_node_key=body.target_node_key,
        )
    except ReviewError as exc:
        return JSONResponse(status_code=exc.status_code, content=_err(exc.message))
    await enqueue_job_with_context(pool, "run_workflow", run_id=str(run_id), resume=True)
    return JSONResponse(status_code=200, content=_ok(data))


@router.post("/runs/{run_id}/rollbacks/{rollback_id}/confirm")
async def rollback_confirm_route(
    run_id: uuid.UUID,
    rollback_id: uuid.UUID,
    body: ConfirmRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> JSONResponse:
    try:
        data = confirm_rollback(
            session,
            run_id,
            rollback_id,
            accept=body.accept,
            actor_user_id=_actor_user_id(request),
        )
    except ReviewError as exc:
        return JSONResponse(status_code=exc.status_code, content=_err(exc.message))
    await enqueue_job_with_context(pool, "run_workflow", run_id=str(run_id), resume=True)
    return JSONResponse(status_code=200, content=_ok(data))
