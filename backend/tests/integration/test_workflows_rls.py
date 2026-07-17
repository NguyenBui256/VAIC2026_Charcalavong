"""AC9 — RLS applied to `workflows`; direct SQL cross-tenant returns empty.

Mirrors `test_agents_rls.py`'s pattern: `SET LOCAL ROLE vaic_app` to drop
superuser privileges, then verify tenant isolation via ORM and raw SQL.
Seeds its own Workflow rows via `AdminSessionLocal` (bypasses RLS) reusing
the `agent_seed_data` tenant/user fixtures — no new conftest fixtures
needed (Workflow rows only need tenant_id/owner_id, no department).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.orchestrator.models import Workflow


@pytest.fixture()
def seeded_workflow(agent_seed_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Seed one Workflow row per tenant (agents tenant + tenant B)."""
    from app.core.db import AdminSessionLocal

    workflow_a_id = uuid.uuid4()
    workflow_b_id = uuid.uuid4()
    with AdminSessionLocal() as s:
        s.add(
            Workflow(
                id=workflow_a_id,
                tenant_id=agent_seed_data["tenant_agents_id"],
                owner_id=agent_seed_data["builder_user_id"],
                name="Workflow A",
                description="Handle loan requests.",
            )
        )
        s.add(
            Workflow(
                id=workflow_b_id,
                tenant_id=agent_seed_data["tenant_b_id"],
                owner_id=agent_seed_data["user_b_id"],
                name="Workflow B",
                description="Handle HR requests.",
            )
        )
        s.commit()
    try:
        yield {
            **agent_seed_data,
            "workflow_a_id": workflow_a_id,
            "workflow_b_id": workflow_b_id,
        }
    finally:
        with AdminSessionLocal() as s:
            s.execute(
                text("DELETE FROM workflows WHERE id IN (:a, :b)"),
                {"a": str(workflow_a_id), "b": str(workflow_b_id)},
            )
            s.commit()


def _as_app(session: Session, tenant_id: uuid.UUID) -> None:
    """Drop superuser privileges + set RLS context for the current txn."""
    session.execute(text("SET LOCAL ROLE vaic_app"))
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def test_rls_enabled_and_forced_on_workflows(seeded_workflow: dict[str, Any]) -> None:
    """workflows has RLS ENABLE + FORCE (AC9)."""
    from app.core.db import AdminSessionLocal

    with AdminSessionLocal() as s:
        row = s.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = 'workflows'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] is True
    assert row[1] is True


def test_rls_policy_uses_tenant_id(seeded_workflow: dict[str, Any]) -> None:
    """Policy references tenant_id + current_setting (AC9)."""
    from app.core.db import AdminSessionLocal

    with AdminSessionLocal() as s:
        policies = s.execute(
            text(
                "SELECT policyname, qual, with_check FROM pg_policies "
                "WHERE tablename = 'workflows'"
            )
        ).fetchall()
    assert len(policies) >= 1
    for _name, qual, check in policies:
        assert "tenant_id" in str(qual).lower()
        assert "tenant_id" in str(check).lower()


def test_tenant_a_sees_own_workflow_orm(
    app_session: Session, seeded_workflow: dict[str, Any]
) -> None:
    """Under Tenant C's RLS context, ORM select returns only its Workflow."""
    _as_app(app_session, seeded_workflow["tenant_agents_id"])
    rows = app_session.execute(select(Workflow)).scalars().all()
    names = {r.name for r in rows}
    assert "Workflow A" in names
    assert "Workflow B" not in names


def test_cross_tenant_orm_query_returns_empty(
    app_session: Session, seeded_workflow: dict[str, Any]
) -> None:
    """Tenant C session querying Tenant B's Workflow by id returns nothing."""
    _as_app(app_session, seeded_workflow["tenant_agents_id"])
    rows = (
        app_session.execute(
            select(Workflow).where(Workflow.id == seeded_workflow["workflow_b_id"])
        )
        .scalars()
        .all()
    )
    assert rows == []


def test_cross_tenant_raw_sql_query_returns_empty(
    app_session: Session, seeded_workflow: dict[str, Any]
) -> None:
    """Raw SQL under Tenant C's context cannot read Tenant B's Workflow (AC9)."""
    _as_app(app_session, seeded_workflow["tenant_agents_id"])
    result = app_session.execute(
        text("SELECT name FROM workflows WHERE id = :wid"),
        {"wid": str(seeded_workflow["workflow_b_id"])},
    ).fetchall()
    assert result == []
