"""Mini-App Database HTTP routes (Database page).

Thin adapters: parse -> service -> _ok envelope. Tenant isolation is enforced
by RLS (app.tenant_id GUC); no per-row visibility tiers here.

`SchemaValidationError` (raised by `validate_entity_schema` inside the
service) is a plain `Exception`, not a `DomainError` — it is NOT globally
converted to a 422 by `register_error_handlers` (which only registers
handlers for `DomainError` and the catch-all `Exception` -> 500). Mirroring
the existing `mini_app/routes.py` `create_mini_app_route` convention, the
create/update routes below wrap the service call and translate it into a
422 `DomainError` explicitly.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.core.errors import DomainError
from app.modules.mini_app import database_service as svc
from app.modules.mini_app.schema_validation import SchemaValidationError
from app.modules.mini_app.visibility import MiniAppPrincipal

mini_app_databases_router = APIRouter(prefix="/mini-app-databases", tags=["mini-app-databases"])


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


class CreateDatabaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    entity_schema: dict[str, Any]


class UpdateDatabaseRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    entity_schema: dict[str, Any] | None = None


@mini_app_databases_router.get("")
def list_databases_route(session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok([svc.serialize_database(d) for d in svc.list_databases(session)]))


@mini_app_databases_router.post("")
def create_database_route(
    body: CreateDatabaseRequest, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    try:
        db = svc.create_database(
            session, principal=_principal(request),
            name=body.name, description=body.description, entity_schema=body.entity_schema,
        )
    except SchemaValidationError as exc:
        raise DomainError(exc.reason, code="schema_rejected", http_status=422) from exc
    return JSONResponse(status_code=201, content=_ok(svc.serialize_database(db)))


@mini_app_databases_router.get("/{db_id}")
def get_database_route(db_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok(svc.serialize_database(svc.get_database(session, db_id))))


@mini_app_databases_router.patch("/{db_id}")
def update_database_route(
    db_id: uuid.UUID, body: UpdateDatabaseRequest,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    try:
        db = svc.update_database(
            session, db_id, name=body.name, description=body.description, entity_schema=body.entity_schema,
        )
    except SchemaValidationError as exc:
        raise DomainError(exc.reason, code="schema_rejected", http_status=422) from exc
    return JSONResponse(status_code=200, content=_ok(svc.serialize_database(db)))


@mini_app_databases_router.delete("/{db_id}")
def delete_database_route(db_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    svc.delete_database(session, db_id)
    return JSONResponse(status_code=200, content=_ok({"id": str(db_id)}))


@mini_app_databases_router.get("/{db_id}/rows")
def list_database_rows_route(db_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok(svc.list_database_rows(session, db_id)))
