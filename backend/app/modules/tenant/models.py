"""Tenant module SQLAlchemy models.

Three foundational tables:
- `tenants`        — top-level isolation boundary; primary key IS the tenant id
- `departments`    — sub-tenant scope for KB, agents, mini-apps
- `users`          — human/system identities within a tenant

RLS policies:
- `tenants` table uses `id = current_setting('app.tenant_id')::uuid`
  (tenants are their own boundary; there is no `tenant_id` column to compare).
- `departments`, `users` use `tenant_id = current_setting('app.tenant_id')::uuid`.

All PKs are UUID v7 generated Python-side (AR-14). All timestamps are
`timestamptz` UTC (AR-14).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class Tenant(Base):
    """Top-level tenant record. The boundary of all data isolation."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    audit_key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Department(Base):
    """Department within a tenant. Bound for KB / Agent / Mini-App scope."""

    __tablename__ = "departments"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class User(Base):
    """User within a tenant. Story 1.3 adds password_hash, JWT issuance."""

    __tablename__ = "users"

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
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
