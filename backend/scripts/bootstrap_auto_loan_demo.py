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
from app.modules.orchestrator.models import Workflow
from app.modules.orchestrator.graph_authoring import replace_workflow_graph
from app.modules.orchestrator.service import create_workflow
from app.modules.mini_app import database_service
from app.modules.mini_app import service as mini_app_service
from app.modules.mini_app.database_models import MiniAppDatabase
from app.modules.mini_app.models import MiniApp
from app.modules.mini_app.schema_validation import validate_entity_schema, validate_ui_spec
from app.modules.mini_app.visibility import MiniAppPrincipal
from app.modules.action.models import ActionBinding
from app.modules.action.service import create_binding

DEMO_PASSWORD = "Password123!"
TENANT_NAME = "SHB Demo"

WORKFLOW_NAME = "Thẩm định & Giải ngân Vay Thế chấp Ô tô"
WORKFLOW_DESC = (
    "Quy trình 6 bước thẩm định và giải ngân vay thế chấp mua ô tô: tiếp nhận hồ sơ, "
    "thẩm định tín dụng (CIC/DTI), định giá TSĐB, phê duyệt (duyệt thật), ký hợp đồng & "
    "hoàn thiện TSĐB, đăng ký GDBĐ & giải ngân (duyệt thật)."
)

DATABASE_NAME = "Hồ sơ vay thế chấp ô tô"
APP_NAME = "Đăng ký vay mua ô tô (SHB)"

BINDING_NAME = "Auto-Loan Intake → Thẩm định & Giải ngân"

LOAN_ENTITY_SCHEMA = {
    "fields": [
        {"name": "ho_ten", "type": "string", "label": "Họ và tên người vay", "required": True, "maxLength": 255},
        {"name": "cccd", "type": "string", "label": "Số CCCD", "required": True, "maxLength": 20},
        {"name": "sdt", "type": "string", "label": "Số điện thoại", "required": True, "maxLength": 15},
        {"name": "tinh_trang_hon_nhan", "type": "enum", "label": "Tình trạng hôn nhân",
         "required": True, "options": ["Độc thân", "Đã kết hôn"]},
        {"name": "thu_nhap_thang", "type": "number", "label": "Thu nhập/tháng (VND)", "required": True, "min": 0},
        {"name": "loai_xe", "type": "enum", "label": "Loại xe", "required": True,
         "options": ["Xe mới", "Xe cũ"]},
        {"name": "hang_dong_xe", "type": "string", "label": "Hãng/Dòng xe", "required": True, "maxLength": 255},
        {"name": "gia_xe", "type": "number", "label": "Giá xe (VND)", "required": True, "min": 0},
        {"name": "so_tien_vay_de_nghi", "type": "number", "label": "Số tiền vay đề nghị (VND)",
         "required": True, "min": 0},
        {"name": "gt_cccd", "type": "boolean", "label": "Đã nộp CCCD (2 mặt)"},
        {"name": "gt_hon_nhan", "type": "boolean", "label": "Đã nộp giấy tờ hôn nhân/độc thân"},
        {"name": "gt_hdld", "type": "boolean", "label": "Đã nộp HĐ lao động"},
        {"name": "gt_sao_ke_luong", "type": "boolean", "label": "Đã nộp sao kê lương 3–6 tháng"},
        {"name": "gt_hd_mua_ban_xe", "type": "boolean", "label": "Đã nộp HĐ mua bán xe"},
        {"name": "gt_phieu_coc", "type": "boolean", "label": "Đã nộp phiếu cọc/vốn tự có"},
        {"name": "gt_hoa_don_gia", "type": "boolean", "label": "Đã nộp hóa đơn/thông báo giá (xe mới)"},
        {"name": "gt_ca_vet_cu", "type": "boolean", "label": "Đã nộp cà vẹt cũ (xe cũ)"},
        {"name": "link_ho_so", "type": "longtext", "label": "Link ảnh/scan hồ sơ"},
    ],
    "primary_display": "ho_ten",
}


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


def seed_mini_app(session, people):
    tid = people["tenant_id"]
    owner = people["owner"]
    principal = MiniAppPrincipal(
        user_id=owner.id, tenant_id=tid,
        department_id=owner.department_id, role="builder",
    )

    db = session.execute(
        select(MiniAppDatabase).where(
            MiniAppDatabase.tenant_id == tid, MiniAppDatabase.name == DATABASE_NAME
        )
    ).scalar_one_or_none()
    if db is None:
        set_tenant_context(tid)
        db = database_service.create_database(
            session, principal=principal, name=DATABASE_NAME,
            description="Hồ sơ khách nộp để vay thế chấp mua ô tô.",
            entity_schema=LOAN_ENTITY_SCHEMA,
        )

    app = session.execute(
        select(MiniApp).where(MiniApp.tenant_id == tid, MiniApp.name == APP_NAME)
    ).scalar_one_or_none()
    if app is None:
        set_tenant_context(tid)
        schema = validate_entity_schema(db.entity_schema)
        ui_spec = validate_ui_spec({})
        app = mini_app_service.create_app_from_schema(
            session, principal=principal, name=APP_NAME,
            description="Biểu mẫu khách hàng đăng ký vay mua ô tô.",
            schema=schema, ui_spec=ui_spec, visibility_tier="public",
            whitelist_user_ids=[], database_id=db.id,
        )
    return db, app


def seed_binding(session, people, workflow, db) -> ActionBinding:
    tid = people["tenant_id"]
    owner = people["owner"]
    existing = session.execute(
        select(ActionBinding).where(
            ActionBinding.tenant_id == tid, ActionBinding.name == BINDING_NAME
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    principal = MiniAppPrincipal(
        user_id=owner.id, tenant_id=tid,
        department_id=owner.department_id, role="builder",
    )
    set_tenant_context(tid)
    return create_binding(
        session, principal=principal, name=BINDING_NAME,
        database_id=db.id, event_type="row.created",
        workflow_id=workflow.id,
        notify_user_ids=[people["credit_mgr"].id, people["ops"].id],
        is_active=True,
    )


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


def seed_workflow(session, people, agents) -> Workflow:
    tid = people["tenant_id"]
    owner = people["owner"]
    credit_mgr = people["credit_mgr"]
    ops = people["ops"]

    wf = session.execute(
        select(Workflow).where(
            Workflow.tenant_id == tid, Workflow.name == WORKFLOW_NAME
        )
    ).scalar_one_or_none()
    if wf is None:
        set_tenant_context(tid)
        wf = create_workflow(
            session, owner_id=owner.id, role="builder",
            name=WORKFLOW_NAME, description=WORKFLOW_DESC,
        )

    def node(key, label, x, y, approvers=None):
        return {
            "node_key": key, "label": label,
            "agent_id": str(agents[key].id), "config": {},
            "position": {"x": float(x), "y": float(y)},
            "approver_user_ids": [str(u.id) for u in (approvers or [])],
        }

    nodes = [
        node("rm_intake", "1. Tiếp nhận & kiểm tra hồ sơ", 0, 0),
        node("credit_appraisal", "2. Thẩm định tín dụng (CIC/DTI)", -160, 160),
        node("collateral_valuation", "3. Định giá TSĐB", 160, 160),
        node("credit_memo", "4. Phê duyệt khoản vay", 0, 320, approvers=[credit_mgr]),
        node("back_office", "5. Ký HĐ & hoàn thiện TSĐB", 0, 480),
        node("disbursement", "6. Đăng ký GDBĐ & Giải ngân", 0, 640, approvers=[ops]),
    ]
    edges = [
        {"from": "rm_intake", "to": "credit_appraisal"},
        {"from": "rm_intake", "to": "collateral_valuation"},
        {"from": "credit_appraisal", "to": "credit_memo"},
        {"from": "collateral_valuation", "to": "credit_memo"},
        {"from": "credit_memo", "to": "back_office"},
        {"from": "back_office", "to": "disbursement"},
    ]
    set_tenant_context(tid)
    replace_workflow_graph(session, wf.id, role="builder", nodes=nodes, edges=edges)
    return wf


def main() -> int:
    with AdminSessionLocal() as session:
        people = seed_people(session)
        agents = seed_agents(session, people)
        print("[auto-loan] agents seeded:")
        for key, a in agents.items():
            print(f"  - {key}: {a.name} (id={a.id})")
        workflow = seed_workflow(session, people, agents)
        print(f"[auto-loan] workflow: {workflow.name} (id={workflow.id})")
        db, app = seed_mini_app(session, people)
        print(f"[auto-loan] database: {db.name} (id={db.id})")
        print(f"[auto-loan] mini-app: {app.name} (id={app.id}, database_id={app.database_id}, "
              f"build_status={app.build_status})")
        binding = seed_binding(session, people, workflow, db)
        print(f"[auto-loan] binding: {binding.name} (id={binding.id}, active={binding.is_active})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
