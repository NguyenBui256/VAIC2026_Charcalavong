"""API Integration CRUD service — tenant-scoped shared pool (Sub-project A).

Integrations are no longer agent-owned; they live at tenant level and are
managed exclusively by `builder`-role principals (`require_builder`, Task 1).
Tools reference an integration via `Tool.integration_id` (kind="integration").

`auth_header` is ENCRYPTED before it ever touches the DB (`app.core.crypto`,
AC2) and is NEVER included in `serialize_integration` output or any audit
payload (AC2, AC7/NFR-9) — only a masked value leaves this module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.core.deps import crud_audit_ids
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.perms import require_builder
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.models import ApiIntegration, Tool
from app.modules.agent_builder.service import Principal

__all__ = [
    "create_integration",
    "list_integrations",
    "get_integration",
    "update_integration",
    "delete_integration",
    "serialize_integration",
]


def _emit_integration_audit(audit: AuditPort, integration: ApiIntegration, entry_type: str) -> None:
    """Emit one CRUD audit entry (AD-4). NEVER includes the auth header."""
    run_id, step_id = crud_audit_ids(str(integration.id))
    payload = {
        "integration_id": str(integration.id),
        "tenant_id": str(integration.tenant_id),
        "name": integration.name,
    }
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(integration.tenant_id),
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
    principal: Principal,
    name: str,
    base_url: str,
    auth_header: str,
    schema: dict | None = None,
    audit: AuditPort | None = None,
) -> ApiIntegration:
    """Register a tenant-level Integration (shared pool). Builder role required."""
    require_builder(principal)

    integration = ApiIntegration(
        id=uuid7(),
        tenant_id=tenant_context.get(),
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


def list_integrations(session: Session) -> list[ApiIntegration]:
    """List non-deleted Integrations in the tenant. Tenant scoping is RLS-only."""
    return list(
        session.execute(
            select(ApiIntegration).where(ApiIntegration.is_deleted.is_(False))
        )
        .scalars()
        .all()
    )


def get_integration(session: Session, integration_id: uuid.UUID) -> ApiIntegration:
    """Fetch a single non-deleted Integration. RLS hides cross-tenant rows."""
    integration = session.execute(
        select(ApiIntegration).where(
            ApiIntegration.id == integration_id,
            ApiIntegration.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if integration is None:
        raise NotFoundError("API Integration not found")
    return integration


def update_integration(
    session: Session,
    integration_id: uuid.UUID,
    *,
    principal: Principal,
    audit: AuditPort | None = None,
    **changes: object,
) -> ApiIntegration:
    """Update mutable fields on an Integration. Builder role required."""
    require_builder(principal)
    integration = get_integration(session, integration_id)

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


def delete_integration(
    session: Session,
    integration_id: uuid.UUID,
    *,
    principal: Principal,
    audit: AuditPort | None = None,
) -> None:
    """Soft-delete an Integration — never hard-deletes. Builder role required.

    Blocked (`integration_in_use`) if any non-deleted catalog tool still
    references this integration (mirrors the `tools_integration_id_fkey`
    RESTRICT FK for the soft-delete path, which the FK itself never sees).
    """
    require_builder(principal)
    integration = get_integration(session, integration_id)

    in_use = session.execute(
        select(Tool.id).where(
            Tool.integration_id == integration_id, Tool.is_deleted.is_(False)
        )
    ).first()
    if in_use is not None:
        raise ValidationError(
            "Integration is still referenced by one or more tools",
            code="integration_in_use",
        )

    integration.is_deleted = True
    integration.deleted_at = datetime.now(UTC)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ValidationError(
            "Integration is still referenced by one or more tools",
            code="integration_in_use",
        ) from None
    session.refresh(integration)

    _emit_integration_audit(audit or PostgresAuditSink(), integration, "integration.deleted")


def serialize_integration(integration: ApiIntegration) -> dict:
    """Response payload — auth header MASKED only, never full/ciphertext (AC2)."""
    try:
        plaintext = decrypt_secret(integration.auth_header_encrypted)
        masked = mask_secret(plaintext)
    except ValidationError as exc:
        # Only the ciphertext-specific decrypt failure gets the masked
        # fallback (a legitimately undecryptable stored value should still
        # render a row). A misconfigured/missing VAIC_ENCRYPTION_KEY is a
        # deployment error, not a per-row data issue — it must fail loud
        # rather than silently rendering "••••" for every integration.
        if exc.code != "decryption_failed":
            raise
        masked = "••••"
    return {
        "id": str(integration.id),
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
