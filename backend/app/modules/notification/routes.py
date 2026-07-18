"""Notification HTTP routes — the current user's own alerts (RLS + user_id filter)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.notification import service as svc

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _current_user_id(request: Request) -> uuid.UUID:
    return uuid.UUID(str(request.state.user_id))


@notifications_router.get("")
def list_notifications_route(  # noqa: B008
    request: Request, unread: bool = False, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    items = svc.list_notifications(session, _current_user_id(request), unread_only=unread)
    return JSONResponse(status_code=200, content=_ok([svc.serialize_notification(n) for n in items]))


@notifications_router.patch("/{notification_id}/read")
def mark_read_route(  # noqa: B008
    notification_id: uuid.UUID, request: Request, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    n = svc.mark_read(session, _current_user_id(request), notification_id)
    return JSONResponse(status_code=200, content=_ok(svc.serialize_notification(n)))


@notifications_router.post("/read-all")
def mark_all_read_route(  # noqa: B008
    request: Request, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    updated = svc.mark_all_read(session, _current_user_id(request))
    return JSONResponse(status_code=200, content=_ok({"updated": updated}))
