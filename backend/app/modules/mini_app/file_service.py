"""Local-disk storage for mini-app `file` field uploads.

Reuses the WorkflowFile model + `settings.workflow_files_root` (same pattern
as orchestrator/file_routes.py). Bytes land at
`{workflow_files_root}/{tenant_id}/{file_id}_{safe_name}`; the WorkflowFile
row is the tenant RLS gate. Callers gate access with the mini-app scoped
token (`_load_and_gate`) BEFORE calling here.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.ids import uuid7
from app.core.settings import get_settings
from app.modules.orchestrator.models import WorkflowFile

MAX_BYTES = 20 * 1024 * 1024  # 20 MB
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_name(name: str) -> str:
    cleaned = _SAFE.sub("_", name).strip("._") or "file"
    return cleaned[:255]


def save_upload(
    session: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID | None,
    filename: str, content_type: str, reader: Callable[[int], bytes],
) -> dict[str, Any]:
    """Stream-read via `reader(chunk_size)`, enforce the cap, persist, return a ref."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = reader(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_BYTES:
            raise ValidationError("file too large (max 20MB)", code="file_too_large")
        chunks.append(chunk)
    data = b"".join(chunks)

    file_id = uuid7()
    safe = _safe_name(filename or "file")
    root = Path(get_settings().workflow_files_root) / str(tenant_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{file_id}_{safe}"
    path.write_bytes(data)

    row = WorkflowFile(
        id=file_id, tenant_id=tenant_id, filename=safe,
        content_type=content_type or "application/octet-stream",
        size_bytes=len(data), storage_path=str(path),
        created_by=user_id,
    )
    session.add(row)
    session.commit()
    return {"id": str(row.id), "name": row.filename, "mime": row.content_type, "size": row.size_bytes}


def resolve_file(session: Session, file_id: uuid.UUID) -> WorkflowFile:
    row = session.get(WorkflowFile, file_id)  # RLS hides cross-tenant rows
    if row is None or not os.path.exists(row.storage_path):
        raise NotFoundError("file not found")
    return row
