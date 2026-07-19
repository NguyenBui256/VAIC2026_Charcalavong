"""Tenant-wide Knowledge Base store routes (Sub-project A / Shared Pool).

Builder-only CRUD (`require_builder`, guarded in `kb_service`); reads are
tenant-scoped via RLS. User-level grants (`kb_document_grants`) were dropped
in the Shared Pool reshape — access is agent-grant only (`agent_kb_documents`,
see `routes.py`).
"""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.agent_builder.kb_service import (
    create_pending_document, delete_document, fetch_ingest_progress, get_document,
    get_document_content, ingest_document, list_documents, serialize_document,
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
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> JSONResponse:
    # Persist the row as `processing` and return immediately; RAG ingestion
    # runs in a background task (large PDFs can take minutes). The frontend
    # polls the pool until the row settles to indexed/failed.
    data = file.file.read()
    doc = create_pending_document(
        session, principal=_principal(request),
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    background_tasks.add_task(ingest_document, doc.id, data, tenant_id=doc.tenant_id)
    return JSONResponse(status_code=201, content=_ok(serialize_document(doc)))


@router.get("")
def list_route(
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    docs = list_documents(session, principal=principal)
    payload = []
    for d in docs:
        item = serialize_document(d)
        # Enrich in-flight docs with live ingest % (best-effort; None -> omit).
        if d.status == "processing":
            percent = fetch_ingest_progress(d)
            if percent is not None:
                item["progress"] = percent
        payload.append(item)
    return JSONResponse(status_code=200, content=_ok(payload))


@router.get("/{doc_id}")
def get_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    doc = get_document(session, document_id=doc_id, principal=principal)
    return JSONResponse(status_code=200, content=_ok(serialize_document(doc)))


@router.get("/{doc_id}/content")
def get_content_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> Response:
    """Serve the original uploaded file bytes for inline viewing/download.

    Tenant-scoped read (RLS). `Content-Disposition: inline` lets the browser
    preview PDF/TXT/Markdown; unpreviewable types (DOCX) download instead.
    Filename is RFC 5987 encoded to stay header-safe for unicode names.
    """
    principal = _principal(request)
    doc, data = get_document_content(session, document_id=doc_id, principal=principal)
    disposition = f"inline; filename*=UTF-8''{quote(doc.filename)}"
    return Response(
        content=data,
        media_type=doc.content_type or "application/octet-stream",
        headers={"Content-Disposition": disposition},
    )


@router.delete("/{doc_id}")
def delete_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    delete_document(session, document_id=doc_id, principal=_principal(request))
    return JSONResponse(status_code=200, content=_ok({"id": str(doc_id)}))
