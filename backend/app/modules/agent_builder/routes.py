"""Agent Builder HTTP routes — /agents CRUD (Story 2.1).

Thin adapter: parse request -> call service -> envelope (AD-1). No SQL or
business rules live here. `DomainError` subclasses raised by the service
flow through the registered exception handlers (`core/errors.py`).

Success envelope: `{data, error: null, meta: {}}` (AR-14).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.agent_builder.service import (
    Principal,
    create_agent,
    list_agents,
    serialize_agent,
    soft_delete_agent,
    update_agent,
)
from app.modules.agent_builder.service import get_agent as get_agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    department_id: uuid.UUID
    system_prompt: str = Field(..., min_length=1)


class UpdateAgentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    system_prompt: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    department_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Envelope + principal helpers
# ---------------------------------------------------------------------------

def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _principal(request: Request) -> Principal:
    """Extract the caller's Principal from `request.state` (set by AuthMiddleware)."""
    dept = getattr(request.state, "department_id", None)
    return Principal(
        user_id=uuid.UUID(str(request.state.user_id)),
        tenant_id=uuid.UUID(str(request.state.tenant_id)),
        department_id=uuid.UUID(str(dept)) if dept else None,
        role=str(getattr(request.state, "role", "")),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("")
def create_agent_route(
    body: CreateAgentRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008 -- FastAPI idiom
) -> JSONResponse:
    """POST /agents — create a scoped Agent (AC1, AC10)."""
    principal = _principal(request)
    agent = create_agent(
        session,
        owner_id=principal.user_id,
        role=principal.role,
        name=body.name,
        department_id=body.department_id,
        system_prompt=body.system_prompt,
    )
    return JSONResponse(status_code=201, content=_ok(serialize_agent(agent)))


@router.get("/{agent_id}")
def get_agent_route(
    agent_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """GET /agents/{id} — cross-tenant returns 404 via RLS (AC2, AC3)."""
    agent = get_agent_service(session, agent_id)
    return JSONResponse(status_code=200, content=_ok(serialize_agent(agent)))


@router.get("")
def list_agents_route(
    session: Session = Depends(get_tenant_session),  # noqa: B008
    department_id: uuid.UUID | None = None,
) -> JSONResponse:
    """GET /agents — tenant-scoped list, optional department filter (AC4, AC5)."""
    agents = list_agents(session, department_id=department_id)
    return JSONResponse(
        status_code=200, content=_ok([serialize_agent(a) for a in agents])
    )


@router.patch("/{agent_id}")
def update_agent_route(
    agent_id: uuid.UUID,
    body: UpdateAgentRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """PATCH /agents/{id} — owner or builder-in-department only (AC6)."""
    principal = _principal(request)
    agent = update_agent(
        session,
        agent_id,
        principal,
        **body.model_dump(exclude_unset=True),
    )
    return JSONResponse(status_code=200, content=_ok(serialize_agent(agent)))


@router.delete("/{agent_id}")
def delete_agent_route(
    agent_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """DELETE /agents/{id} — soft-delete only, same scoping as PATCH (AC7)."""
    principal = _principal(request)
    soft_delete_agent(session, agent_id, principal)
    return JSONResponse(status_code=200, content=_ok({"id": str(agent_id)}))
