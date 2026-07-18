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

from app.core.deps import assume_app_role
from app.core.errors import ConflictError, NotFoundError
from app.core.tenant_context import set_tenant_context, set_tenant_session_var
from app.modules.action.models import EVENT_TYPES, ActionBinding, ActionEvent
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


# --- Worker-side resolution (called from action/worker.py inside a job) -----

# Terminal run statuses that should trigger a completion notification.
# Mirrors the terminal branch of state.py's `_RUN_CAS_SET_CLAUSES` ended_at
# CASE (orchestrator/state.py) — the subset of orchestrator.models.RUN_STATUSES
# for which a run's `ended_at` gets set. Was missing "timed_out", which left
# timed-out runs' action_events stuck at dispatched/completed_notified=false
# forever, causing perpetual re-dispatch by the 5s cron fan-out.
TERMINAL_RUN_STATUSES = {"completed", "completed_with_failures", "failed", "timed_out"}


def _reassert(session: Session, tenant_id: uuid.UUID) -> None:
    """Re-apply role + tenant RLS var after a commit (SET LOCAL is txn-scoped)."""
    set_tenant_context(tenant_id)
    assume_app_role(session)
    set_tenant_session_var(session, tenant_id)


def dispatch_pending_events(session: Session, tenant_id: uuid.UUID) -> list[str]:
    """Resolve each pending action_event -> create WorkflowRun(s) + notifications.

    Returns the list of created run ids for the caller to enqueue as
    `run_workflow` jobs. `create_run` commits internally, so we re-fetch the
    event and re-assert RLS around every commit boundary.
    """
    from app.modules.notification.service import create_notification
    from app.modules.orchestrator.service import create_run

    _reassert(session, tenant_id)
    event_ids = list(
        session.execute(
            select(ActionEvent.id)
            .where(ActionEvent.status == "pending")
            .order_by(ActionEvent.created_at)
        ).scalars()
    )

    run_ids: list[str] = []
    for event_id in event_ids:
        _reassert(session, tenant_id)
        ev = session.get(ActionEvent, event_id)
        if ev is None or ev.status != "pending":
            continue

        # No database bound -> nothing can match.
        if ev.database_id is None:
            _finish_event(session, ev, status="skipped", result={"reason": "app has no database"})
            continue

        bindings = list(
            session.execute(
                select(ActionBinding).where(
                    ActionBinding.database_id == ev.database_id,
                    ActionBinding.event_type == ev.event_type,
                    ActionBinding.is_active.is_(True),
                )
            ).scalars()
        )
        if not bindings:
            _finish_event(session, ev, status="skipped", result={"reason": "no matching active binding"})
            continue

        # Snapshot primitives before create_run commits + expires ORM state.
        app_id = str(ev.app_id)
        row_id = str(ev.row_id) if ev.row_id else None
        event_type = ev.event_type
        data = (ev.payload or {}).get("data", {})

        dispatched: list[dict[str, Any]] = []
        for b in bindings:
            binding_id = str(b.id)
            binding_name = b.name
            workflow_id = b.workflow_id
            recipients = list(b.notify_user_ids or []) or [b.owner_id]

            _reassert(session, tenant_id)
            run = create_run(
                session, workflow_id, role="builder",
                input={
                    "source": "action", "action_id": binding_id, "app_id": app_id,
                    "row_id": row_id, "event_type": event_type, "data": data,
                },
            )
            run_id = str(run.id)
            run_ids.append(run_id)

            _reassert(session, tenant_id)
            notif_ids: list[str] = []
            for uid in recipients:
                n = create_notification(
                    session, tenant_id=tenant_id, user_id=uid,
                    category="action.dispatched",
                    title=f"New submission received — {binding_name}",
                    body="A new record started background workflow processing.",
                    ref={"workflow_run_id": run_id, "app_id": app_id,
                         "action_id": binding_id, "row_id": row_id},
                )
                notif_ids.append(str(n.id))
            session.commit()
            dispatched.append({"action_id": binding_id, "run_id": run_id, "notification_ids": notif_ids})

        _reassert(session, tenant_id)
        ev = session.get(ActionEvent, event_id)
        if ev is not None:
            _finish_event(
                session, ev, status="dispatched",
                result={"dispatched": dispatched},
                workflow_run_id=uuid.UUID(dispatched[0]["run_id"]) if dispatched else None,
            )

    return run_ids


def notify_completed_events(session: Session, tenant_id: uuid.UUID) -> None:
    """Sweep dispatched events whose run reached a terminal status; notify once."""
    from app.modules.notification.service import create_notification
    from app.modules.orchestrator.models import WorkflowRun

    _reassert(session, tenant_id)
    event_ids = list(
        session.execute(
            select(ActionEvent.id).where(
                ActionEvent.status == "dispatched",
                ActionEvent.completed_notified.is_(False),
                ActionEvent.workflow_run_id.isnot(None),
            )
        ).scalars()
    )

    for event_id in event_ids:
        _reassert(session, tenant_id)
        ev = session.get(ActionEvent, event_id)
        if ev is None:
            continue
        run = session.get(WorkflowRun, ev.workflow_run_id)
        if run is None or run.status not in TERMINAL_RUN_STATUSES:
            continue

        app_id = str(ev.app_id)
        run_status = run.status
        run_id = str(run.id)
        for d in (ev.result or {}).get("dispatched", []):
            b = session.get(ActionBinding, uuid.UUID(d["action_id"]))
            if b is None:
                continue
            recipients = list(b.notify_user_ids or []) or [b.owner_id]
            for uid in recipients:
                create_notification(
                    session, tenant_id=tenant_id, user_id=uid,
                    category="action.completed",
                    title=f"Workflow {run_status} — {b.name}",
                    body="Background processing finished.",
                    ref={"workflow_run_id": run_id, "app_id": app_id},
                )
        ev.completed_notified = True
        session.commit()


def _finish_event(
    session: Session, ev: ActionEvent, *, status: str,
    result: dict[str, Any], workflow_run_id: uuid.UUID | None = None,
) -> None:
    ev.status = status
    ev.result = result
    ev.workflow_run_id = workflow_run_id
    ev.processed_at = datetime.now(UTC)
    session.commit()
