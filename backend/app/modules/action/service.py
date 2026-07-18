"""Action service — CRUD over action_bindings (Database-event -> Workflow config).

Worker-side resolution (`dispatch_pending_events` / `notify_completed_events`) is
appended in Task 5; this file starts with binding CRUD only.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.action.models import EVENT_TYPES, ActionBinding
from app.modules.mini_app.visibility import MiniAppPrincipal


def list_bindings(session: Session) -> list[ActionBinding]:
    return list(
        session.execute(select(ActionBinding).order_by(ActionBinding.created_at.desc())).scalars()
    )


def get_binding(session: Session, binding_id: uuid.UUID) -> ActionBinding:
    b = session.get(ActionBinding, binding_id)
    if b is None:
        raise NotFoundError(f"action binding {binding_id} not found")
    return b


def create_binding(
    session: Session, *, principal: MiniAppPrincipal, name: str,
    database_id: uuid.UUID, event_type: str, workflow_id: uuid.UUID,
    notify_user_ids: list[uuid.UUID], is_active: bool = True,
) -> ActionBinding:
    _validate_event_type(event_type)
    if _name_taken(session, principal.tenant_id, name):
        raise ConflictError(f"an action named '{name}' already exists")
    b = ActionBinding(
        tenant_id=principal.tenant_id, owner_id=principal.user_id, name=name,
        database_id=database_id, event_type=event_type, workflow_id=workflow_id,
        notify_user_ids=notify_user_ids, is_active=is_active,
    )
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def update_binding(
    session: Session, binding_id: uuid.UUID, *,
    name: str | None, database_id: uuid.UUID | None, event_type: str | None,
    workflow_id: uuid.UUID | None, notify_user_ids: list[uuid.UUID] | None, is_active: bool | None,
) -> ActionBinding:
    b = get_binding(session, binding_id)
    if name is not None and name != b.name:
        if _name_taken(session, b.tenant_id, name):
            raise ConflictError(f"an action named '{name}' already exists")
        b.name = name
    if database_id is not None:
        b.database_id = database_id
    if event_type is not None:
        _validate_event_type(event_type)
        b.event_type = event_type
    if workflow_id is not None:
        b.workflow_id = workflow_id
    if notify_user_ids is not None:
        b.notify_user_ids = notify_user_ids
    if is_active is not None:
        b.is_active = is_active
    b.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(b)
    return b


def delete_binding(session: Session, binding_id: uuid.UUID) -> None:
    b = get_binding(session, binding_id)
    session.delete(b)
    session.commit()


def serialize_binding(b: ActionBinding) -> dict[str, Any]:
    return {
        "id": str(b.id), "name": b.name, "database_id": str(b.database_id),
        "event_type": b.event_type, "workflow_id": str(b.workflow_id),
        "notify_user_ids": [str(u) for u in (b.notify_user_ids or [])],
        "is_active": b.is_active, "owner_id": str(b.owner_id),
        "created_at": b.created_at.isoformat(), "updated_at": b.updated_at.isoformat(),
    }


def _validate_event_type(event_type: str) -> None:
    if event_type not in EVENT_TYPES:
        raise ConflictError(f"event_type must be one of {EVENT_TYPES}")


def _name_taken(session: Session, tenant_id: uuid.UUID, name: str) -> bool:
    stmt = select(ActionBinding.id).where(
        ActionBinding.tenant_id == tenant_id, ActionBinding.name == name
    )
    return session.execute(stmt).first() is not None
