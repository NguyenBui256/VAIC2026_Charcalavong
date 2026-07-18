"""Tenant-wide Knowledge Base store routes (Sub-project A)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.agent_builder.kb_grants_service import (
    list_grants, revoke_grant, serialize_grant, set_grant,
)
from app.modules.agent_builder.kb_service import (
    delete_document, get_document, list_documents, serialize_document, upload_document,
)
from app.modules.agent_builder.kb_grants_service import effective_role
from app.modules.agent_builder.kb_service import _get_document_row
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


class SetGrantRequest(BaseModel):
    user_id: uuid.UUID
    role: str  # viewer|manager


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
    return JSONResponse(status_code=201, content=_ok(serialize_document(doc, effective_role="manager")))


@router.get("")
def list_route(
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    docs = list_documents(session, principal=principal)
    return JSONResponse(status_code=200, content=_ok([
        serialize_document(d, effective_role=("manager" if d.owner_id == principal.user_id else None))
        for d in docs
    ]))


@router.get("/{doc_id}")
def get_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    doc = get_document(session, document_id=doc_id, principal=principal)
    role = effective_role(session, doc, principal.user_id)
    return JSONResponse(status_code=200, content=_ok(serialize_document(doc, effective_role=role)))


@router.delete("/{doc_id}")
def delete_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    delete_document(session, document_id=doc_id, principal=_principal(request))
    return JSONResponse(status_code=200, content=_ok({"id": str(doc_id)}))


@router.get("/{doc_id}/grants")
def list_grants_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    from app.modules.agent_builder.kb_grants_service import require_access
    principal = _principal(request)
    doc = _get_document_row(session, doc_id)
    require_access(session, doc, principal.user_id, need_manage=True)
    return JSONResponse(status_code=200, content=_ok([serialize_grant(g) for g in list_grants(session, doc_id)]))


@router.post("/{doc_id}/grants")
def set_grant_route(
    doc_id: uuid.UUID, body: SetGrantRequest, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    grant = set_grant(session, doc_id=doc_id, principal=_principal(request), user_id=body.user_id, role=body.role)
    return JSONResponse(status_code=201, content=_ok(serialize_grant(grant)))


@router.delete("/{doc_id}/grants/{user_id}")
def revoke_grant_route(
    doc_id: uuid.UUID, user_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    revoke_grant(session, doc_id=doc_id, principal=_principal(request), user_id=user_id)
    return JSONResponse(status_code=200, content=_ok({"document_id": str(doc_id), "user_id": str(user_id)}))
