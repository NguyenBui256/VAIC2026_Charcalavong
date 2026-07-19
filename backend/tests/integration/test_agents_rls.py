"""AC9 — RLS applied to `agents`; direct SQL cross-tenant returns empty.

Mirrors `test_rls.py`'s pattern: `SET LOCAL ROLE vaic_app` to drop superuser
privileges, then verify tenant isolation via ORM and raw SQL.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.agent_builder.models import Agent


def _as_app(session: Session, tenant_id: uuid.UUID) -> None:
    """Drop superuser privileges + set RLS context for the current txn."""
    session.execute(text("SET LOCAL ROLE vaic_app"))
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def test_rls_enabled_and_forced_on_agents(seeded_agent: dict[str, Any]) -> None:
    """agents has RLS ENABLE + FORCE (AC9)."""
    from app.core.db import AdminSessionLocal

    with AdminSessionLocal() as s:
        row = s.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = 'agents'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] is True
    assert row[1] is True


def test_rls_policy_uses_tenant_id(seeded_agent: dict[str, Any]) -> None:
    """Policy references tenant_id + current_setting (AC9)."""
    from app.core.db import AdminSessionLocal

    with AdminSessionLocal() as s:
        policies = s.execute(
            text(
                "SELECT policyname, qual, with_check FROM pg_policies "
                "WHERE tablename = 'agents'"
            )
        ).fetchall()
    assert len(policies) >= 1
    for _name, qual, check in policies:
        assert "tenant_id" in str(qual).lower()
        assert "tenant_id" in str(check).lower()


def test_tenant_a_sees_own_agent_orm(
    app_session: Session, seeded_agent: dict[str, Any]
) -> None:
    """Under TenantA's RLS context, ORM select returns only TenantA's Agent."""
    _as_app(app_session, seeded_agent["tenant_agents_id"])
    rows = app_session.execute(select(Agent)).scalars().all()
    names = {r.name for r in rows}
    assert "Agent A" in names
    assert "Agent B" not in names


def test_cross_tenant_orm_query_returns_empty(
    app_session: Session, seeded_agent: dict[str, Any]
) -> None:
    """TenantA session querying TenantB's Agent by id returns nothing."""
    _as_app(app_session, seeded_agent["tenant_agents_id"])
    rows = (
        app_session.execute(
            select(Agent).where(Agent.id == seeded_agent["agent_b_id"])
        )
        .scalars()
        .all()
    )
    assert rows == []


def test_cross_tenant_raw_sql_query_returns_empty(
    app_session: Session, seeded_agent: dict[str, Any]
) -> None:
    """Raw SQL under TenantA's context cannot read TenantB's Agent row (AC9)."""
    _as_app(app_session, seeded_agent["tenant_agents_id"])
    result = app_session.execute(
        text("SELECT name FROM agents WHERE id = :aid"),
        {"aid": str(seeded_agent["agent_b_id"])},
    ).fetchall()
    assert result == []


def test_vaic_app_cannot_delete_agents(seeded_agent: dict[str, Any]) -> None:
    """DELETE is revoked from vaic_app — soft-delete only (AC7)."""
    from app.core.db import SessionLocal

    with SessionLocal() as s:
        _as_app(s, seeded_agent["tenant_agents_id"])
        try:
            raised = False
            try:
                s.execute(text("DELETE FROM agents"))
            except Exception as exc:  # noqa: BLE001
                raised = True
                msg = str(exc).lower()
                assert "permission" in msg or "insufficient" in msg
            assert raised, "DELETE must be rejected for vaic_app"
        finally:
            s.rollback()
