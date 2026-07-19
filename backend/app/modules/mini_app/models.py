"""Mini-App SQLAlchemy models (Epic 4).

Two tables:
- `mini_apps`   — one row per generated app: schema + ui_spec (JSONB),
  visibility tier + whitelist, build status, bundle path.
- `mini_app_rows` — one row per user record across ALL apps (single-table
  JSONB namespace, PRD FR-13). The four access fields are NOT NULL.

Enum-ish columns use String + CheckConstraint (mirrors orchestrator.models
`RUN_STATUSES` pattern) so adding a value never needs an ALTER TYPE.

RLS (applied by the accompanying migration) is tenant-isolation only:
`tenant_id = current_setting('app.tenant_id')::uuid` (ENABLE + FORCE).
Visibility-tier enforcement lives in `visibility.py` at the app layer
(the platform only propagates `app.tenant_id` as a GUC — see spec §4).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7

VISIBILITY_TIERS = ("public", "need_auth", "private")
BUILD_STATUSES = ("pending", "building", "ready", "failed")


class MiniApp(Base):
    __tablename__ = "mini_apps"
    __table_args__ = (
        CheckConstraint(
            f"visibility_tier IN {VISIBILITY_TIERS!r}",
            name="ck_mini_apps_visibility_tier",
        ),
        CheckConstraint(
            f"build_status IN {BUILD_STATUSES!r}", name="ck_mini_apps_build_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    entity_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ui_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    visibility_tier: Mapped[str] = mapped_column(
        String(16), nullable=False, default="need_auth", server_default="need_auth"
    )
    whitelist_user_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}"
    )
    build_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    build_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    bundle_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    database_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mini_app_databases.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MiniAppRow(Base):
    __tablename__ = "mini_app_rows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mini_apps.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
