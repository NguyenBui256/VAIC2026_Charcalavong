"""Tenant-wide Knowledge Base store service (Sub-project A).

Documents are shared, owner-scoped (spec D1/D2), no longer agent-owned.
Ingestion/deletion route through `McpClientPort` (`rag.ingest`/`rag.delete`).
Access is enforced via `kb_grants_service` (owner + grants).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.deps import crud_audit_ids, get_mcp_client
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.ports.mcp_client import McpClientPort
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.kb_models import AgentKbDocument, KbDocument, KbDocumentGrant
from app.modules.agent_builder.service import Principal

__all__ = [
    "KB_MAX_BYTES", "KB_ALLOWED_CONTENT_TYPES", "INGEST_TIMEOUT_S",
    "upload_document", "delete_document", "list_documents", "get_document",
    "serialize_document", "_get_document_row",
]

KB_MAX_BYTES = 20 * 1024 * 1024
INGEST_TIMEOUT_S = 30
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


def upload_document(
    session: Session, *, principal: Principal, filename: str, content_type: str,
    data: bytes, department_id: uuid.UUID | None = None,
    mcp_factory: McpFactory = get_mcp_client, audit: AuditPort | None = None,
) -> KbDocument:
    """Any authenticated tenant user may upload (spec OQ-3); uploader = owner."""
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
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    _run_ingest(session, doc, data, mcp_factory)
    _emit_kb_audit(audit or PostgresAuditSink(), doc, "kb.document.uploaded")
    return doc


def list_documents(session: Session, *, principal: Principal) -> list[KbDocument]:
    """Docs the caller can access: owned OR granted (RLS already scopes tenant)."""
    granted_ids = select(KbDocumentGrant.document_id).where(
        KbDocumentGrant.user_id == principal.user_id
    )
    return list(
        session.execute(
            select(KbDocument)
            .where(or_(KbDocument.owner_id == principal.user_id, KbDocument.id.in_(granted_ids)))
            .order_by(KbDocument.created_at.desc())
        ).scalars().all()
    )


def get_document(session: Session, *, document_id: uuid.UUID, principal: Principal) -> KbDocument:
    from app.modules.agent_builder.kb_grants_service import require_access
    doc = _get_document_row(session, document_id)
    require_access(session, doc, principal.user_id)
    return doc


def delete_document(
    session: Session, *, document_id: uuid.UUID, principal: Principal,
    mcp_factory: McpFactory = get_mcp_client, audit: AuditPort | None = None,
) -> None:
    """Manager/owner only. Removes the external index + doc + refs/grants (CASCADE)."""
    from app.modules.agent_builder.kb_grants_service import require_access
    doc = _get_document_row(session, document_id)
    require_access(session, doc, principal.user_id, need_manage=True)
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


def serialize_document(doc: KbDocument, *, effective_role: str | None = None) -> dict:
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
        "effective_role": effective_role,
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
