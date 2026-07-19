"""Tenant-wide Tool catalog routes (Sub-project A / Shared Pool).

`GET` is open to any tenant principal (agents reference these tools). CRUD
(`POST`/`PATCH`/`DELETE`) is builder-only — guarded in
`tool_catalog_service` (`require_builder`), not here. Built-in tools
(`kind="builtin"`) reject mutation at the service layer.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.agent_builder.service import Principal
from app.modules.agent_builder.tool_catalog_service import (
    create_catalog_tool,
    delete_catalog_tool,
    get_catalog_tool,
    list_catalog_tools,
    serialize_tool,
    update_catalog_tool,
)

router = APIRouter(prefix="/tools", tags=["tools"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _principal(request: Request) -> Principal:
    dept = getattr(request.state, "department_id", None)
    return Principal(
        user_id=uuid.UUID(str(request.state.user_id)),
        tenant_id=uuid.UUID(str(request.state.tenant_id)),
        department_id=uuid.UUID(str(dept)) if dept else None,
        role=str(getattr(request.state, "role", "")),
    )


class CreateToolRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    params_schema: dict[str, Any]
    output_schema: dict[str, Any]
    integration_id: uuid.UUID


class UpdateToolRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    params_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    integration_id: uuid.UUID | None = None


@router.get("")
def list_tools_route(
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    tools = list_catalog_tools(session)
    return JSONResponse(status_code=200, content=_ok([serialize_tool(t) for t in tools]))


@router.get("/{tool_id}")
def get_tool_route(
    tool_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    return JSONResponse(status_code=200, content=_ok(serialize_tool(get_catalog_tool(session, tool_id))))


@router.post("")
def create_tool_route(
    body: CreateToolRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """POST /tools — create a `kind="integration"` catalog tool. Builder role required."""
    tool = create_catalog_tool(
        session,
        principal=_principal(request),
        display_name=body.display_name,
        description=body.description,
        params_schema=body.params_schema,
        output_schema=body.output_schema,
        integration_id=body.integration_id,
    )
    return JSONResponse(status_code=201, content=_ok(serialize_tool(tool)))


@router.patch("/{tool_id}")
def update_tool_route(
    tool_id: uuid.UUID,
    body: UpdateToolRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """PATCH /tools/{id} — update a `kind="integration"` catalog tool. Builder role required."""
    tool = update_catalog_tool(
        session,
        tool_id,
        principal=_principal(request),
        **body.model_dump(exclude_unset=True),
    )
    return JSONResponse(status_code=200, content=_ok(serialize_tool(tool)))


@router.delete("/{tool_id}")
def delete_tool_route(
    tool_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """DELETE /tools/{id} — soft-delete a `kind="integration"` catalog tool. Builder role required."""
    delete_catalog_tool(session, tool_id, principal=_principal(request))
    return JSONResponse(status_code=200, content=_ok({"id": str(tool_id)}))
