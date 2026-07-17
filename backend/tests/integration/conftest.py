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
from sqlalchemy import text
from sqlalchemy.orm import Session

# Ensure backend/ is on sys.path so `from app...` resolves during pytest.
# conftest.py is at backend/tests/integration/conftest.py → .parent.parent.parent = backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import AdminSessionLocal, SessionLocal, admin_engine, engine  # noqa: E402
from app.modules.tenant.models import Department, Tenant, User  # noqa: E402

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
