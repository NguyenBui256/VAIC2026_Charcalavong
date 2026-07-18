"""Outbox writer — the mini_app row-change seam's Action Bus publish (FR-17).

Inserts one `action_events` row per material row change. Best-effort outbox:
the mini_app service commits the row first, then this appends the event in the
same session (a short follow-up commit). The ARQ fan-out consumes pending rows.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.action.models import ActionEvent


def emit_action_event(
    session: Session, *, tenant_id: uuid.UUID, app_id: uuid.UUID,
    database_id: uuid.UUID | None, event_type: str, row_id: uuid.UUID | None,
    payload: dict[str, Any],
) -> None:
    event = ActionEvent(
        tenant_id=tenant_id, app_id=app_id, database_id=database_id,
        event_type=event_type, row_id=row_id, payload=payload, status="pending",
    )
    session.add(event)
    session.commit()
