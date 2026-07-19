"""Knowledge Base document model (Sub-project A reshape).

`KbDocument` — one row per document in the tenant-wide Knowledge Base store.
No longer agent-owned; `owner_id` is the uploader (implicit manager) and
`department_id` is now optional. Access is role-based (`builder` manages the
shared pool) plus per-agent grants: agents that may RAG over a doc are
listed in `agent_kb_documents`.

RLS policy (mirrors `agents`/`audit_trail`):
    tenant_id = current_setting('app.tenant_id')::uuid  (ENABLE + FORCE)

Hard-delete allowed (OQ-3): a KB delete is an index removal, not audit data,
so `vaic_app` retains DELETE (unlike `agents`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class KbDocument(Base):
    """A document in the tenant-wide Knowledge Base store (Sub-project A).

    No longer agent-owned. `owner_id` is the uploader (implicit manager).
    Access is role-based (`builder` manages the shared pool); agents that
    may RAG over a doc are listed in `agent_kb_documents`.
    """

    __tablename__ = "kb_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="processing", server_default="processing"
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_document_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Original uploaded bytes, retained so builders/users can view/download the
    # source file (RAG only stores chunks, not the original). `deferred=True`
    # keeps the blob out of list/get queries — loaded lazily only when the
    # content endpoint reads it. Nullable: legacy rows uploaded pre-migration
    # have no stored bytes.
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentKbDocument(Base):
    """M2M: an Agent is granted a KB document for RAG (spec D3)."""

    __tablename__ = "agent_kb_documents"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kb_documents.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
