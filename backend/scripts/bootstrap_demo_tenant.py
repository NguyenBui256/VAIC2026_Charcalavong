"""Minimal demo-tenant seed script (Story 1.12 — Bootstrap Lite + Epic 7-thin).

Idempotently provisions one demo Tenant ("SHB Demo") with:
- 3 Departments (Credit, Compliance, Operations)
- 3 Users across roles (builder, manager, operator) with Argon2-hashed passwords
- 3 Specialist Agents (one per Department) each with a KB doc + a Tool
  (Epic 7-thin, roadmap §2 — see `demo_seed_agents.py`)
- The demo "Business Loan Pre-Screen" Workflow when the `workflows` table
  exists (defensive hook — see `demo_seed_workflow.py`)
- A 32-byte hex audit_key_id on the Tenant

Usage::

    cd backend
    uv run python -m scripts.bootstrap_demo_tenant
    # or
    uv run python scripts/bootstrap_demo_tenant.py

The script connects via `AdminSessionLocal` (BYPASSRLS-capable) because it runs
before any tenant context exists. It uses a find-or-create pattern keyed on the
Tenant name and user email so that repeated runs produce no duplicate rows.

Scope note (FR-28 / §A8): the full demo tenant spec also calls for ≥1
pre-configured Workflow. The `workflows` table does not exist yet — Story 3.1
creates it. This script logs a deferred-work message at the end instead of
attempting to seed a non-existent table. When Story 3.1 lands, extend
`_seed_workflow()` (or add a new step) to insert the pre-configured workflow.

References:
- PRD §A8 (Bootstrapping the Demo Tenant)
- FR-28 (Tenant bootstrapping — demo-ready)
- epics.md Story 1.12 ACs
"""

from __future__ import annotations

import secrets
import sys
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path bootstrap — make `from app...` resolve when invoked as a script
# (`python scripts/bootstrap_demo_tenant.py`) or as a module
# (`python -m scripts.bootstrap_demo_tenant`). When run as a module, the
# current working directory must be `backend/`.
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.auth import hash_password  # noqa: E402
from app.core.db import AdminSessionLocal  # noqa: E402
from app.modules.tenant.models import Department, Tenant, User  # noqa: E402

from scripts.demo_seed_agents import seed_agents_kb_tools  # noqa: E402
from scripts.demo_seed_workflow import seed_workflow_if_ready  # noqa: E402

__all__ = [
    "DEFAULT_PASSWORD",
    "DEMO_TENANT_NAME",
    "bootstrap_demo_tenant",
    "main",
]

# ---------------------------------------------------------------------------
# Constants — single source of truth for the demo dataset.
# ---------------------------------------------------------------------------

DEMO_TENANT_NAME: str = "SHB Demo"
DEFAULT_PASSWORD: str = "Password123!"

# (email, role, department_name) — department_name must match one of the
# entries in DEPARTMENTS below.
_SEED_USERS: tuple[tuple[str, str, str], ...] = (
    ("admin@shbdemo.vaic", "builder", "Operations"),
    ("manager@shbdemo.vaic", "manager", "Credit"),
    ("ops_agent@shbdemo.vaic", "operator", "Operations"),
)

# Compliance added for the Epic-7 demo: the "Business Loan Pre-Screen" workflow
# dispatches to a Credit, a Compliance, and an Operations Agent (rubric bar 1 —
# ≥2 specialists collaborate).
DEPARTMENTS: tuple[str, ...] = ("Credit", "Compliance", "Operations")


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def bootstrap_demo_tenant() -> dict[str, Any]:
    """Provision the demo tenant, departments, and users.

    Idempotent — safe to call multiple times. Returns a summary dict::

        {
            "tenant": <Tenant>,
            "departments": [<Department>, ...],
            "users": [<User>, ...],
            "created": {"tenant": bool, "departments": int, "users": int},
        }
    """
    print(f"[bootstrap] starting — tenant={DEMO_TENANT_NAME!r}")
    with AdminSessionLocal() as session:
        tenant, tenant_created = _upsert_tenant(session)
        departments, depts_created = _upsert_departments(session, tenant)
        users, users_created = _upsert_users(session, tenant, departments)

        owner = _builder_user(users)
        agent_counts = seed_agents_kb_tools(session, tenant, departments, owner)
        workflow_status = seed_workflow_if_ready(session, tenant, owner)

        session.commit()

    _print_summary(
        tenant, departments, users, tenant_created, depts_created, users_created
    )
    _print_agent_summary(agent_counts, workflow_status)

    return {
        "tenant": tenant,
        "departments": departments,
        "users": users,
        "created": {
            "tenant": tenant_created,
            "departments": depts_created,
            "users": users_created,
            "agents": agent_counts["agents"],
            "kb": agent_counts["kb"],
            "tools": agent_counts["tools"],
        },
        "workflow": workflow_status,
    }


def _builder_user(users: list[User]) -> User:
    """Return the seeded builder user (Agent/Workflow owner). Falls back to the
    first user so seeding never crashes if roles change."""
    for user in users:
        if user.role == "builder":
            return user
    if not users:
        raise RuntimeError("no users seeded — cannot assign Agent owner")
    return users[0]


# ---------------------------------------------------------------------------
# Upsert helpers — find-or-create by natural key.
# ---------------------------------------------------------------------------

def _upsert_tenant(session: Any) -> tuple[Tenant, bool]:
    """Find or create the demo Tenant. Returns (tenant, created)."""
    existing = session.execute(
        select(Tenant).where(Tenant.name == DEMO_TENANT_NAME)
    ).scalars().first()
    if existing is not None:
        print(f"[bootstrap] tenant already exists id={existing.id}")
        return existing, False

    audit_key = _generate_audit_key_id()
    tenant = Tenant(
        name=DEMO_TENANT_NAME,
        audit_key_id=audit_key,
    )
    session.add(tenant)
    session.flush()  # populate tenant.id for FK references
    print(
        f"[bootstrap] created tenant id={tenant.id} "
        f"audit_key_id={tenant.audit_key_id}"
    )
    return tenant, True


def _upsert_departments(
    session: Any, tenant: Tenant
) -> tuple[list[Department], int]:
    """Find or create the demo Departments under the Tenant."""
    created_count = 0
    departments: list[Department] = []
    for name in DEPARTMENTS:
        existing = session.execute(
            select(Department).where(
                Department.tenant_id == tenant.id,
                Department.name == name,
            )
        ).scalars().first()
        if existing is not None:
            departments.append(existing)
            continue
        dept = Department(
            tenant_id=tenant.id,
            name=name,
        )
        session.add(dept)
        session.flush()
        departments.append(dept)
        created_count += 1
        print(f"[bootstrap] created department name={name!r} id={dept.id}")
    return departments, created_count


def _upsert_users(
    session: Any, tenant: Tenant, departments: list[Department]
) -> tuple[list[User], int]:
    """Find or create the demo Users. Password is re-hashed only on create."""
    dept_by_name = {d.name: d for d in departments}
    created_count = 0
    users: list[User] = []
    for email, role, dept_name in _SEED_USERS:
        existing = session.execute(
            select(User).where(
                User.tenant_id == tenant.id,
                User.email == email,
            )
        ).scalars().first()
        if existing is not None:
            users.append(existing)
            continue

        department = dept_by_name.get(dept_name)
        if department is None:
            raise RuntimeError(
                f"Department {dept_name!r} not found for user {email!r}"
            )
        user = User(
            tenant_id=tenant.id,
            department_id=department.id,
            email=email,
            role=role,
            password_hash=hash_password(DEFAULT_PASSWORD),
            is_active=True,
        )
        session.add(user)
        session.flush()
        users.append(user)
        created_count += 1
        print(f"[bootstrap] created user email={email!r} role={role!r}")
    return users, created_count


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _generate_audit_key_id() -> uuid.UUID:
    """Generate a 32-byte random hex audit key, returned as a UUID.

    Per AC: `audit_key_id` is a 32-byte random hex. We store it as UUID (the
    model column type) which is the 128-bit/16-byte subset. The PRD asks for
    32-byte hex (256 bits) — a UUID's hex form is 32 hex chars == 16 bytes.
    We use `secrets.token_hex(16)` (16 bytes → 32 hex chars) and parse to UUID
    so the column type remains consistent with the migration.
    """
    hex_str = secrets.token_hex(16)  # 32 hex chars == 16 bytes of entropy
    return uuid.UUID(hex_str)


def _print_summary(
    tenant: Tenant,
    departments: list[Department],
    users: list[User],
    tenant_created: bool,
    depts_created: int,
    users_created: int,
) -> None:
    """Log the final state and credentials for the demo operator."""
    print()
    print("=" * 72)
    print("Bootstrap complete")
    print("=" * 72)
    print(f"  Tenant:       {tenant.name} (id={tenant.id})")
    print(f"  audit_key_id: {tenant.audit_key_id}")
    print(f"  Departments:  {len(departments)} ({depts_created} new)")
    for d in departments:
        print(f"    - {d.name} (id={d.id})")
    print(f"  Users:        {len(users)} ({users_created} new)")
    for u in users:
        print(f"    - {u.email:<32} role={u.role:<10} dept_id={u.department_id}")
    print()
    print("Credentials (default password for all seeded users):")
    print(f"  password: {DEFAULT_PASSWORD}")
    for u in users:
        print(f"    email: {u.email}")
    print("=" * 72)


def _print_agent_summary(agent_counts: dict[str, int], workflow_status: str) -> None:
    """Log the Agent/KB/Tool + Workflow seed outcome (Epic 7-thin)."""
    print()
    print(
        f"  Agents:       {agent_counts['agents']} new "
        f"(KB docs: {agent_counts['kb']} new, Tools: {agent_counts['tools']} new)"
    )
    print(f"  Workflow:     {workflow_status}")
    print("=" * 72)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entrypoint. Returns process exit code (0 = success)."""
    try:
        bootstrap_demo_tenant()
    except Exception as exc:  # noqa: BLE001 — top-level CLI boundary
        print(f"[bootstrap] FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
