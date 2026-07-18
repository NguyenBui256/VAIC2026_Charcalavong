"""Demo-tenant seed script (Story 1.12 "Bootstrap Lite" + Epic 7 extension).

Idempotently provisions one demo Tenant ("SHB Demo") with:
- 3 Departments (Credit, Legal/Compliance, Operations)
- 3 Users across roles (builder, manager, operator) with Argon2-hashed passwords
- A 32-byte hex audit_key_id on the Tenant
- 3 Specialist Agents (Credit/Compliance/Operations Analyst), each with a
  Model selection + 1 embedded-Python Tool (§A6/§A8) — see
  `bootstrap_demo_agents_workflow.py` / `demo_agent_specs.py`
- 1 Workflow ("Business Loan Pre-Screen") ready to Run

Usage::

    cd backend
    uv run python -m scripts.bootstrap_demo_tenant
    # or
    uv run python scripts/bootstrap_demo_tenant.py

The script connects via `AdminSessionLocal` (BYPASSRLS-capable) because it runs
before any tenant context exists. It uses a find-or-create pattern keyed on the
Tenant name, user email, Agent/Tool/Workflow name so that repeated runs
produce no duplicate rows.

KB seeding (§A8 "seeded from sample policy PDFs") is intentionally SKIPPED —
see `bootstrap_demo_agents_workflow.py` module docstring for why.

References:
- PRD §A6 (Orchestrator Decomposition example), §A8 (Bootstrapping the Demo
  Tenant)
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
from app.core.ids import uuid7  # noqa: E402
from app.modules.audit.models import AuditEvaluationCriterion  # noqa: E402
from app.modules.audit.signing import get_or_create_active_key  # noqa: E402
from app.modules.tenant.models import Department, Tenant, User  # noqa: E402
from scripts.bootstrap_demo_agents_workflow import seed_agents_tools_workflow  # noqa: E402

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
DEFAULT_EVALUATION_CRITERIA = (
    (
        "Workflow objective fulfilled",
        "The workflow completed the stated user or business objective.",
    ),
    (
        "Evidence-grounded conclusion",
        "Conclusions are supported by available session evidence without unsupported claims.",
    ),
    (
        "Appropriate tool and RAG usage",
        "Tools and retrieval were selected, validated and used appropriately for the task.",
    ),
    (
        "Errors and retries handled",
        "Failures, retries and incomplete operations were handled or clearly surfaced.",
    ),
    (
        "HITL and escalation respected",
        "Human decisions, escalations and overrides were followed correctly.",
    ),
    (
        "Complete and clear output",
        "The final output is complete, internally consistent and understandable.",
    ),
)

# (email, role, department_name) — department_name must match one of the
# entries in DEPARTMENTS below.
_SEED_USERS: tuple[tuple[str, str, str], ...] = (
    ("admin@shbdemo.vaic", "builder", "Operations"),
    ("manager@shbdemo.vaic", "manager", "Credit"),
    ("ops_agent@shbdemo.vaic", "operator", "Operations"),
)

DEPARTMENTS: tuple[str, ...] = ("Credit", "Legal/Compliance", "Operations")


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
        audit_key = get_or_create_active_key(session, tenant.id)
        tenant.audit_key_id = audit_key.id
        departments, depts_created = _upsert_departments(session, tenant)
        users, users_created = _upsert_users(session, tenant, departments)
        _upsert_evaluation_criteria(session, tenant, users)
        session.commit()

        builder_user = next(u for u in users if u.role == "builder")
        awt_result = seed_agents_tools_workflow(
            session,
            tenant_id=tenant.id,
            departments=departments,
            builder_user=builder_user,
        )

    _print_summary(
        tenant, departments, users, tenant_created, depts_created, users_created
    )

    return {
        "tenant": tenant,
        "departments": departments,
        "users": users,
        "agents": awt_result["agents"],
        "workflow": awt_result["workflow"],
        "created": {
            "tenant": tenant_created,
            "departments": depts_created,
            "users": users_created,
            **awt_result["created"],
        },
    }


# ---------------------------------------------------------------------------
# Upsert helpers — find-or-create by natural key.
# ---------------------------------------------------------------------------


def _upsert_tenant(session: Any) -> tuple[Tenant, bool]:
    """Find or create the demo Tenant. Returns (tenant, created)."""
    existing = (
        session.execute(select(Tenant).where(Tenant.name == DEMO_TENANT_NAME)).scalars().first()
    )
    if existing is not None:
        print(f"[bootstrap] tenant already exists id={existing.id}")
        return existing, False

    tenant = Tenant(
        name=DEMO_TENANT_NAME,
        audit_key_id=None,
    )
    session.add(tenant)
    session.flush()  # populate tenant.id for FK references
    print(f"[bootstrap] created tenant id={tenant.id} audit_key_id={tenant.audit_key_id}")
    return tenant, True


def _upsert_departments(session: Any, tenant: Tenant) -> tuple[list[Department], int]:
    """Find or create the demo Departments under the Tenant."""
    created_count = 0
    departments: list[Department] = []
    for name in DEPARTMENTS:
        existing = (
            session.execute(
                select(Department).where(
                    Department.tenant_id == tenant.id,
                    Department.name == name,
                )
            )
            .scalars()
            .first()
        )
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
        existing = (
            session.execute(
                select(User).where(
                    User.tenant_id == tenant.id,
                    User.email == email,
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            users.append(existing)
            continue

        department = dept_by_name.get(dept_name)
        if department is None:
            raise RuntimeError(f"Department {dept_name!r} not found for user {email!r}")
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


def _upsert_evaluation_criteria(session: Any, tenant: Tenant, users: list[User]) -> None:
    owner = next((user for user in users if user.role == "manager"), users[0])
    existing = {
        value.casefold()
        for value in session.execute(
            select(AuditEvaluationCriterion.name).where(
                AuditEvaluationCriterion.tenant_id == tenant.id,
                AuditEvaluationCriterion.is_active.is_(True),
            )
        ).scalars()
    }
    for name, description in DEFAULT_EVALUATION_CRITERIA:
        if name.casefold() in existing:
            continue
        session.add(
            AuditEvaluationCriterion(
                id=uuid7(),
                tenant_id=tenant.id,
                name=name,
                description=description,
                created_by_user_id=owner.id,
                updated_by_user_id=owner.id,
            )
        )


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
