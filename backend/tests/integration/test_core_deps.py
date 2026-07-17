"""Phase 0 (Epic 2) — `get_tenant_session` promoted to `app.core.deps`.

Proves:
- `from app.core.deps import get_tenant_session` imports successfully.
- Using the dependency, a tenant-scoped session enforces RLS: querying for
  another tenant's row returns EMPTY (cross-tenant isolation holds after
  the move, identical to the pre-move behavior in `tenant/routes.py`).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenant_context import reset_tenant_context, set_tenant_context
from app.modules.tenant.models import User


def test_get_tenant_session_importable_from_core_deps() -> None:
    """`get_tenant_session` must live in `app.core.deps` (shared module)."""
    from app.core.deps import get_tenant_session

    assert callable(get_tenant_session)


def test_get_tenant_session_enforces_cross_tenant_isolation(
    seed_data: dict[str, dict[str, Any]],
) -> None:
    """Under TenantA's context, the yielded session cannot see TenantB's user."""
    from app.core.deps import get_tenant_session

    set_tenant_context(seed_data["tenant_a_id"])
    try:
        gen = get_tenant_session()
        session: Session = next(gen)
        try:
            rows = (
                session.execute(
                    select(User).where(User.id == seed_data["user_b_id"])
                )
                .scalars()
                .all()
            )
            assert rows == []

            # Sanity: TenantA's own user IS visible under the same session.
            own_rows = (
                session.execute(
                    select(User).where(User.id == seed_data["user_a_id"])
                )
                .scalars()
                .all()
            )
            assert len(own_rows) == 1
        finally:
            # Exhaust the generator to trigger its `with SessionLocal()` exit.
            next(gen, None)
    finally:
        reset_tenant_context()
