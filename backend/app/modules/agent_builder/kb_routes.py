"""Tenant-wide Knowledge Base store routes (Sub-project A / Shared Pool).

Builder-only CRUD (`require_builder`, guarded in `kb_service`); reads are
tenant-scoped via RLS. User-level grants (`kb_document_grants`) were dropped
in the Shared Pool reshape — access is agent-grant only (`agent_kb_documents`,
see `routes.py`).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.agent_builder.kb_service import (
    delete_document, get_document, list_documents, serialize_document, upload_document,
)
from app.modules.agent_builder.service import Principal

router = APIRouter(prefix="/kb/documents", tags=["kb"])


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


@router.post("")
def upload_route(
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> JSONResponse:
    doc = upload_document(
        session, principal=_principal(request),
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        data=file.file.read(),
    )
    return JSONResponse(status_code=201, content=_ok(serialize_document(doc)))


@router.get("")
def list_route(
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    docs = list_documents(session, principal=principal)
    return JSONResponse(status_code=200, content=_ok([serialize_document(d) for d in docs]))


@router.get("/{doc_id}")
def get_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    doc = get_document(session, document_id=doc_id, principal=principal)
    return JSONResponse(status_code=200, content=_ok(serialize_document(doc)))


@router.delete("/{doc_id}")
def delete_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    delete_document(session, document_id=doc_id, principal=_principal(request))
    return JSONResponse(status_code=200, content=_ok({"id": str(doc_id)}))
