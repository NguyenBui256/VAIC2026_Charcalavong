"""Tenant-wide Knowledge Base store service (Sub-project A).

Documents are shared, builder-managed (spec D1/D2 revised), no longer
agent-owned. Ingestion/deletion route through `McpClientPort`
(`rag.ingest`/`rag.delete`). Mutations gated by `require_builder`; reads
scoped by tenant via RLS.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.deps import crud_audit_ids, get_mcp_client
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.perms import require_builder
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.ports.mcp_client import McpClientPort
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.kb_models import KbDocument
from app.modules.agent_builder.service import Principal

__all__ = [
    "KB_MAX_BYTES", "KB_ALLOWED_CONTENT_TYPES", "INGEST_TIMEOUT_S",
    "upload_document", "create_pending_document", "ingest_document",
    "delete_document", "list_documents", "get_document",
    "get_document_content", "fetch_ingest_progress",
    "serialize_document", "_get_document_row",
]

KB_MAX_BYTES = 20 * 1024 * 1024
# Large PDFs (hundreds of pages) chunk into thousands of embedding calls, so
# 30s was far too short — the client timed out while vaic_tools kept indexing,
# leaving the pool row and the RAG store desynced. Ingest now runs in a
# background task (see `ingest_document`), so a generous ceiling is safe.
INGEST_TIMEOUT_S = 300
KB_ALLOWED_CONTENT_TYPES = {
    "application/pdf", "text/plain", "text/markdown", "text/x-markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_NIL_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")
McpFactory = Callable[..., McpClientPort]
logger = logging.getLogger(__name__)


def _validate_upload(content_type: str, data: bytes) -> None:
    if content_type not in KB_ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"Unsupported content_type '{content_type}'", code="unsupported_content_type")
    if len(data) > KB_MAX_BYTES:
        raise ValidationError("File exceeds the 20MB limit", code="file_too_large")


def _get_document_row(session: Session, document_id: uuid.UUID) -> KbDocument:
    doc = session.execute(
        select(KbDocument).where(KbDocument.id == document_id)
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("KB document not found")
    return doc


def _run_ingest(session: Session, doc: KbDocument, data: bytes, mcp_factory: McpFactory) -> None:
    dept = doc.department_id or _NIL_UUID
    mcp = mcp_factory(agent_department_id=dept)
    try:
        result = asyncio.run(
            asyncio.wait_for(
                mcp.call_tool(
                    "rag.ingest",
                    {
                        "document_id": str(doc.id),
                        "filename": doc.filename,
                        "content_type": doc.content_type,
                        "data": base64.b64encode(data).decode("ascii"),
                    },
                    tenant_id=doc.tenant_id,
                    department_id=dept,
                ),
                timeout=INGEST_TIMEOUT_S,
            )
        )
        if not result.success:
            # The adapter surfaces upstream failures (timeout, 4xx/5xx,
            # connection error) as success=False rather than raising, so we
            # MUST check it — otherwise a failed ingest was silently recorded
            # as "indexed" with 0 chunks.
            doc.status = "failed"
            doc.failure_reason = result.error or "Ingestion failed"
        else:
            doc.status = "indexed"
            doc.external_document_id = result.output.get("document_id")
            doc.chunk_count = int(result.output.get("chunk_count", 0))
    except TimeoutError:
        doc.status = "failed"
        doc.failure_reason = "Timeout"
    except Exception as exc:  # noqa: BLE001
        logger.exception("KB ingest failed for document %s: %s", doc.id, exc)
        doc.status = "failed"
        doc.failure_reason = "Ingestion failed"
    finally:
        doc.updated_at = datetime.now(UTC)
        session.commit()
        session.refresh(doc)


def create_pending_document(
    session: Session, *, principal: Principal, filename: str, content_type: str,
    data: bytes, department_id: uuid.UUID | None = None,
) -> KbDocument:
    """Builder-only. Persist the row in `processing` state and return it.

    Ingestion is deferred to `ingest_document` (background task) so the upload
    request returns immediately; the frontend polls the pool until the row
    settles to `indexed`/`failed`.
    """
    require_builder(principal)
    _validate_upload(content_type, data)
    doc = KbDocument(
        id=uuid7(),
        tenant_id=tenant_context.get(),
        owner_id=principal.user_id,
        department_id=department_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        status="processing",
        content=data,  # retain original bytes for the view/download endpoint
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def ingest_document(
    document_id: uuid.UUID, data: bytes, *, tenant_id: uuid.UUID,
    mcp_factory: McpFactory = get_mcp_client, audit: AuditPort | None = None,
) -> None:
    """Run RAG ingestion for an already-persisted `processing` document.

    Designed to run as a FastAPI BackgroundTask (in the threadpool), AFTER the
    upload response is sent — so it opens its OWN tenant-scoped session and
    re-establishes tenant context (the request session is already closed).
    Blocking work inside `_run_ingest` (asyncio.run) is fine in a worker thread.
    """
    from app.core.db import SessionLocal
    from app.core.deps import assume_app_role
    from app.core.tenant_context import set_tenant_session_var

    token = tenant_context.set(tenant_id)
    try:
        with SessionLocal() as session:
            assume_app_role(session)
            set_tenant_session_var(session, tenant_id)
            doc = _get_document_row(session, document_id)
            _run_ingest(session, doc, data, mcp_factory)
            _emit_kb_audit(audit or PostgresAuditSink(), doc, "kb.document.uploaded")
    finally:
        tenant_context.reset(token)


def upload_document(
    session: Session, *, principal: Principal, filename: str, content_type: str,
    data: bytes, department_id: uuid.UUID | None = None,
    mcp_factory: McpFactory = get_mcp_client, audit: AuditPort | None = None,
) -> KbDocument:
    """Synchronous create + ingest (Builder-only). Kept for callers/tests that
    want the fully-settled document in one call; the HTTP route uses the
    background path (`create_pending_document` + `ingest_document`)."""
    doc = create_pending_document(
        session, principal=principal, filename=filename,
        content_type=content_type, data=data, department_id=department_id,
    )
    _run_ingest(session, doc, data, mcp_factory)
    _emit_kb_audit(audit or PostgresAuditSink(), doc, "kb.document.uploaded")
    return doc


def list_documents(session: Session, *, principal: Principal) -> list[KbDocument]:
    """All docs in tenant (RLS already scopes tenant)."""
    return list(
        session.execute(
            select(KbDocument).order_by(KbDocument.created_at.desc())
        ).scalars().all()
    )


def get_document(session: Session, *, document_id: uuid.UUID, principal: Principal) -> KbDocument:
    return _get_document_row(session, document_id)


def get_document_content(
    session: Session, *, document_id: uuid.UUID, principal: Principal
) -> tuple[KbDocument, bytes]:
    """Return (doc, original bytes) for viewing/downloading.

    Read-only, tenant-scoped by RLS (no builder gate — any tenant user may
    view a pool document, mirroring `list_documents`). Raises NotFoundError
    when the row exists but has no stored bytes (uploaded before the content
    column existed), so the caller can surface a clean 404. Accessing
    `doc.content` triggers the deferred blob load for this single row.
    """
    doc = _get_document_row(session, document_id)
    if doc.content is None:
        raise NotFoundError("Original file is not available for this document")
    return doc, doc.content


def delete_document(
    session: Session, *, document_id: uuid.UUID, principal: Principal,
    mcp_factory: McpFactory = get_mcp_client, audit: AuditPort | None = None,
) -> None:
    """Builder only. Removes the external index + doc + refs (CASCADE)."""
    require_builder(principal)
    doc = _get_document_row(session, document_id)
    dept = doc.department_id or _NIL_UUID
    mcp = mcp_factory(agent_department_id=dept)
    asyncio.run(
        mcp.call_tool(
            "rag.delete",
            {"external_document_id": doc.external_document_id, "document_id": str(doc.id)},
            tenant_id=doc.tenant_id,
            department_id=dept,
        )
    )
    _emit_kb_audit(audit or PostgresAuditSink(), doc, "kb.document.deleted")
    session.delete(doc)  # grants + agent_kb_documents cascade at DB
    session.commit()


def fetch_ingest_progress(
    doc: KbDocument, mcp_factory: McpFactory = get_mcp_client
) -> int | None:
    """Live ingest % for a `processing` doc, via the RAG store (keyed by doc.id).

    Best-effort and fast: returns None on any error/timeout so the pool list
    never breaks or stalls just because progress couldn't be fetched.
    """
    dept = doc.department_id or _NIL_UUID
    try:
        mcp = mcp_factory(agent_department_id=dept)
        result = asyncio.run(
            asyncio.wait_for(
                mcp.call_tool(
                    "rag.progress", {"external_ref": str(doc.id)},
                    tenant_id=doc.tenant_id, department_id=dept,
                ),
                timeout=5,
            )
        )
        if result.success:
            return int(result.output.get("percent", 0))
    except Exception:  # noqa: BLE001 -- progress is non-critical
        return None
    return None


def serialize_document(doc: KbDocument) -> dict:
    return {
        "id": str(doc.id),
        "owner_id": str(doc.owner_id),
        "department_id": str(doc.department_id) if doc.department_id else None,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "status": doc.status,
        "failure_reason": doc.failure_reason,
        "chunk_count": doc.chunk_count,
        "created_at": doc.created_at.isoformat(timespec="milliseconds"),
        "updated_at": doc.updated_at.isoformat(timespec="milliseconds"),
    }


def _emit_kb_audit(audit: AuditPort, doc: KbDocument, entry_type: str) -> None:
    run_id, step_id = crud_audit_ids(str(doc.id))
    payload = {"document_id": str(doc.id), "filename": doc.filename, "status": doc.status}
    audit.log(AuditEntry(
        run_id=run_id, step_id=step_id, agent_id=str(doc.owner_id),
        ts=utcnow_iso_ms(), type=entry_type, input=payload, output=payload,
        latency_ms=0, model="",
    ))
