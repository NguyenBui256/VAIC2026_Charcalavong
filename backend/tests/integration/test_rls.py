"""AC2–AC5, AC9 — RLS cross-tenant isolation tests.

These tests prove AD-2 holds:
- TenantA session can read only TenantA rows.
- TenantB rows are invisible via ORM and raw SQL.
- `tenants` table self-isolates via `id` policy.
- `vaic_app` role has BYPASSRLS revoked.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.tenant.models import Department, Tenant, User

# -- Helper: assume the vaic_app role within a session ----------------------
#
# `vaic` (the docker postgres superuser) bypasses RLS implicitly. The app
# role `vaic_app` is NOLOGIN, NOBYPASSRLS. Tests SET LOCAL ROLE vaic_app
# inside their transaction to drop superuser privileges and become subject
# to RLS.


def _as_app(session: Session, tenant_id: uuid.UUID) -> None:
    """Drop superuser privileges + set RLS context for the current txn."""
    session.execute(text("SET LOCAL ROLE vaic_app"))
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


# -- AC2: tenant sees its own rows -----------------------------------------


def test_tenant_a_sees_own_users_orm(
    app_session: Session, seed_data: dict[str, dict[str, Any]]
) -> None:
    """Under TenantA's RLS context, ORM select returns TenantA users only."""
    _as_app(app_session, seed_data["tenant_a_id"])
    rows = app_session.execute(select(User)).scalars().all()
    emails = {r.email for r in rows}
    assert "alice@tenanta.example" in emails
    assert "bob@tenantb.example" not in emails


def test_tenant_a_sees_own_departments_orm(
    app_session: Session, seed_data: dict[str, dict[str, Any]]
) -> None:
    _as_app(app_session, seed_data["tenant_a_id"])
    rows = app_session.execute(select(Department)).scalars().all()
    assert {r.name for r in rows} == {"Credit"}


def test_tenant_a_sees_own_tenant_row_only(
    app_session: Session, seed_data: dict[str, dict[str, Any]]
) -> None:
    """`tenants` policy uses `id` — TenantA sees only its own tenant row."""
    _as_app(app_session, seed_data["tenant_a_id"])
    rows = app_session.execute(select(Tenant)).scalars().all()
    assert {r.name for r in rows} == {"Tenant A"}


# -- AC3 + AC4: cross-tenant query returns empty under ORM and raw SQL ------


def test_cross_tenant_orm_query_returns_empty(
    app_session: Session, seed_data: dict[str, dict[str, Any]]
) -> None:
    """Under TenantA's session, querying for TenantB's user returns nothing."""
    _as_app(app_session, seed_data["tenant_a_id"])
    rows = (
        app_session.execute(select(User).where(User.id == seed_data["user_b_id"])).scalars().all()
    )
    assert rows == []


def test_cross_tenant_raw_sql_query_returns_empty(
    app_session: Session, seed_data: dict[str, dict[str, Any]]
) -> None:
    """Under TenantA's session, raw SELECT on users returns only TenantA's rows."""
    _as_app(app_session, seed_data["tenant_a_id"])
    result = app_session.execute(text("SELECT email FROM users")).fetchall()
    emails = {r[0] for r in result}
    assert emails == {"alice@tenanta.example"}


def test_cross_tenant_raw_sql_specific_id_returns_empty(
    app_session: Session, seed_data: dict[str, dict[str, Any]]
) -> None:
    """Even when targeting TenantB's user by id, raw SQL returns nothing."""
    _as_app(app_session, seed_data["tenant_a_id"])
    result = app_session.execute(
        text("SELECT email FROM users WHERE id = :uid"),
        {"uid": str(seed_data["user_b_id"])},
    ).fetchall()
    assert result == []


def test_cross_tenant_aggregate_count_excludes_other_tenant(
    app_session: Session, seed_data: dict[str, dict[str, Any]]
) -> None:
    """COUNT(*) must reflect only the current tenant's rows."""
    _as_app(app_session, seed_data["tenant_a_id"])
    count = app_session.execute(select(func.count()).select_from(User)).scalar()
    assert count == 1


# -- AC5: app role must NOT have BYPASSRLS ----------------------------------


def test_vaic_app_role_lacks_bypassrls(
    app_session: Session, seed_data: dict[str, dict[str, Any]]
) -> None:
    """The `vaic_app` role has BYPASSRLS = false."""
    rolbypassrls = app_session.execute(
        text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'vaic_app'")
    ).scalar()
    assert rolbypassrls is False
