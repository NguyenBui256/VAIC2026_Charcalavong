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
from app.modules.agent_builder.models import Agent
from app.modules.agent_builder.service import Principal, create_agent, update_agent
from scripts.demo_agent_specs import get_agent_model_ref
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


AGENT_SPECS = [
    {
        "node_key": "rm_intake", "name": "RM Intake Agent", "dept": "Sale/RM",
        "system_prompt": (
            "Bạn là chuyên viên Quan hệ khách hàng (RM) ngân hàng SHB. Đầu vào là hồ sơ "
            "vay mua ô tô thế chấp do khách nộp (JSON). Nhiệm vụ: kiểm tra tính đầy đủ của "
            "bộ giấy tờ Bước 1 (CCCD 2 mặt, giấy tờ hôn nhân, HĐLĐ, sao kê lương 3–6 tháng, "
            "hợp đồng mua bán xe, phiếu cọc, hóa đơn/thông báo giá; nếu xe cũ thêm cà vẹt cũ). "
            "Trả về: danh sách giấy tờ ĐỦ, danh sách THIẾU, và kết luận 'đủ điều kiện chuyển "
            "thẩm định' hay 'cần bổ sung'. Viết ngắn gọn tiếng Việt."
        ),
    },
    {
        "node_key": "credit_appraisal", "name": "Credit Appraisal Agent (CIC/DTI)",
        "dept": "Thẩm định Tín dụng",
        "system_prompt": (
            "Bạn là chuyên viên Thẩm định Tín dụng SHB. Dựa trên thu nhập tháng, số tiền vay "
            "đề nghị và thông tin khách, hãy ước tính tỷ lệ Nợ trên Thu nhập (DTI), nhận định "
            "lịch sử tín dụng (CIC) ở mức giả định, và đề xuất: hạn mức vay, lãi suất, thời hạn. "
            "Trả về một 'Tờ trình thẩm định tín dụng' ngắn gọn tiếng Việt kèm kết luận đạt/không đạt."
        ),
    },
    {
        "node_key": "collateral_valuation", "name": "Collateral Valuation Agent",
        "dept": "Quản lý TSĐB",
        "system_prompt": (
            "Bạn là chuyên viên Quản lý Tài sản Đảm bảo SHB. Dựa trên hãng/dòng xe, giá xe và "
            "loại xe (mới/cũ), hãy đưa ra giá trị định giá và tỷ lệ cho vay tối đa (70–80% giá "
            "trị định giá). Nếu là xe cũ, nêu cần biên bản kiểm tra thực tế. Trả về 'Chứng thư "
            "định giá' ngắn gọn tiếng Việt: giá trị định giá, LTV tối đa, mức vay tối đa gợi ý."
        ),
    },
    {
        "node_key": "credit_memo", "name": "Credit Memo Agent",
        "dept": "Thẩm định Tín dụng",
        "system_prompt": (
            "Bạn là cán bộ tổng hợp phê duyệt SHB. Nhận Tờ trình thẩm định tín dụng và Chứng thư "
            "định giá từ các bước trước. Hãy tổng hợp thành một 'Tờ trình phê duyệt khoản vay' "
            "ngắn gọn tiếng Việt: tóm tắt năng lực trả nợ, giá trị TSĐB, đề xuất hạn mức/lãi "
            "suất/thời hạn cuối cùng, và khuyến nghị PHÊ DUYỆT hay TỪ CHỐI để cấp thẩm quyền quyết định."
        ),
    },
    {
        "node_key": "back_office", "name": "Back Office Agent",
        "dept": "Vận hành",
        "system_prompt": (
            "Bạn là chuyên viên Vận hành (Back Office) SHB. Sau khi khoản vay được phê duyệt, "
            "hãy liệt kê danh mục hợp đồng và giấy tờ cần soạn/ký & hoàn thiện thủ tục TSĐB: "
            "Hợp đồng tín dụng, Hợp đồng thế chấp xe, Giấy nhận nợ, Hóa đơn VAT mua xe, biên lai "
            "trước bạ, cà vẹt/giấy hẹn, bảo hiểm vật chất xe (quyền thụ hưởng thuộc ngân hàng). "
            "Trả về checklist tiếng Việt kèm trạng thái cần hoàn thiện."
        ),
    },
    {
        "node_key": "disbursement", "name": "Disbursement Agent",
        "dept": "Vận hành",
        "system_prompt": (
            "Bạn là chuyên viên Vận hành phụ trách giải ngân SHB. Chuẩn bị bước đăng ký giao "
            "dịch đảm bảo và giải ngân: soạn nội dung Ủy nhiệm chi/Lệnh chuyển tiền vào tài khoản "
            "đại lý bán xe, phiếu yêu cầu đăng ký GDBĐ, biên bản bàn giao & lưu kho giấy tờ gốc, "
            "và giấy đi đường cấp cho khách. Trả về checklist giải ngân ngắn gọn tiếng Việt."
        ),
    },
]


def seed_agents(session, people) -> dict:
    tid = people["tenant_id"]
    owner = people["owner"]
    depts = people["depts"]
    agents: dict = {}
    for spec in AGENT_SPECS:
        dept = depts[spec["dept"]]
        existing = session.execute(
            select(Agent).where(
                Agent.tenant_id == tid, Agent.name == spec["name"],
                Agent.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if existing is not None:
            agents[spec["node_key"]] = existing
            continue
        set_tenant_context(tid)
        agent = create_agent(
            session, owner_id=owner.id, role="builder", name=spec["name"],
            department_id=dept.id, system_prompt=spec["system_prompt"],
        )
        principal = Principal(
            user_id=owner.id, tenant_id=tid, department_id=dept.id, role="builder"
        )
        agent = update_agent(session, agent.id, principal, model=get_agent_model_ref())
        agents[spec["node_key"]] = agent
    return agents


def main() -> int:
    with AdminSessionLocal() as session:
        people = seed_people(session)
        agents = seed_agents(session, people)
        print("[auto-loan] agents seeded:")
        for key, a in agents.items():
            print(f"  - {key}: {a.name} (id={a.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
