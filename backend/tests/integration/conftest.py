"""Pytest fixtures for RLS integration tests.

Strategy:
- Apply Alembic migrations once per session (against the running Postgres).
- Seed cross-tenant fixtures using `AdminSessionLocal` (BYPASSRLS-capable role).
- Per-test isolation: each test opens a fresh session against `engine` and
  runs its queries inside a transaction that it controls (BEGIN → SET LOCAL
  app.tenant_id → query → COMMIT/ROLLBACK). Seed data is committed once at
  session start.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.orm import Session

# Ensure backend/ is on sys.path so `from app...` resolves during pytest.
# conftest.py is at backend/tests/integration/conftest.py → .parent.parent.parent = backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import AdminSessionLocal, SessionLocal, admin_engine, engine  # noqa: E402
from app.core.tenant_context import tenant_context  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.agent_builder.models import Agent  # noqa: E402
from app.modules.tenant.models import Department, Tenant, User  # noqa: E402

# Shared password for seeded users in Story 1.3 tests.
_PWD = CryptContext(schemes=["argon2"], deprecated="auto")
SEED_PASSWORD = "Password123!"

# -- Session-scoped migrations ---------------------------------------------

@pytest.fixture(scope="session")
def _migrations_applied() -> Iterator[None]:
    """Apply Alembic migrations once per test session, then stamp back to base.

    Runs `alembic upgrade head` before tests; `alembic downgrade base` after.
    """
    env = {**os.environ}

    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["uv", "run", "alembic", *args],
            cwd=BACKEND_DIR,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    try:
        _run("downgrade", "base")
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"initial downgrade skipped: {e.stderr}\n")

    _run("upgrade", "head")
    yield
    try:
        _run("downgrade", "base")
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"teardown downgrade failed: {e.stderr}\n")


# -- Cross-tenant seed data ------------------------------------------------

@pytest.fixture(scope="session")
def seed_data(_migrations_applied: None) -> dict[str, dict[str, Any]]:
    """Seed two tenants + two departments + two users, return their UUIDs.

    Uses `AdminSessionLocal` so RLS does not block the inserts.
    """
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    dept_a_id = uuid.uuid4()
    dept_b_id = uuid.uuid4()
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

    with AdminSessionLocal() as s:
        # Epic 7: `test_bootstrap_demo_tenant.py`'s last test intentionally
        # leaves a live "SHB Demo" Tenant (+ Agents/Tools/Workflow) behind
        # for the smoke test. Those rows' `owner_id`/`agent_id` FKs are
        # `ondelete=RESTRICT` -- a bare `DELETE FROM users` below would
        # raise a RestrictViolation whenever this fixture resolves AFTER
        # that file has run (pytest collection order is alphabetical:
        # `test_bootstrap_demo_tenant.py` sorts before most other test
        # files). Clear the FK-dependent tables first, globally -- this
        # fixture already wipes the ENTIRE `users`/`departments`/`tenants`
        # tables unconditionally, so cascading the same wipe to their
        # dependents is consistent with its existing "reset everything"
        # contract.
        s.execute(text("DELETE FROM audit_trail"))
        s.execute(text("DELETE FROM tasks"))
        s.execute(text("DELETE FROM workflow_runs"))
        s.execute(text("DELETE FROM workflows"))
        s.execute(text("DELETE FROM tools"))
        s.execute(text("DELETE FROM agents"))
        s.execute(text("DELETE FROM users"))
        s.execute(text("DELETE FROM departments"))
        s.execute(text("DELETE FROM tenants"))
        s.commit()

        s.add(Tenant(id=tenant_a_id, name="Tenant A"))
        s.add(Tenant(id=tenant_b_id, name="Tenant B"))
        s.flush()
        s.add(Department(id=dept_a_id, tenant_id=tenant_a_id, name="Credit"))
        s.add(Department(id=dept_b_id, tenant_id=tenant_b_id, name="HR"))
        s.flush()
        s.add(
            User(
                id=user_a_id,
                tenant_id=tenant_a_id,
                department_id=dept_a_id,
                email="alice@tenanta.example",
                role="admin",
            )
        )
        s.add(
            User(
                id=user_b_id,
                tenant_id=tenant_b_id,
                department_id=dept_b_id,
                email="bob@tenantb.example",
                role="admin",
            )
        )
        s.commit()

    return {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "dept_a_id": dept_a_id,
        "dept_b_id": dept_b_id,
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
    }


# -- Per-test app session (RLS subject) ------------------------------------

@pytest.fixture()
def app_session(seed_data: dict[str, dict[str, Any]]) -> Iterator[Session]:
    """Yield a fresh Session against the runtime engine.

    Tests issue `SET LOCAL app.tenant_id` (and optionally `SET LOCAL ROLE
    vaic_app`) themselves to control the RLS context. The session is
    rolled back at teardown so no test commits anything.
    """
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


# Re-export so `from tests.integration.conftest import engine, admin_engine`
# works for ad-hoc inspection.
_ = (engine, admin_engine)


# -- Story 1.3 additions ---------------------------------------------------

@pytest.fixture(scope="session")
def auth_seed(seed_data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Set Argon2 password_hash on seeded users (Story 1.3 AC7).

    Idempotent — re-runs the UPDATE every session.
    """
    pw_hash = _PWD.hash(SEED_PASSWORD)
    with AdminSessionLocal() as s:
        s.execute(
            text("UPDATE users SET password_hash = :h WHERE email LIKE 'alice@%'"),
            {"h": pw_hash},
        )
        s.execute(
            text("UPDATE users SET password_hash = :h WHERE email LIKE 'bob@%'"),
            {"h": pw_hash},
        )
        s.commit()
    return seed_data


@pytest.fixture()
def api_client(auth_seed: dict[str, dict[str, Any]]) -> Iterator[TestClient]:
    """Yield a FastAPI TestClient.

    Resets `tenant_context` before and after each test to prove AC8 — the
    contextvar default must be None when no request is in flight.
    """
    tenant_context.set(None)
    with TestClient(app) as c:
        yield c
    tenant_context.set(None)


# -- Story 2.1 additions -----------------------------------------------------
#
# IMPORTANT: Story 1.2's `test_rls.py` asserts EXACT row counts/sets for
# TenantA/TenantB (e.g. "TenantA has exactly 1 user"). To avoid polluting
# those session-scoped fixtures, Agent CRUD tests seed their OWN dedicated
# tenant ("Tenant C") rather than adding users/departments to seed_data's
# TenantA. `tenant_b_id`/`dept_b_id`/`user_b_id` are still reused (via the
# `**auth_seed` spread) for cross-tenant isolation checks (AC3).

@pytest.fixture(scope="session")
def agent_seed_data(
    auth_seed: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Seed a dedicated tenant + 2 departments + builder/operator users.

    Story 2.1 T6.1 — isolated from seed_data's TenantA/TenantB so Story 1.2's
    exact-count RLS assertions keep holding regardless of test order:
    - `tenant_agents_id` / `dept_agents_id` / `dept_agents2_id`
    - `builder_user_id`       — role="builder", dept_agents_id (owner case)
    - `operator_user_id`      — role="operator", dept_agents_id (AC10 case)
    - `builder_dept2_user_id` — role="builder", dept_agents2_id (AC6 wrong-dept case)
    """
    tenant_agents_id = uuid.uuid4()
    dept_agents_id = uuid.uuid4()
    dept_agents2_id = uuid.uuid4()
    builder_user_id = uuid.uuid4()
    operator_user_id = uuid.uuid4()
    builder_dept2_user_id = uuid.uuid4()

    pw_hash = _PWD.hash(SEED_PASSWORD)
    with AdminSessionLocal() as s:
        s.add(Tenant(id=tenant_agents_id, name="Tenant C (Agents)"))
        s.flush()
        s.add(Department(id=dept_agents_id, tenant_id=tenant_agents_id, name="Support"))
        s.add(Department(id=dept_agents2_id, tenant_id=tenant_agents_id, name="Ops"))
        s.flush()
        s.add(
            User(
                id=builder_user_id,
                tenant_id=tenant_agents_id,
                department_id=dept_agents_id,
                email="builder@tenantc.example",
                role="builder",
                password_hash=pw_hash,
            )
        )
        s.add(
            User(
                id=operator_user_id,
                tenant_id=tenant_agents_id,
                department_id=dept_agents_id,
                email="operator@tenantc.example",
                role="operator",
                password_hash=pw_hash,
            )
        )
        s.add(
            User(
                id=builder_dept2_user_id,
                tenant_id=tenant_agents_id,
                department_id=dept_agents2_id,
                email="builder2@tenantc.example",
                role="builder",
                password_hash=pw_hash,
            )
        )
        s.commit()

    return {
        **auth_seed,
        "tenant_agents_id": tenant_agents_id,
        "dept_agents_id": dept_agents_id,
        "dept_agents2_id": dept_agents2_id,
        "builder_user_id": builder_user_id,
        "operator_user_id": operator_user_id,
        "builder_dept2_user_id": builder_dept2_user_id,
    }


@pytest.fixture()
def agent_client(agent_seed_data: dict[str, Any]) -> Iterator[TestClient]:
    """Like `api_client` but depends on the Story 2.1 seed extension."""
    tenant_context.set(None)
    with TestClient(app) as c:
        yield c
    tenant_context.set(None)


def login_token(client: TestClient, email: str) -> str:
    """POST /auth/login for a seeded user and return the access token."""
    r = client.post("/auth/login", json={"email": email, "password": SEED_PASSWORD})
    assert r.status_code == 200, f"login failed for {email}: {r.text}"
    return r.json()["data"]["access_token"]


@pytest.fixture()
def seeded_agent(agent_seed_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Seed one Agent row per tenant (A + B) via AdminSessionLocal (bypasses RLS).

    Used by RLS-focused tests that need existing rows without going through
    the API. Cleaned up after each test.
    """
    agent_a_id = uuid.uuid4()
    agent_b_id = uuid.uuid4()
    with AdminSessionLocal() as s:
        s.add(
            Agent(
                id=agent_a_id,
                tenant_id=agent_seed_data["tenant_agents_id"],
                department_id=agent_seed_data["dept_agents_id"],
                owner_id=agent_seed_data["builder_user_id"],
                name="Agent A",
                system_prompt="You are helpful.",
            )
        )
        s.add(
            Agent(
                id=agent_b_id,
                tenant_id=agent_seed_data["tenant_b_id"],
                department_id=agent_seed_data["dept_b_id"],
                owner_id=agent_seed_data["user_b_id"],
                name="Agent B",
                system_prompt="You are helpful.",
            )
        )
        s.commit()
    try:
        yield {**agent_seed_data, "agent_a_id": agent_a_id, "agent_b_id": agent_b_id}
    finally:
        with AdminSessionLocal() as s:
            s.execute(text("DELETE FROM agents WHERE id IN (:a, :b)"), {
                "a": str(agent_a_id), "b": str(agent_b_id),
            })
            s.commit()
