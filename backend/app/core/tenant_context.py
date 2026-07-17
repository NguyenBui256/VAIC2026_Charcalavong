"""Tenant context — `contextvars.ContextVar` + RLS session-variable helper.

Story 1.2 provides:
- The `ContextVar` itself.
- `set_tenant_session_var()` — issue `set_config('app.tenant_id', ...)` on a session.

Story 1.3 will populate the contextvar from the JWT via middleware.
AD-10 will extend this for arq workers by re-setting the contextvar from
the materialized job payload at worker entry.

Implementation note: we use `set_config(name, value, is_local)` rather than
`SET LOCAL app.tenant_id = :id` because Postgres `SET` does not accept
bind parameters — only literals. `set_config` is the function-call form and
is safe to parameterise.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

__all__ = [
    "tenant_context",
    "set_tenant_context",
    "reset_tenant_context",
    "set_tenant_session_var",
    "clear_tenant_session_var",
]

# Per-request / per-job tenant identifier. Set by FastAPI middleware on HTTP
# paths and by the arq worker bootstrap on background paths (AD-10).
tenant_context: ContextVar[uuid.UUID | None] = ContextVar(
    "tenant_context", default=None
)


def set_tenant_context(tenant_id: uuid.UUID | str) -> None:
    """Set the contextvar. Accepts UUID or string form."""
    tenant_context.set(uuid.UUID(str(tenant_id)))


def reset_tenant_context() -> None:
    """Reset the contextvar — call at request teardown."""
    tenant_context.set(None)


def set_tenant_session_var(session: Session, tenant_id: uuid.UUID | str) -> None:
    """Set `app.tenant_id` for the current transaction.

    Uses `set_config(name, value, is_local=true)` — the third argument makes
    the setting transaction-local, identical in scope to `SET LOCAL`. The
    caller MUST be inside a transaction (SQLAlchemy 2.x opens one implicitly
    on first execute). The setting evaporates at COMMIT/ROLLBACK, preventing
    cross-request leakage through pooled connections.

    Never swallow exceptions (consistency-conventions.md).
    """
    value = str(tenant_id)
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": value},
    )


def clear_tenant_session_var(session: Session) -> None:
    """Unset `app.tenant_id` for the current transaction.

    Used when a request legitimately has no tenant context — sets the value
    to an empty string so `current_setting(..., true)::uuid` returns NULL,
    which makes RLS policies filter everything out (no row matches).
    """
    session.execute(text("SELECT set_config('app.tenant_id', '', true)"))
