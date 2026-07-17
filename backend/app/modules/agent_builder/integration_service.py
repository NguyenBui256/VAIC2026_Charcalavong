"""API Integration CRUD service (Story 2.7 T4).

Mirrors the Story 2.6 `tool_crud.py` conventions verbatim: `tenant_context`
via RLS (never accept `tenant_id` as an argument), builder-role +
owner-or-same-department authz reused from `service._authorize_mutation`
applied SYMMETRICALLY to create and delete, soft-delete only, and one
`audit.log()` per CRUD write (AD-4).

`auth_header` is ENCRYPTED before it ever touches the DB (`app.core.crypto`,
AC2) and is NEVER included in `serialize_integration` output or any audit
payload (AC2, AC7/NFR-9) — only a masked value leaves this module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.core.deps import crud_audit_ids
from app.core.errors import NotFoundError
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.models import ApiIntegration
from app.modules.agent_builder.service import Principal, _authorize_mutation
from app.modules.agent_builder.service import get_agent as get_agent_row

__all__ = [
    "create_integration",
    "list_integrations",
    "get_integration",
    "update_integration",
    "soft_delete_integration",
    "serialize_integration",
]


def _emit_integration_audit(audit: AuditPort, integration: ApiIntegration, entry_type: str) -> None:
    """Emit one CRUD audit entry (AD-4). NEVER includes the auth header."""
    run_id, step_id = crud_audit_ids(str(integration.id))
    payload = {
        "integration_id": str(integration.id),
        "agent_id": str(integration.agent_id),
        "name": integration.name,
    }
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(integration.agent_id),
            ts=utcnow_iso_ms(),
            type=entry_type,
            input=payload,
            output=payload,
            latency_ms=0,
            model="",
        )
    )


def create_integration(
    session: Session,
    *,
    agent_id: uuid.UUID,
    principal: Principal,
    name: str,
    base_url: str,
    auth_header: str,
    schema: dict | None = None,
    audit: AuditPort | None = None,
) -> ApiIntegration:
    """Register an Integration against an Agent (AC1, AC2). Builder role required."""
    agent = get_agent_row(session, agent_id)
    _authorize_mutation(agent, principal)

    integration = ApiIntegration(
        id=uuid7(),
        tenant_id=tenant_context.get(),
        agent_id=agent.id,
        name=name,
        base_url=base_url,
        auth_header_encrypted=encrypt_secret(auth_header),
        schema_=schema,
    )
    session.add(integration)
    session.commit()
    session.refresh(integration)

    _emit_integration_audit(audit or PostgresAuditSink(), integration, "integration.created")
    return integration


def list_integrations(session: Session, *, agent_id: uuid.UUID) -> list[ApiIntegration]:
    """List non-deleted Integrations for an Agent. Tenant scoping is RLS-only."""
    return list(
        session.execute(
            select(ApiIntegration).where(
                ApiIntegration.agent_id == agent_id, ApiIntegration.is_deleted.is_(False)
            )
        )
        .scalars()
        .all()
    )


def get_integration(
    session: Session, *, agent_id: uuid.UUID, integration_id: uuid.UUID
) -> ApiIntegration:
    """Fetch a single non-deleted Integration. RLS hides cross-tenant rows."""
    integration = session.execute(
        select(ApiIntegration).where(
            ApiIntegration.id == integration_id,
            ApiIntegration.agent_id == agent_id,
            ApiIntegration.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if integration is None:
        raise NotFoundError("API Integration not found")
    return integration


def update_integration(
    session: Session,
    *,
    agent_id: uuid.UUID,
    integration_id: uuid.UUID,
    principal: Principal,
    audit: AuditPort | None = None,
    **changes: object,
) -> ApiIntegration:
    """Update mutable fields on an Integration (mirrors `tool_crud.update_tool`)."""
    integration = get_integration(session, agent_id=agent_id, integration_id=integration_id)
    agent = get_agent_row(session, agent_id)
    _authorize_mutation(agent, principal)

    if (name := changes.get("name")) is not None:
        integration.name = name  # type: ignore[assignment]
    if (base_url := changes.get("base_url")) is not None:
        integration.base_url = base_url  # type: ignore[assignment]
    if (auth_header := changes.get("auth_header")) is not None:
        integration.auth_header_encrypted = encrypt_secret(auth_header)  # type: ignore[arg-type]
    if "schema" in changes:
        integration.schema_ = changes["schema"]  # type: ignore[assignment]

    integration.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(integration)

    _emit_integration_audit(audit or PostgresAuditSink(), integration, "integration.updated")
    return integration


def soft_delete_integration(
    session: Session,
    *,
    agent_id: uuid.UUID,
    integration_id: uuid.UUID,
    principal: Principal,
    audit: AuditPort | None = None,
) -> None:
    """Soft-delete an Integration — never hard-deletes. Symmetric authz with create."""
    integration = get_integration(session, agent_id=agent_id, integration_id=integration_id)
    agent = get_agent_row(session, agent_id)
    _authorize_mutation(agent, principal)

    integration.is_deleted = True
    integration.deleted_at = datetime.now(UTC)
    session.commit()
    session.refresh(integration)

    _emit_integration_audit(audit or PostgresAuditSink(), integration, "integration.deleted")


def serialize_integration(integration: ApiIntegration) -> dict:
    """Response payload — auth header MASKED only, never full/ciphertext (AC2)."""
    try:
        plaintext = decrypt_secret(integration.auth_header_encrypted)
        masked = mask_secret(plaintext)
    except Exception:  # noqa: BLE001 -- never let a decrypt failure leak into a 500 here
        masked = "••••"
    return {
        "id": str(integration.id),
        "agent_id": str(integration.agent_id),
        "name": integration.name,
        "base_url": integration.base_url,
        "auth_header_masked": masked,
        "schema": integration.schema_,
        "last_used_at": (
            integration.last_used_at.isoformat(timespec="milliseconds")
            if integration.last_used_at
            else None
        ),
        "created_at": integration.created_at.isoformat(timespec="milliseconds"),
        "updated_at": integration.updated_at.isoformat(timespec="milliseconds"),
    }
