"""Notification service — create + list + mark-read over per-user alerts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.notification.models import Notification


def create_notification(
    session: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
    category: str, title: str, body: str = "", ref: dict[str, Any] | None = None,
) -> Notification:
    """Insert one notification. Caller owns the surrounding transaction/commit."""
    n = Notification(
        tenant_id=tenant_id, user_id=user_id, category=category,
        title=title, body=body or "", ref=ref or {},
    )
    session.add(n)
    session.flush()  # assign id; caller commits
    return n


def list_notifications(session: Session, user_id: uuid.UUID, *, unread_only: bool = False) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc())
    return list(session.execute(stmt).scalars())


def mark_read(session: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    n = session.get(Notification, notification_id)
    if n is None or n.user_id != user_id:
        raise NotFoundError(f"notification {notification_id} not found")
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
    session.commit()
    session.refresh(n)
    return n


def mark_all_read(session: Session, user_id: uuid.UUID) -> int:
    result = session.execute(
        sa_update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    session.commit()
    return int(result.rowcount or 0)


def serialize_notification(n: Notification) -> dict[str, Any]:
    return {
        "id": str(n.id), "category": n.category, "title": n.title, "body": n.body,
        "ref": n.ref, "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat(),
    }
