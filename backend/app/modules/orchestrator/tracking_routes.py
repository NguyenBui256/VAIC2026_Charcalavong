"""HTTP routes for the per-user Tracking inbox (cross-run review status)."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.orchestrator import tracking_service as svc

router = APIRouter(prefix="/me/tracking", tags=["tracking"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _current_user_id(request: Request) -> uuid.UUID:
    return uuid.UUID(str(request.state.user_id))


@router.get("")
def list_tracking_route(  # noqa: B008
    request: Request,
    scope: str = "active",
    session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    scope = scope if scope in ("active", "all") else "active"
    items = svc.list_my_tracking(session, _current_user_id(request), scope=scope)
    return JSONResponse(status_code=200, content=_ok(items))


@router.get("/summary")
def tracking_summary_route(  # noqa: B008
    request: Request,
    session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    n = svc.count_my_awaiting(session, _current_user_id(request))
    return JSONResponse(status_code=200, content=_ok({"awaiting_my_review": n}))
