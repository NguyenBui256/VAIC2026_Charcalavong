"""Shared FastAPI dependencies + cross-cutting ID conventions (Epic 2, Phase 0).

- `get_tenant_session` — promoted verbatim from `app.modules.tenant.routes`
  (Story 1.3) so non-tenant modules can depend on it without reaching into
  the tenant module's internals (AD-1 hexagonal rule).
- `crud_audit_ids` — pins the OQ-1 stopgap convention for audit entries
  emitted by plain CRUD endpoints that happen outside a Workflow Run.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import AuthError
from app.core.db import SessionLocal
from app.core.ids import uuid7
from app.core.settings import get_settings
from app.core.tenant_context import set_tenant_session_var, tenant_context

__all__ = ["get_tenant_session", "crud_audit_ids"]


def _assume_app_role(session: Session) -> None:
    """Drop superuser privileges for this transaction.

    AD-2: the application role must not have BYPASSRLS. In production the
    runtime DSN connects via `vaic_app` directly (it's the only role the
    app holds). In tests, the DSN connects via the superuser `vaic`, so
    we explicitly `SET LOCAL ROLE vaic_app` to make RLS enforce.

    `SET LOCAL ROLE` is transaction-scoped and only takes effect if the
    current user is a member of the target role. The migration grants
    membership implicitly by creating `vaic_app` from a superuser
    context; `vaic` can SET ROLE to it.
    """
    app_role = get_settings().app_db_role
    if app_role:
        session.execute(text(f"SET LOCAL ROLE {app_role}"))


def get_tenant_session() -> Iterator[Session]:
    """Protected-endpoint dependency.

    Opens a runtime-engine session and sets `app.tenant_id` from the
    contextvar that AuthMiddleware populated. Downstream ORM/raw SQL
    queries are then subject to RLS automatically.

    Raises AuthError if no tenant context is set — defensive guard.
    """
    tenant_id = tenant_context.get()
    if tenant_id is None:
        raise AuthError("No tenant context on protected path")
    with SessionLocal() as s:
        _assume_app_role(s)
        set_tenant_session_var(s, tenant_id)
        yield s


def crud_audit_ids(entity_id: str) -> tuple[str, str]:
    """Audit-id convention for CRUD writes made OUTSIDE a Workflow Run (OQ-1).

    Stopgap: plain CRUD endpoints (e.g. Agent create/update/delete) have no
    natural `run_id`/`step_id` because they're not part of a Workflow Run.
    Until a dedicated CRUD-audit shape lands, callers MUST use:
        run_id = str(entity.id)      # the CRUD entity's own id
        step_id = uuid7()            # a fresh id identifying this audit write
        latency_ms = 0
        model = ""
    and MUST still route the audit entry through `AuditPort` (never direct
    SQL) so tenant scoping + envelope shape stay consistent.
    """
    run_id = str(entity_id)
    step_id = str(uuid7())
    return run_id, step_id
