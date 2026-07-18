"""Audit HTTP routes — Trace Dashboard read API (Epic 6, FR-22).

Thin adapter (AD-1): parse query -> call read service -> success envelope.
Read-only — this module NEVER writes ``audit_trail`` (writes go through
``PostgresAuditSink`` only, AD-4). Tenant isolation is enforced by RLS via
``get_tenant_session`` (no Python tenant filtering).

Success envelope: ``{data, error: null, meta}`` (AR-14).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.audit.service import (
    entries_to_csv,
    export_audit_entries,
    list_audit_entries,
)

router = APIRouter(prefix="/audit", tags=["audit"])


def _ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": meta or {}}


@router.get("")
def list_audit_route(
    request: Request,  # noqa: ARG001 -- kept for symmetry / future principal use
    session: Session = Depends(get_tenant_session),  # noqa: B008 -- FastAPI idiom
    run_id: uuid.UUID | None = None,
    type: str | None = None,  # noqa: A002 -- matches the AuditEntry field name
    limit: int = 200,
) -> JSONResponse:
    """GET /audit — tenant-scoped Trace Dashboard entries (FR-22).

    Optional filters: ``run_id`` (a single Run's timeline, ordered ts ASC),
    ``type`` (entry type), ``limit`` (capped by the service).
    """
    entries = list_audit_entries(
        session, run_id=run_id, entry_type=type, limit=limit
    )
    return JSONResponse(
        status_code=200,
        content=_ok(entries, meta={"count": len(entries)}),
    )


@router.get("/export")
def export_audit_route(
    request: Request,  # noqa: ARG001 -- symmetry
    session: Session = Depends(get_tenant_session),  # noqa: B008 -- FastAPI idiom
    run_id: uuid.UUID | None = None,
    type: str | None = None,  # noqa: A002 -- matches AuditEntry field name
    format: str = "json",  # noqa: A002 -- query param name
) -> Response:
    """GET /audit/export — download the tenant's Audit Trail (FR-24).

    Returns a raw file (NOT the envelope) with a ``Content-Disposition``
    attachment. ``format`` ∈ {json, csv}; unknown falls back to json.
    Filters mirror ``GET /audit`` (``run_id``, ``type``). Bounded by
    ``EXPORT_LIMIT`` in the service.
    """
    entries = export_audit_entries(session, run_id=run_id, entry_type=type)
    scope = str(run_id)[:8] if run_id is not None else "all"

    if format == "csv":
        body = entries_to_csv(entries)
        media_type = "text/csv"
        filename = f"audit-trail-{scope}.csv"
    else:
        body = json.dumps(entries, ensure_ascii=False, indent=2)
        media_type = "application/json"
        filename = f"audit-trail-{scope}.json"

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
