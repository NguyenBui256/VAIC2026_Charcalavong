"""Knowledge Base ingestion service (Story 2.4).

Domain functions read `tenant_context.get()` via RLS on the session — NEVER
accept `tenant_id` as an argument (AR-14 tenant context convention). The KB
scope is always the calling Agent's own Department, derived from the Agent
record — never caller-supplied (AD-11).

Ingestion/deletion route through `McpClientPort` (AD-3) — VAIC is an MCP
client only; the stub (`core/adapters/mcp_client_stub.py`) fabricates a
successful result until the real MCP server lands.

OQ-4 (sync vs async ingestion): this MVP uses a synchronous ingest wrapped
in a 30s timeout inside the request (acceptable fallback per the story's
Dev Notes; ARQ wiring is a follow-up, not blocking this slice).
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.deps import crud_audit_ids, get_mcp_client
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.ports.mcp_client import McpClientPort
from app.modules.agent_builder.kb_models import KbDocument
from app.modules.agent_builder.models import Agent
from app.modules.agent_builder.service import Principal, _authorize_mutation
from app.modules.agent_builder.service import get_agent as get_agent_row

__all__ = [
    "KB_MAX_BYTES",
    "KB_ALLOWED_CONTENT_TYPES",
    "INGEST_TIMEOUT_S",
    "upload_document",
    "delete_document",
    "list_documents",
    "serialize_document",
]

KB_MAX_BYTES = 20 * 1024 * 1024  # 20MB (AC3)
INGEST_TIMEOUT_S = 30  # AC4

KB_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

McpFactory = Callable[..., McpClientPort]


def _validate_upload(content_type: str, data: bytes) -> None:
    """Server-side defense-in-depth (AC3, T7.2)."""
    if content_type not in KB_ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            f"Unsupported content_type '{content_type}'",
            code="unsupported_content_type",
        )
    if len(data) > KB_MAX_BYTES:
        raise ValidationError(
            "File exceeds the 20MB limit", code="file_too_large"
        )


def _run_ingest(
    session: Session,
    agent: Agent,
    doc: KbDocument,
    data: bytes,
    mcp_factory: McpFactory,
) -> None:
    """Call `rag.ingest` with a 30s timeout; flip status on outcome (AC2, AC4)."""
    mcp = mcp_factory(agent_department_id=agent.department_id)
    try:
        result = asyncio.run(
            asyncio.wait_for(
                mcp.call_tool(
                    "rag.ingest",
                    {
                        "agent_id": str(agent.id),
                        "filename": doc.filename,
                        "content_type": doc.content_type,
                        "data": base64.b64encode(data).decode("ascii"),
                    },
                    tenant_id=agent.tenant_id,
                    department_id=agent.department_id,
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
    except Exception as exc:  # noqa: BLE001 -- captured as failure_reason, never swallowed
        doc.status = "failed"
        doc.failure_reason = str(exc)
    finally:
        doc.updated_at = datetime.now(UTC)
        session.commit()
        session.refresh(doc)


def upload_document(
    session: Session,
    *,
    agent_id: uuid.UUID,
    principal: Principal,
    filename: str,
    content_type: str,
    data: bytes,
    mcp_factory: McpFactory = get_mcp_client,
    audit: AuditPort | None = None,
) -> KbDocument:
    """Validate, persist, and ingest a KB document (AC1, AC2, AC3, AC4, AC6)."""
    _ = principal  # any authenticated tenant member may upload (no role gate)
    agent = get_agent_row(session, agent_id)
    _validate_upload(content_type, data)

    doc = KbDocument(
        id=uuid7(),
        tenant_id=agent.tenant_id,
        agent_id=agent.id,
        department_id=agent.department_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        status="processing",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    _run_ingest(session, agent, doc, data, mcp_factory)
    _emit_kb_audit(audit or PostgresAuditSink(), agent, doc, "kb.document.uploaded")
    return doc


def _get_document(session: Session, document_id: uuid.UUID) -> KbDocument:
    doc = session.execute(
        select(KbDocument).where(KbDocument.id == document_id)
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("KB document not found")
    return doc


def delete_document(
    session: Session,
    *,
    document_id: uuid.UUID,
    principal: Principal,
    mcp_factory: McpFactory = get_mcp_client,
    audit: AuditPort | None = None,
) -> None:
    """Remove the document + its chunks/embeddings via `rag.delete` (AC5, AC6)."""
    doc = _get_document(session, document_id)
    agent = get_agent_row(session, doc.agent_id)
    _authorize_mutation(agent, principal)

    mcp = mcp_factory(agent_department_id=agent.department_id)
    asyncio.run(
        mcp.call_tool(
            "rag.delete",
            {"external_document_id": doc.external_document_id, "agent_id": str(agent.id)},
            tenant_id=agent.tenant_id,
            department_id=agent.department_id,
        )
    )

    _emit_kb_audit(audit or PostgresAuditSink(), agent, doc, "kb.document.deleted")
    session.delete(doc)
    session.commit()


def list_documents(session: Session, *, agent_id: uuid.UUID) -> list[KbDocument]:
    """List KB documents for an Agent. NO tenant_id filter — RLS owns that."""
    return list(
        session.execute(
            select(KbDocument).where(KbDocument.agent_id == agent_id)
        )
        .scalars()
        .all()
    )


def serialize_document(doc: KbDocument) -> dict:
    """Response payload shape (AR-14: ISO 8601 ms timestamps)."""
    return {
        "id": str(doc.id),
        "agent_id": str(doc.agent_id),
        "filename": doc.filename,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "status": doc.status,
        "failure_reason": doc.failure_reason,
        "chunk_count": doc.chunk_count,
        "created_at": doc.created_at.isoformat(timespec="milliseconds"),
        "updated_at": doc.updated_at.isoformat(timespec="milliseconds"),
    }


def _emit_kb_audit(
    audit: AuditPort, agent: Agent, doc: KbDocument, entry_type: str
) -> None:
    """Emit one audit entry — metadata only, never document bytes/text (NFR-9)."""
    run_id, step_id = crud_audit_ids(str(agent.id))
    payload = {
        "agent_id": str(agent.id),
        "document_id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status,
    }
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(agent.id),
            ts=utcnow_iso_ms(),
            type=entry_type,
            input=payload,
            output=payload,
            latency_ms=0,
            model="",
        )
    )
