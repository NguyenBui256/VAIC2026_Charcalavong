"""Knowledge Base document model (Story 2.4).

`KbDocument` — one row per uploaded document on an Agent's Knowledge Base.
`department_id` is denormalized from the owning Agent so the AD-11 MCP scope
check never needs a join (Dev Notes T1.2).

RLS policy (mirrors `agents`/`audit_trail`):
    tenant_id = current_setting('app.tenant_id')::uuid  (ENABLE + FORCE)

Hard-delete allowed (OQ-3): a KB delete is an index removal, not audit data,
so `vaic_app` retains DELETE (unlike `agents`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class KbDocument(Base):
    """A document uploaded to an Agent's Knowledge Base (Story 2.4)."""

    __tablename__ = "kb_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="processing", server_default="processing"
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_document_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
