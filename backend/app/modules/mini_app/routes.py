"""Mini-App HTTP routes — catalog CRUD + generic row CRUD (Epic 4).

Thin adapters: parse -> service -> _ok envelope. Visibility tier is
asserted on every read/write of a specific app (`assert_can_access`).
`POST /mini-apps` accepts EITHER a caller-supplied validated schema OR a
`description`+`expected_output` pair, in which case the schema+ui_spec are
LLM-emitted (FR-12, `emission.emit_schema`).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.arq_pool import get_arq_pool
from app.core.deps import crud_audit_ids, get_tenant_session
from app.core.errors import DomainError
from app.core.ids import utcnow_iso_ms
from app.core.ports.audit import AuditEntry
from app.modules.mini_app import service
from app.modules.mini_app.emission import emit_schema
from app.modules.mini_app.lifecycle import enqueue_build
from app.modules.mini_app.schema_validation import (
    SchemaValidationError,
    validate_entity_schema,
    validate_ui_spec,
)
from app.modules.mini_app.visibility import MiniAppPrincipal, assert_can_access

mini_apps_router = APIRouter(prefix="/mini-apps", tags=["mini-apps"])
mini_app_rows_router = APIRouter(prefix="/apps", tags=["mini-app-rows"])


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


def _audit_emission(entity_id: uuid.UUID, event_type: str, detail: dict[str, Any]) -> None:
    """Audit LLM schema emission (FR-12). Mirrors `mini_app.service._audit`:
    the sink method is `.log(...)`, entity_id doubles as `agent_id`/`run_id`
    per the CRUD-audit convention (`crud_audit_ids`, OQ-1)."""
    run_id, step_id = crud_audit_ids(str(entity_id))
    PostgresAuditSink().log(
        AuditEntry(
            run_id=run_id, step_id=step_id, agent_id=str(entity_id),
            ts=utcnow_iso_ms(), type=event_type, input=detail, output={},
            latency_ms=0, model="",
        )
    )


class CreateMiniAppRequest(BaseModel):
    """Either a caller-supplied `entity_schema` (Task 7 path) OR a
    `description` + `expected_output` pair with no schema, in which case
    the schema+ui_spec are LLM-emitted (FR-12)."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    entity_schema: dict[str, Any] | None = None
    expected_output: str | None = None
    ui_spec: dict[str, Any] | None = None
    visibility_tier: str = "need_auth"
    whitelist_user_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_schema_or_description(self) -> "CreateMiniAppRequest":
        if self.entity_schema is None and not self.expected_output:
            raise ValueError(
                "either 'entity_schema' or ('description' + 'expected_output') is required"
            )
        return self


class RowWriteRequest(BaseModel):
    data: dict[str, Any]


class RowUpdateRequest(BaseModel):
    data: dict[str, Any]
    expected_updated_at: datetime


@mini_apps_router.post("")
async def create_mini_app_route(
    body: CreateMiniAppRequest, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    prompt: str | None = None
    if body.entity_schema is not None:
        schema = validate_entity_schema(body.entity_schema)
        ui_spec = validate_ui_spec(body.ui_spec or {})
    else:
        try:
            schema, ui_spec, prompt = emit_schema(body.description, body.expected_output or "")
        except SchemaValidationError as exc:
            _audit_emission(principal.user_id, "mini_app.schema_rejected", {"reason": exc.reason})
            raise DomainError(exc.reason, code="schema_rejected", http_status=422) from exc
    app = service.create_app_from_schema(
        session, principal=principal, name=body.name, description=body.description,
        schema=schema, ui_spec=ui_spec, visibility_tier=body.visibility_tier,
        whitelist_user_ids=body.whitelist_user_ids,
    )
    if prompt is not None:
        _audit_emission(app.id, "mini_app.schema_emitted", {"prompt": prompt})
    await enqueue_build(pool, str(app.id))
    return JSONResponse(status_code=201, content=_ok(service.serialize_app(app)))


@mini_apps_router.get("")
def list_mini_apps_route(session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok([service.serialize_app(a) for a in service.list_apps(session)]))


@mini_apps_router.get("/{app_id}")
def get_mini_app_route(app_id: uuid.UUID, request: Request,
                       session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app = service.get_app(session, app_id)
    assert_can_access(app, _principal(request))
    return JSONResponse(status_code=200, content=_ok(service.serialize_app(app)))


@mini_apps_router.post("/{app_id}/rebuild")
async def rebuild_mini_app_route(app_id: uuid.UUID, request: Request,
                                 session: Session = Depends(get_tenant_session),  # noqa: B008
                                 pool: ArqRedis = Depends(get_arq_pool)) -> JSONResponse:  # noqa: B008
    app = service.get_app(session, app_id)
    assert_can_access(app, _principal(request))
    await enqueue_build(pool, str(app.id))
    return JSONResponse(status_code=202, content=_ok({"app_id": str(app.id), "build_status": "pending"}))


def _load_and_gate(app_id: uuid.UUID, request: Request, session: Session):  # noqa: ANN202
    app = service.get_app(session, app_id)
    principal = _principal(request)
    assert_can_access(app, principal)
    return app, principal


@mini_app_rows_router.post("/{app_id}/rows")
def create_row_route(app_id: uuid.UUID, body: RowWriteRequest, request: Request,
                     session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, principal = _load_and_gate(app_id, request, session)
    row = service.create_row(session, app, principal, body.data)
    return JSONResponse(status_code=201, content=_ok(service.serialize_row(row)))


@mini_app_rows_router.get("/{app_id}/rows")
def list_rows_route(app_id: uuid.UUID, request: Request,
                    session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, _ = _load_and_gate(app_id, request, session)
    return JSONResponse(status_code=200, content=_ok([service.serialize_row(r) for r in service.list_rows(session, app)]))


@mini_app_rows_router.get("/{app_id}/rows/{row_id}")
def get_row_route(app_id: uuid.UUID, row_id: uuid.UUID, request: Request,
                  session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, _ = _load_and_gate(app_id, request, session)
    return JSONResponse(status_code=200, content=_ok(service.serialize_row(service.get_row(session, app, row_id))))


@mini_app_rows_router.patch("/{app_id}/rows/{row_id}")
def update_row_route(app_id: uuid.UUID, row_id: uuid.UUID, body: RowUpdateRequest, request: Request,
                     session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, principal = _load_and_gate(app_id, request, session)
    row = service.update_row(session, app, principal, row_id, body.data, body.expected_updated_at)
    return JSONResponse(status_code=200, content=_ok(service.serialize_row(row)))


@mini_app_rows_router.delete("/{app_id}/rows/{row_id}")
def delete_row_route(app_id: uuid.UUID, row_id: uuid.UUID, request: Request,
                     session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, _ = _load_and_gate(app_id, request, session)
    service.delete_row(session, app, row_id)
    return JSONResponse(status_code=200, content=_ok({"deleted": str(row_id)}))
