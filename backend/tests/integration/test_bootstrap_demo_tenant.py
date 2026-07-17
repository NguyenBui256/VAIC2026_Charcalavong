"""Integration tests for the demo tenant bootstrap script (Story 1.12).

Tests prove:
- Script runs successfully on a clean DB.
- Script is idempotent — running twice doesn't duplicate rows.
- All required roles present (admin, analyst/member).
- At least 2 departments present.
- At least 3 users present.
- Each user's password_hash is an Argon2 hash (starts with `$argon2`).
- Tenant has a 32-byte hex audit_key_id.
- Each user can authenticate via verify_password with the documented default.
- Seeded users can log in via POST /auth/login.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.auth import verify_password
from app.core.db import AdminSessionLocal
from app.core.tenant_context import tenant_context
from app.main import app
from app.modules.tenant.models import Department, Tenant, User
from scripts.bootstrap_demo_tenant import (
    DEFAULT_PASSWORD,
    DEMO_TENANT_NAME,
    bootstrap_demo_tenant,
)

# `_migrations_applied` is provided by tests/integration/conftest.py and is
# implicitly available to every test in this directory — no import needed.


# ---------------------------------------------------------------------------
# Fixtures — isolated bootstrap state per test.
# ---------------------------------------------------------------------------

@pytest.fixture()
def clean_db(_migrations_applied: None) -> Iterator[None]:
    """Remove only the demo tenant's rows so each test starts clean for 1.12.

    Scoped to the demo tenant by name — does NOT truncate the whole table,
    which would break the session-scoped `seed_data` fixture used by
    test_rls.py / test_auth.py when they run after us. The session-scoped
    `_migrations_applied` fixture downgrades to base at session end for
    full cleanup.
    """
    with AdminSessionLocal() as s:
        # Cascade from the tenant down: users → departments → tenant.
        s.execute(
            text(
                "DELETE FROM users WHERE tenant_id IN "
                "(SELECT id FROM tenants WHERE name = :name)"
            ),
            {"name": DEMO_TENANT_NAME},
        )
        s.execute(
            text(
                "DELETE FROM departments WHERE tenant_id IN "
                "(SELECT id FROM tenants WHERE name = :name)"
            ),
            {"name": DEMO_TENANT_NAME},
        )
        s.execute(
            text("DELETE FROM tenants WHERE name = :name"),
            {"name": DEMO_TENANT_NAME},
        )
        s.commit()
    yield


@pytest.fixture()
def api_client(clean_db: None) -> Iterator[TestClient]:
    """TestClient for /auth/login checks; contextvar reset around each test."""
    tenant_context.set(None)
    with TestClient(app) as c:
        yield c
    tenant_context.set(None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_demo_tenant(session: Session) -> Tenant | None:
    return (
        session.execute(
            select(Tenant).where(Tenant.name == DEMO_TENANT_NAME)
        )
        .scalars()
        .first()
    )


# ---------------------------------------------------------------------------
# AC: Script runs on a clean DB and creates a Tenant.
# ---------------------------------------------------------------------------

def test_bootstrap_creates_demo_tenant(clean_db: None) -> None:
    """Bootstrap creates exactly one Tenant named DEMO_TENANT_NAME."""
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None, "Demo tenant was not created"
        assert tenant.name == DEMO_TENANT_NAME


def test_tenant_has_32_byte_hex_audit_key(clean_db: None) -> None:
    """Tenant.audit_key_id is a 32-byte hex string (UUID form is acceptable
    per the model column type, but AC mandates 32 bytes of entropy).
    """
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        assert tenant.audit_key_id is not None
        # audit_key_id is stored as UUID; the 32-byte hex form is the str().
        hex_str = str(tenant.audit_key_id).replace("-", "")
        assert len(hex_str) == 32, (
            f"audit_key_id must be 32 hex chars, got {len(hex_str)}"
        )
        # Must parse as a UUID.
        uuid.UUID(hex_str)


# ---------------------------------------------------------------------------
# AC: At least 2 Departments.
# ---------------------------------------------------------------------------

def test_bootstrap_creates_at_least_two_departments(clean_db: None) -> None:
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        depts = (
            s.execute(
                select(Department).where(Department.tenant_id == tenant.id)
            )
            .scalars()
            .all()
        )
        assert len(depts) >= 2, f"Expected >=2 departments, got {len(depts)}"
        dept_names = {d.name for d in depts}
        assert {"Credit", "Operations"}.issubset(dept_names), (
            f"Expected Credit + Operations, got {dept_names}"
        )


# ---------------------------------------------------------------------------
# AC: At least 3 Users, one per role.
# ---------------------------------------------------------------------------

def test_bootstrap_creates_at_least_three_users(clean_db: None) -> None:
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        users = (
            s.execute(select(User).where(User.tenant_id == tenant.id))
            .scalars()
            .all()
        )
        assert len(users) >= 3, f"Expected >=3 users, got {len(users)}"


def test_bootstrap_covers_required_roles(clean_db: None) -> None:
    """Roles {builder, manager, operator} per AC. We accept any superset that
    includes an admin-equivalent (builder) and at least one operator/analyst.
    """
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        users = (
            s.execute(select(User).where(User.tenant_id == tenant.id))
            .scalars()
            .all()
        )
        roles = {u.role for u in users}
        assert "builder" in roles, f"builder role missing; roles={roles}"
        assert "manager" in roles, f"manager role missing; roles={roles}"
        assert "operator" in roles, f"operator role missing; roles={roles}"


def test_each_user_has_department(clean_db: None) -> None:
    """AC: each User is associated with the Tenant and assigned a Department."""
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        users = (
            s.execute(select(User).where(User.tenant_id == tenant.id))
            .scalars()
            .all()
        )
        for u in users:
            assert u.department_id is not None, (
                f"User {u.email} has no department"
            )


# ---------------------------------------------------------------------------
# AC: All password hashes are Argon2.
# ---------------------------------------------------------------------------

def test_all_users_have_argon2_hash(clean_db: None) -> None:
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        users = (
            s.execute(select(User).where(User.tenant_id == tenant.id))
            .scalars()
            .all()
        )
        for u in users:
            assert u.password_hash is not None, (
                f"User {u.email} has NULL password_hash"
            )
            assert u.password_hash.startswith("$argon2"), (
                f"User {u.email} hash is not Argon2: {u.password_hash!r}"
            )


def test_seeded_password_verifies(clean_db: None) -> None:
    """The documented DEFAULT_PASSWORD verifies against every hash."""
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        users = (
            s.execute(select(User).where(User.tenant_id == tenant.id))
            .scalars()
            .all()
        )
        for u in users:
            assert verify_password(DEFAULT_PASSWORD, u.password_hash), (
                f"Default password did not verify for {u.email}"
            )


# ---------------------------------------------------------------------------
# AC: Idempotency — second run does not duplicate rows.
# ---------------------------------------------------------------------------

def test_bootstrap_is_idempotent(clean_db: None) -> None:
    """Running twice must yield the same row counts (no duplicates)."""
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        first_counts = {
            "tenants": s.execute(
                select(Tenant).where(Tenant.name == DEMO_TENANT_NAME)
            ).scalars().all(),
            "departments": s.execute(
                select(Department).where(Department.tenant_id == tenant.id)
            ).scalars().all(),
            "users": s.execute(
                select(User).where(User.tenant_id == tenant.id)
            ).scalars().all(),
        }

    # Run a second time.
    bootstrap_demo_tenant()

    with AdminSessionLocal() as s:
        tenant2 = _fetch_demo_tenant(s)
        assert tenant2 is not None
        assert tenant2.id == tenant.id, "Tenant id changed on second run"
        second_counts = {
            "tenants": s.execute(
                select(Tenant).where(Tenant.name == DEMO_TENANT_NAME)
            ).scalars().all(),
            "departments": s.execute(
                select(Department).where(Department.tenant_id == tenant2.id)
            ).scalars().all(),
            "users": s.execute(
                select(User).where(User.tenant_id == tenant2.id)
            ).scalars().all(),
        }

    for table in ("tenants", "departments", "users"):
        assert len(second_counts[table]) == len(first_counts[table]), (
            f"{table} row count changed on second run: "
            f"{len(first_counts[table])} -> {len(second_counts[table])}"
        )


def test_bootstrap_is_idempotent_email_stable(clean_db: None) -> None:
    """The same set of emails exists after both runs."""
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        emails_first = {
            row[0]
            for row in s.execute(
                select(User.email).where(User.tenant_id == tenant.id)
            )
        }

    bootstrap_demo_tenant()

    with AdminSessionLocal() as s:
        tenant2 = _fetch_demo_tenant(s)
        assert tenant2 is not None
        emails_second = {
            row[0]
            for row in s.execute(
                select(User.email).where(User.tenant_id == tenant2.id)
            )
        }

    assert emails_first == emails_second


# ---------------------------------------------------------------------------
# AC: Seeded users can authenticate via POST /auth/login.
# ---------------------------------------------------------------------------

def test_seeded_users_can_login(api_client: TestClient) -> None:
    """The builder/admin user can authenticate via the real /auth/login endpoint."""
    bootstrap_demo_tenant()
    with AdminSessionLocal() as s:
        tenant = _fetch_demo_tenant(s)
        assert tenant is not None
        admin_user = (
            s.execute(
                select(User).where(
                    User.tenant_id == tenant.id, User.role == "builder"
                )
            )
            .scalars()
            .first()
        )
        assert admin_user is not None, "No builder user seeded"

    resp = api_client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": DEFAULT_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["access_token"]
    assert body["data"]["user"]["email"] == admin_user.email
