"""Agent Builder SQLAlchemy models.

Story 2.1: the `agents` table — identity + department scoping only. Model/
provider/prompt-parameter columns arrive in Story 2.3; tools in Story 2.6.
Keep this model lean (Dev Notes "Scope Boundaries" — Rule of Three /
No premature abstraction).

RLS policy (Story 1.2 pattern, mirrored by the accompanying migration):
    tenant_id = current_setting('app.tenant_id')::uuid  (ENABLE + FORCE)

Soft-delete only: `is_deleted`/`deleted_at`; the migration REVOKEs DELETE
from `vaic_app` so a stray hard delete fails at the DB (AC7).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class Agent(Base):
    """A Specialist Agent — identity + department scoping (Story 2.1)."""

    __tablename__ = "agents"

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
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # Story 2.3 (AD-7): ModelRef {provider, model_name, parameters} as data.
    # Empty dict means "not yet configured" -- never validated at write time
    # beyond `provider` being a known id (AC9: unconfigured providers OK).
    model: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApiIntegration(Base):
    """A reusable named HTTP connection registered against an Agent (Story 2.7).

    `auth_header_encrypted` is CIPHERTEXT ONLY (Fernet, `app.core.crypto`) —
    there is no plaintext column, ever (AC2, NFR-6). Serialization exposes a
    masked value only (`service.serialize_integration`).
    """

    __tablename__ = "api_integrations"

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

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    auth_header_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    schema_: Mapped[dict[str, Any] | None] = mapped_column(
        "schema", JSONB, nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Tool(Base):
    """A Tool registered against an Agent (Story 2.6).

    `embedded_python` NULL => MCP-routed tool; non-NULL => sandbox-routed
    (AR-14). `header` (incl. auth) is stored but NEVER echoed to the client
    in full (NFR-9) — routes mask it in serialization.
    """

    __tablename__ = "tools"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    header: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    embedded_python: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Story 2.8 (carried item #1) — optional link to a registered
    # ApiIntegration this Tool calls through. NULL => the Tool doesn't use a
    # registered Integration (e.g. embedded_python or a standalone MCP call).
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_integrations.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
