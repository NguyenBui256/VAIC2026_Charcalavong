"""Action binding HTTP routes (Actions page). Thin adapters -> service -> _ok."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.action import service as svc
from app.modules.mini_app.visibility import MiniAppPrincipal

actions_router = APIRouter(prefix="/actions", tags=["actions"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _principal(request: Request) -> MiniAppPrincipal:
    dept = getattr(request.state, "department_id", None)
    return MiniAppPrincipal(
        user_id=uuid.UUID(str(request.state.user_id)),
        tenant_id=uuid.UUID(str(request.state.tenant_id)),
        department_id=uuid.UUID(str(dept)) if dept else None,
        role=str(getattr(request.state, "role", "")),
    )


class CreateActionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    database_id: uuid.UUID
    event_type: str = "row.created"
    target_type: str = "workflow"
    workflow_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    notify_user_ids: list[uuid.UUID] = Field(default_factory=list)
    is_active: bool = True


class UpdateActionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    database_id: uuid.UUID | None = None
    event_type: str | None = None
    target_type: str | None = None
    workflow_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    notify_user_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None


@actions_router.get("")
def list_actions_route(session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok([svc.serialize_binding(b) for b in svc.list_bindings(session)]))


@actions_router.post("")
def create_action_route(  # noqa: B008
    body: CreateActionRequest, request: Request, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    b = svc.create_binding(
        session, principal=_principal(request), name=body.name,
        database_id=body.database_id, event_type=body.event_type,
        target_type=body.target_type, workflow_id=body.workflow_id, agent_id=body.agent_id,
        notify_user_ids=body.notify_user_ids, is_active=body.is_active,
    )
    return JSONResponse(status_code=201, content=_ok(svc.serialize_binding(b)))


@actions_router.get("/{binding_id}")
def get_action_route(binding_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok(svc.serialize_binding(svc.get_binding(session, binding_id))))


@actions_router.patch("/{binding_id}")
def update_action_route(  # noqa: B008
    binding_id: uuid.UUID, body: UpdateActionRequest, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    b = svc.update_binding(
        session, binding_id, name=body.name, database_id=body.database_id,
        event_type=body.event_type, target_type=body.target_type,
        workflow_id=body.workflow_id, agent_id=body.agent_id,
        notify_user_ids=body.notify_user_ids, is_active=body.is_active,
    )
    return JSONResponse(status_code=200, content=_ok(svc.serialize_binding(b)))


@actions_router.delete("/{binding_id}")
def delete_action_route(binding_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    svc.delete_binding(session, binding_id)
    return JSONResponse(status_code=200, content=_ok({"id": str(binding_id)}))
