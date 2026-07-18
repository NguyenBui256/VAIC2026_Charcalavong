"""Tenant-scoped uploaded-file storage for typed workflow I/O (3E).

Run-agnostic upload (POST /workflows/files) + authenticated download
(GET /workflows/files/{id}). Bytes on local disk under
`settings.workflow_files_root/{tenant_id}/{id}_{safe_name}`; the row is the
tenant RLS gate. NOT a StaticFiles mount — download is JWT/tenant-scoped.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.tenant_context import tenant_context
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import uuid7
from app.core.settings import get_settings
from app.core.deps import get_tenant_session
from app.modules.orchestrator.models import WorkflowFile

router = APIRouter(prefix="/workflows/files", tags=["workflows-files"])

_MAX_BYTES = 20 * 1024 * 1024  # 20 MB, matches KB upload cap
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _safe_name(name: str) -> str:
    cleaned = _SAFE.sub("_", name).strip("._") or "file"
    return cleaned[:255]


@router.post("")
def upload_file_route(
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> JSONResponse:
    data = file.file.read()
    if len(data) > _MAX_BYTES:
        raise ValidationError("file too large (max 20MB)", code="file_too_large")
    tenant_id = tenant_context.get()
    file_id = uuid7()
    safe = _safe_name(file.filename or "file")
    root = Path(get_settings().workflow_files_root) / str(tenant_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{file_id}_{safe}"
    path.write_bytes(data)

    user_id = getattr(request.state, "user_id", None)
    row = WorkflowFile(
        id=file_id,
        tenant_id=tenant_id,
        filename=safe,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        storage_path=str(path),
        created_by=uuid.UUID(str(user_id)) if user_id else None,
    )
    session.add(row)
    session.commit()
    return JSONResponse(
        status_code=201,
        content=_ok(
            {
                "id": str(row.id),
                "name": row.filename,
                "mime": row.content_type,
                "size": row.size_bytes,
            }
        ),
    )


@router.get("/{file_id}")
def download_file_route(
    file_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> FileResponse:
    row = session.get(WorkflowFile, file_id)  # RLS hides cross-tenant rows
    if row is None or not os.path.exists(row.storage_path):
        raise NotFoundError("file not found")
    return FileResponse(
        row.storage_path,
        media_type=row.content_type,
        filename=row.filename,
    )
