"""Tenant-wide Tool catalog routes (Sub-project A) — GET only.

Read-only catalog: agents reference these tools; there is no user-authored
tool creation yet (spec D4).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.agent_builder.tool_catalog_service import (
    get_catalog_tool,
    list_catalog_tools,
    serialize_tool,
)

router = APIRouter(prefix="/tools", tags=["tools"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


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
