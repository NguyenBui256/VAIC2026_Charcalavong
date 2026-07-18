"""Mini-App Database model — a reusable entity-schema template (Database page).

A `mini_app_databases` row is a named, tenant-scoped `entity_schema` that
mini-apps reference via `mini_apps.database_id`. Binding copies the schema
into the app at create time; row data stays per-app (`mini_app_rows.app_id`).

RLS (accompanying migration): tenant-isolation only
`tenant_id = current_setting('app.tenant_id')::uuid` (ENABLE + FORCE).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class MiniAppDatabase(Base):
    __tablename__ = "mini_app_databases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_mini_app_databases_tenant_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    entity_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
