"""Orchestrator SQLAlchemy models.

Story 3.1: the `workflows` table — Workflow definition CRUD only (name,
description, constraints, owner, pre-provisioned confidence/escalation
config). `workflow_runs`/`tasks` (Run lifecycle) arrive in Story 3.2 — do
NOT add Run/Task columns here (Dev Notes "Scope Boundaries", YAGNI).

RLS policy (mirrors `agents`/`tools`, applied by the accompanying migration):
    tenant_id = current_setting('app.tenant_id')::uuid  (ENABLE + FORCE)

No soft-delete: Workflows have no DELETE AC in Story 3.1.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class Workflow(Base):
    """A Workflow definition — natural-language description + constraints.

    `description` is an opaque run-time hint passed to the Orchestrator at
    Run time; Story 3.1 never decomposes it (AC2). `confidence_threshold`
    and `escalation_timeout_seconds` are pre-provisioned here (cheap now)
    to avoid a follow-up migration for Story 3.5/3.6.
    """

    __tablename__ = "workflows"

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
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    confidence_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.7, server_default="0.7"
    )
    escalation_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300, server_default="300"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
