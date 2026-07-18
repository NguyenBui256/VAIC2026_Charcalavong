"""Mini-App service — sole writer to mini_app_rows (Divergence-3).

CRUD-outside-a-Run audit ids via `crud_audit_ids` (OQ-1). Row updates are
compare-and-set on `updated_at` → ConflictError (409) on mismatch. Every
material row change funnels through `_emit_row_change` — a no-op seam that
becomes the Action Bus publish in the Epic 5 pairing (FR-17).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.deps import crud_audit_ids
from app.core.errors import ConflictError, NotFoundError
from app.core.ids import utcnow_iso_ms
from app.core.ports.audit import AuditEntry
from app.modules.mini_app.models import MiniApp, MiniAppRow
from app.modules.mini_app.schema_validation import (
    coerce_row_data,
    validate_entity_schema,
)
from app.modules.mini_app.schemas import EntitySchema, UiSpec
from app.modules.mini_app.visibility import MiniAppPrincipal


def _emit_row_change(
    session: Session, app: MiniApp, event_type: str, payload: dict[str, Any]
) -> None:
    """FR-17 App Event emission — write the action-event outbox (Actions/Events).

    Best-effort: the row is already committed by the caller; we append an
    `action_events` row (its own short commit). Import is function-local to keep
    the mini_app module decoupled from the action module at import time.
    """
    from app.modules.action.emit import emit_action_event

    row_id = payload.get("row_id")
    emit_action_event(
        session,
        tenant_id=app.tenant_id,
        app_id=app.id,
        database_id=app.database_id,
        event_type=event_type,
        row_id=uuid.UUID(row_id) if row_id else None,
        payload=payload,
    )


def _audit(entity_id: uuid.UUID, event_type: str, detail: dict[str, Any]) -> None:
    # EXACT AuditEntry shape (verified from core/ports/audit.py) — the sink
    # method is `.log(...)`, NOT `.write`; fields are run_id/step_id/agent_id/
    # ts/type/input/output/latency_ms/model. Do NOT rename (Trace Dashboard
    # depends on them). Mirrors orchestrator.service._emit_audit.
    run_id, step_id = crud_audit_ids(str(entity_id))
    PostgresAuditSink().log(
        AuditEntry(
            run_id=run_id, step_id=step_id, agent_id=str(entity_id),
            ts=utcnow_iso_ms(), type=event_type, input=detail, output={},
            latency_ms=0, model="",
        )
    )


def create_app_from_schema(
    session: Session,
    *,
    principal: MiniAppPrincipal,
    name: str,
    description: str,
    schema: EntitySchema,
    ui_spec: UiSpec,
    visibility_tier: str,
    whitelist_user_ids: list[uuid.UUID],
    created_by_agent_id: uuid.UUID | None = None,
    database_id: uuid.UUID | None = None,
) -> MiniApp:
    from app.modules.mini_app.lifecycle import plan_to_model
    from app.modules.mini_app.provisioner import build_provisioning_plan

    if principal.role not in ("builder", "admin"):
        from app.core.errors import AuthorizationError
        raise AuthorizationError("mini-app creation requires the builder role")

    plan = build_provisioning_plan(
        tenant_id=principal.tenant_id, department_id=principal.department_id or principal.tenant_id,
        owner_id=principal.user_id, name=name, description=description,
        schema=schema, ui_spec=ui_spec, visibility_tier=visibility_tier,
        whitelist_user_ids=whitelist_user_ids, created_by_agent_id=created_by_agent_id,
        database_id=database_id,
    )
    app = plan_to_model(plan)
    session.add(app)
    session.commit()
    session.refresh(app)
    _audit(app.id, "mini_app.provisioned",
           {"slug": app.slug, "visibility_tier": app.visibility_tier})
    return app


def get_app(session: Session, app_id: uuid.UUID) -> MiniApp:
    app = session.get(MiniApp, app_id)
    if app is None:
        raise NotFoundError(f"mini-app {app_id} not found")
    return app


def list_apps(session: Session) -> list[MiniApp]:
    return list(session.execute(select(MiniApp).order_by(MiniApp.created_at.desc())).scalars())


def _schema_of(app: MiniApp) -> EntitySchema:
    return validate_entity_schema(app.entity_schema)


def create_row(session: Session, app: MiniApp, principal: MiniAppPrincipal, data: dict[str, Any]) -> MiniAppRow:
    coerced = coerce_row_data(_schema_of(app), data)
    row = MiniAppRow(
        app_id=app.id, tenant_id=principal.tenant_id,
        department_id=principal.department_id or app.department_id,
        owner_id=principal.user_id, data=coerced,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    _emit_row_change(session, app, "row.created", {"row_id": str(row.id), "data": coerced})
    return row


def list_rows(session: Session, app: MiniApp) -> list[MiniAppRow]:
    stmt = select(MiniAppRow).where(MiniAppRow.app_id == app.id).order_by(MiniAppRow.created_at.desc())
    return list(session.execute(stmt).scalars())


def get_row(session: Session, app: MiniApp, row_id: uuid.UUID) -> MiniAppRow:
    row = session.get(MiniAppRow, row_id)
    if row is None or row.app_id != app.id:
        raise NotFoundError(f"row {row_id} not found")
    return row


def update_row(
    session: Session, app: MiniApp, principal: MiniAppPrincipal,
    row_id: uuid.UUID, data: dict[str, Any], expected_updated_at: datetime,
) -> MiniAppRow:
    """CAS on updated_at (Divergence-3). Mismatch -> ConflictError (409)."""
    from sqlalchemy import update as sa_update
    coerced = coerce_row_data(_schema_of(app), data)
    result = session.execute(
        sa_update(MiniAppRow)
        .where(
            MiniAppRow.id == row_id,
            MiniAppRow.app_id == app.id,
            MiniAppRow.updated_at == expected_updated_at,
        )
        .values(data=coerced, updated_at=datetime_now())
        .returning(MiniAppRow.id)
    )
    if result.first() is None:
        # Distinguish "gone" from "stale" for a correct 404 vs 409.
        exists = session.get(MiniAppRow, row_id)
        session.rollback()
        if exists is None or exists.app_id != app.id:
            raise NotFoundError(f"row {row_id} not found")
        raise ConflictError("row was modified concurrently (updated_at mismatch)")
    session.commit()
    row = session.get(MiniAppRow, row_id)
    _emit_row_change(session, app, "row.updated", {"row_id": str(row_id), "data": coerced})
    return row


def delete_row(session: Session, app: MiniApp, row_id: uuid.UUID) -> None:
    row = get_row(session, app, row_id)
    session.delete(row)
    session.commit()
    _emit_row_change(session, app, "row.deleted", {"row_id": str(row_id)})


def datetime_now() -> datetime:
    from datetime import UTC, datetime as _dt
    return _dt.now(UTC)


def serialize_app(app: MiniApp) -> dict[str, Any]:
    return {
        "id": str(app.id), "name": app.name, "slug": app.slug,
        "description": app.description, "entity_schema": app.entity_schema,
        "ui_spec": app.ui_spec, "visibility_tier": app.visibility_tier,
        "whitelist_user_ids": [str(u) for u in (app.whitelist_user_ids or [])],
        "database_id": str(app.database_id) if app.database_id else None,
        "build_status": app.build_status, "build_error": app.build_error,
        "created_at": app.created_at.isoformat(), "updated_at": app.updated_at.isoformat(),
    }


def serialize_row(row: MiniAppRow) -> dict[str, Any]:
    return {
        "id": str(row.id), "app_id": str(row.app_id), "owner_id": str(row.owner_id),
        "data": row.data, "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
