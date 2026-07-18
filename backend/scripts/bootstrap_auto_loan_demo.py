"""Seed the Auto-Loan secured-lending demo (agents + graph workflow + mini-app + binding).

Idempotent. Run:  cd backend && uv run python -m scripts.bootstrap_auto_loan_demo

Prerequisites for a live demo:
  * A working LLM key in backend/.env (VAIC_LLM_API_KEY or ANTHROPIC_API_KEY) — agents
    execute real completions at run time (no stub adapter exists).
  * Redis reachable + an arq worker running:  uv run python -m scripts.run_worker
    (needed to build the mini-app AND to run the workflow + 5s action cron).

Demo runbook:
  1. Run this script. It prints the created IDs + login emails.
  2. Login as khachhang@shb.demo (pw Password123!) -> open mini-app
     "Hồ sơ vay thế chấp ô tô" -> fill -> Submit.
  3. Within ~5s a workflow run is created; approvers get a notification.
  4. Run: n1 -> (n2 ‖ n3) -> n4 PAUSES (awaiting_human).
  5. Login truongphong.td@shb.demo -> open the run -> node "Phê duyệt" -> Approve.
  6. n5 runs -> n6 PAUSES. Login vanhanh@shb.demo -> Approve -> run completed.
  7. Admin: route "database" shows all submitted hồ sơ; Audit shows the trace.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.auth import hash_password
from app.core.db import AdminSessionLocal
from app.core.tenant_context import set_tenant_context
from app.modules.tenant.models import Department, Tenant, User
from scripts.bootstrap_demo_tenant import bootstrap_demo_tenant

DEMO_PASSWORD = "Password123!"
TENANT_NAME = "SHB Demo"


def _get_or_create_department(session, tenant_id: uuid.UUID, name: str) -> Department:
    dept = session.execute(
        select(Department).where(
            Department.tenant_id == tenant_id, Department.name == name
        )
    ).scalar_one_or_none()
    if dept is None:
        dept = Department(tenant_id=tenant_id, name=name)
        session.add(dept)
        session.flush()
    return dept


def _get_or_create_user(
    session, tenant_id: uuid.UUID, department_id: uuid.UUID,
    email: str, role: str, full_name: str,
) -> User:
    user = session.execute(
        select(User).where(User.tenant_id == tenant_id, User.email == email)
    ).scalar_one_or_none()
    if user is None:
        user = User(
            tenant_id=tenant_id, department_id=department_id, email=email,
            role=role, password_hash=hash_password(DEMO_PASSWORD), is_active=True,
        )
        session.add(user)
        session.flush()
    return user


def seed_people(session) -> dict:
    # Ensure the base "SHB Demo" tenant + a builder user exist (idempotent).
    bootstrap_demo_tenant()
    tenant = session.execute(
        select(Tenant).where(Tenant.name == TENANT_NAME)
    ).scalar_one()
    tid = tenant.id

    depts = {
        name: _get_or_create_department(session, tid, name)
        for name in ("Sale/RM", "Thẩm định Tín dụng", "Quản lý TSĐB", "Vận hành")
    }

    owner = _get_or_create_user(
        session, tid, depts["Sale/RM"].id, "owner@shb.demo", "builder", "Chủ demo"
    )
    customer = _get_or_create_user(
        session, tid, depts["Sale/RM"].id, "khachhang@shb.demo", "member", "Khách hàng"
    )
    credit_mgr = _get_or_create_user(
        session, tid, depts["Thẩm định Tín dụng"].id,
        "truongphong.td@shb.demo", "manager", "Trưởng phòng Thẩm định",
    )
    ops = _get_or_create_user(
        session, tid, depts["Vận hành"].id, "vanhanh@shb.demo", "manager", "Vận hành",
    )
    session.commit()
    return {
        "tenant_id": tid, "owner": owner, "customer": customer,
        "credit_mgr": credit_mgr, "ops": ops, "depts": depts,
    }


def main() -> int:
    with AdminSessionLocal() as session:
        people = seed_people(session)
        print("[auto-loan] people seeded:")
        for key in ("owner", "customer", "credit_mgr", "ops"):
            u = people[key]
            print(f"  - {key}: {u.email} (id={u.id}, role={u.role})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
