"""Orchestrator service layer — Workflow definition CRUD (Story 3.1).

Run lifecycle (decomposition/dispatch/aggregate) is Story 3.2+ — do NOT add
that logic here yet (Dev Notes "Scope Boundaries").

Domain functions read `tenant_context.get()` (via RLS on the session) —
NEVER accept `tenant_id` as an argument (consistency-conventions "Tenant
context"). `description` is treated as opaque text everywhere in this
module (AC2) — no decomposition/templating logic exists here.

Every CRUD write emits exactly one audit entry through `AuditPort` (AD-4) —
never direct SQL/ORM to `audit_trail` (AC8). Reuses the `crud_audit_ids`
stopgap (OQ-1) verbatim, per Story 3.1 Dev Notes AD-4.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.deps import crud_audit_ids
from app.core.errors import AuthorizationError, NotFoundError
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.tenant_context import tenant_context
from app.modules.orchestrator.models import Workflow

__all__ = [
    "Principal",
    "create_workflow",
    "get_workflow",
    "list_workflows",
    "update_workflow",
    "serialize_workflow",
]


@dataclass(frozen=True)
class Principal:
    """The caller's identity, as extracted from `request.state` by routes."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


def _emit_audit(
    audit: AuditPort, workflow: Workflow, entry_type: str, payload: dict
) -> None:
    """Emit one audit entry for a CRUD write (AC8). Never swallows (AD-4)."""
    run_id, step_id = crud_audit_ids(str(workflow.id))
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(workflow.id),
            ts=utcnow_iso_ms(),
            type=entry_type,
            input=payload,
            output={"workflow_id": str(workflow.id), "version": workflow.version},
            latency_ms=0,
            model="",
        )
    )


def create_workflow(
    session: Session,
    *,
    owner_id: uuid.UUID,
    role: str,
    name: str,
    description: str,
    constraints: list[str] | None = None,
    audit: AuditPort | None = None,
) -> Workflow:
    """Create a scoped Workflow (AC1, AC10). Requires builder role."""
    if role != "builder":
        raise AuthorizationError(
            "builder role required to create a Workflow", code="FORBIDDEN"
        )

    tenant_id = tenant_context.get()
    workflow = Workflow(
        id=uuid7(),
        tenant_id=tenant_id,
        owner_id=owner_id,
        name=name,
        description=description,
        constraints=constraints or [],
        version=1,
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)

    _emit_audit(
        audit or PostgresAuditSink(),
        workflow,
        "workflow.created",
        {"name": name},
    )
    return workflow


def get_workflow(session: Session, workflow_id: uuid.UUID) -> Workflow:
    """Fetch a single Workflow. RLS hides cross-tenant rows (AC4)."""
    workflow = session.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    ).scalar_one_or_none()
    if workflow is None:
        raise NotFoundError("Workflow not found")
    return workflow


def list_workflows(
    session: Session, *, search: str | None = None, owner_id: uuid.UUID | None = None
) -> list[Workflow]:
    """List Workflows. Tenant scoping is RLS-only (AC3)."""
    stmt = select(Workflow)
    if search:
        stmt = stmt.where(Workflow.name.ilike(f"%{search}%"))
    if owner_id is not None:
        stmt = stmt.where(Workflow.owner_id == owner_id)
    return list(session.execute(stmt).scalars().all())


def _authorize_mutation(principal: Principal) -> None:
    """Guard for PATCH (AC10).

    Workflows have no department scope — any builder in the tenant may
    edit any Workflow (simpler than Agent's dept-based rule, per T3.5).
    """
    if principal.role != "builder":
        raise AuthorizationError(
            "builder role required to update a Workflow", code="FORBIDDEN"
        )


def update_workflow(
    session: Session,
    workflow_id: uuid.UUID,
    principal: Principal,
    *,
    audit: AuditPort | None = None,
    **changes: object,
) -> Workflow:
    """Update mutable fields on a Workflow, bumping `version` (AC6, AC8)."""
    workflow = get_workflow(session, workflow_id)
    _authorize_mutation(principal)

    allowed_fields = {
        "name",
        "description",
        "constraints",
        "confidence_threshold",
        "escalation_timeout_seconds",
    }
    applied: dict[str, object] = {}
    for key, value in changes.items():
        if key not in allowed_fields or value is None:
            continue
        setattr(workflow, key, value)
        applied[key] = value

    workflow.version += 1
    workflow.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(workflow)

    _emit_audit(audit or PostgresAuditSink(), workflow, "workflow.updated", applied)
    return workflow


def serialize_workflow(workflow: Workflow) -> dict:
    """Response payload shape (AR-14: ISO 8601 ms timestamps)."""
    return {
        "id": str(workflow.id),
        "tenant_id": str(workflow.tenant_id),
        "owner_id": str(workflow.owner_id),
        "name": workflow.name,
        "description": workflow.description,
        "constraints": workflow.constraints or [],
        "confidence_threshold": workflow.confidence_threshold,
        "escalation_timeout_seconds": workflow.escalation_timeout_seconds,
        "version": workflow.version,
        "created_at": workflow.created_at.isoformat(timespec="milliseconds"),
        "updated_at": workflow.updated_at.isoformat(timespec="milliseconds"),
    }
