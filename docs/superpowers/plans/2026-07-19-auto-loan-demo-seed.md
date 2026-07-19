# Auto-Loan Secured-Lending Demo (Seed-Only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seed one idempotent script that provisions the *Thẩm định & Giải ngân Vay Thế chấp Ô tô* demo — 6 Specialist Agents, a 6-node graph workflow with two human-approval gates, a customer mini-app (bound to a database template so events fire), and an event→workflow ActionBinding — so the whole business flow runs on existing UI with zero product-code changes.

**Architecture:** A single sync seed script (`backend/scripts/bootstrap_auto_loan_demo.py`) that calls existing services via `AdminSessionLocal` (BYPASSRLS) + `tenant_context.set(...)`, exactly like `bootstrap_demo_agents_workflow.py`. The only async leg is the final mini-app build enqueue (needs an arq Redis pool). Everything the script writes is consumed by machinery that already exists and is wired (graph engine, action outbox+cron, run-review UI).

**Tech Stack:** Python 3.13, SQLAlchemy, FastAPI services, arq/Redis, Postgres RLS. No new dependencies.

## Global Constraints

- **No product code changes.** The ONLY new file is `backend/scripts/bootstrap_auto_loan_demo.py`. Do not edit backend modules, frontend, or migrations.
- **No automated tests** (project override, `CLAUDE.md`): do not write or run pytest/typecheck/lint/build. Verification is **running the script + inspecting DB/UI**.
- **Idempotent**: every create is find-or-create by natural key; re-running the script must not error or duplicate.
- **Session pattern**: use `AdminSessionLocal` (BYPASSRLS) and call `tenant_context.set(tenant_id)` before each service call. Do NOT use the RLS `SessionLocal` (would require re-`set_tenant_session_var` after every commit).
- **`role="builder"`** is passed as the service-call arg to `create_agent`/`update_agent`/`create_workflow`/`replace_workflow_graph`/`create_app_from_schema`/`create_binding` regardless of a user's DB role (app-layer authorization check).
- **Every graph node MUST have a non-empty `agent_id`** (graph validation rejects empty). A "human-approval" node is a normal agent node that ALSO has ≥1 `approver_user_ids`.
- **Documents = metadata fields** (boolean/enum/longtext), never binary upload.
- **Run command**: `cd backend && uv run python -m scripts.bootstrap_auto_loan_demo`.

## Demo prerequisites (documented, not code)

- A working LLM key in `backend/.env`: `VAIC_LLM_API_KEY` (or `ANTHROPIC_API_KEY`), with `VAIC_LLM_PROVIDER`/`VAIC_LLM_MODEL` (defaults: `openai` / `DeepSeek-V4-Flash`). **There is no stub adapter** — without a key, agent nodes raise at run time and the run fails instead of pausing. The *schema* is hand-written (no LLM needed); only agent *execution* needs the key.
- Redis reachable (`VAIC_REDIS_URL` default `redis://localhost:6379/0`) and an **arq worker running** (`cd backend && uv run python -m scripts.run_worker`) — required both to build the mini-app and to run the workflow + 5s action cron.

## File structure

- Create: `backend/scripts/bootstrap_auto_loan_demo.py` — the entire deliverable. Sections build up across Tasks 1–6; module docstring holds the runbook.

## Reference signatures (verified — copy exactly)

```python
# Session / context
from app.core.db import AdminSessionLocal            # BYPASSRLS sessionmaker
from app.core.tenant_context import set_tenant_context
from app.core.auth import hash_password
# Base demo (ensures tenant "SHB Demo" + a builder user exist)
from scripts.bootstrap_demo_tenant import bootstrap_demo_tenant   # returns {"tenant","users",...}
from scripts.demo_agent_specs import get_agent_model_ref          # {"provider","model_name","parameters"}
# Tenant models
from app.modules.tenant.models import Tenant, Department, User
# Agents
from app.modules.agent_builder.service import Principal, create_agent, update_agent
# Workflow
from app.modules.orchestrator.service import create_workflow
from app.modules.orchestrator.graph_authoring import replace_workflow_graph
from app.modules.orchestrator.models import Workflow
# Mini-app
from app.modules.mini_app.visibility import MiniAppPrincipal
from app.modules.mini_app import database_service, service as mini_app_service
from app.modules.mini_app.database_models import MiniAppDatabase
from app.modules.mini_app.models import MiniApp
from app.modules.mini_app.schema_validation import validate_entity_schema, validate_ui_spec
# Action binding
from app.modules.action.service import create_binding
from app.modules.action.models import ActionBinding

# create_agent(session, *, owner_id, role, name, department_id, system_prompt, audit=None) -> Agent
# update_agent(session, agent_id, principal: Principal, *, audit=None, **changes) -> Agent   # changes: model=...
# Principal(user_id, tenant_id, department_id, role)
# create_workflow(session, *, owner_id, role, name, description, constraints=None, audit=None) -> Workflow
# replace_workflow_graph(session, workflow_id, *, role, nodes: list[dict], edges: list[dict]) -> dict
#   node dict: {node_key, label, agent_id(str), config(dict), position({x,y}), approver_user_ids(list)}
#   edge dict: {from: node_key, to: node_key}
# database_service.create_database(session, *, principal: MiniAppPrincipal, name, description, entity_schema: dict) -> MiniAppDatabase
# mini_app_service.create_app_from_schema(session, *, principal, name, description, schema: EntitySchema,
#     ui_spec: UiSpec, visibility_tier, whitelist_user_ids: list, created_by_agent_id=None, database_id=None) -> MiniApp
# create_binding(session, *, principal: MiniAppPrincipal, name, database_id, event_type, workflow_id,
#     notify_user_ids: list[uuid], is_active=True) -> ActionBinding
# enqueue_build(pool: ArqRedis, app_id: str) -> None    # async; app/modules/mini_app/lifecycle.py
```

---

### Task 1: Script scaffold + idempotent tenant/departments/users

**Files:**
- Create: `backend/scripts/bootstrap_auto_loan_demo.py`

**Interfaces:**
- Consumes: `bootstrap_demo_tenant()`, `AdminSessionLocal`, tenant models, `hash_password`.
- Produces (module-level, used by later tasks):
  - `DEMO_PASSWORD = "Password123!"`
  - `def _get_or_create_department(session, tenant_id, name) -> Department`
  - `def _get_or_create_user(session, tenant_id, department_id, email, role, full_name) -> User`
  - `def seed_people(session) -> dict` returning `{"tenant_id", "owner", "customer", "credit_mgr", "ops", "depts": {name: Department}}`.

- [ ] **Step 1: Write the module skeleton + people seeding**

Create `backend/scripts/bootstrap_auto_loan_demo.py`:

```python
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
```

- [ ] **Step 2: Run it and verify**

Run: `cd backend && uv run python -m scripts.bootstrap_auto_loan_demo`
Expected: base bootstrap prints its summary, then 4 lines listing `owner/customer/credit_mgr/ops` with UUIDs and roles. No traceback. Re-run once — same output, no errors (idempotent).

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/bootstrap_auto_loan_demo.py
git commit -m "feat(demo): auto-loan seed scaffold + people (tenant/depts/users)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Seed the six Specialist Agents

**Files:**
- Modify: `backend/scripts/bootstrap_auto_loan_demo.py`

**Interfaces:**
- Consumes: `seed_people` result (`owner`, `depts`, `tenant_id`).
- Produces: `def seed_agents(session, people) -> dict[str, "Agent"]` keyed by `node_key` (`"rm_intake"`, `"credit_appraisal"`, `"collateral_valuation"`, `"credit_memo"`, `"back_office"`, `"disbursement"`).

- [ ] **Step 1: Add agent specs + seeding function**

Add imports near the top (after existing imports):

```python
from app.modules.agent_builder.models import Agent
from app.modules.agent_builder.service import Principal, create_agent, update_agent
from scripts.demo_agent_specs import get_agent_model_ref
```

Add the specs + function (each spec's `dept` is a key of `people["depts"]`):

```python
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
```

Wire it into `main()` (replace the `with` block body):

```python
    with AdminSessionLocal() as session:
        people = seed_people(session)
        agents = seed_agents(session, people)
        print("[auto-loan] agents seeded:")
        for key, a in agents.items():
            print(f"  - {key}: {a.name} (id={a.id})")
```

- [ ] **Step 2: Run and verify**

Run: `cd backend && uv run python -m scripts.bootstrap_auto_loan_demo`
Expected: prints 6 agent lines with UUIDs. In the app, the Agents page lists the 6 new agents. Re-run — no duplicates (idempotent by name).

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/bootstrap_auto_loan_demo.py
git commit -m "feat(demo): seed six auto-loan specialist agents

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Seed the workflow + 6-node graph with two approval gates

**Files:**
- Modify: `backend/scripts/bootstrap_auto_loan_demo.py`

**Interfaces:**
- Consumes: `seed_people` result + `seed_agents` result.
- Produces: `def seed_workflow(session, people, agents) -> "Workflow"`.

- [ ] **Step 1: Add workflow + graph seeding**

Add imports:

```python
from app.modules.orchestrator.models import Workflow
from app.modules.orchestrator.graph_authoring import replace_workflow_graph
from app.modules.orchestrator.service import create_workflow
```

Add the function:

```python
WORKFLOW_NAME = "Thẩm định & Giải ngân Vay Thế chấp Ô tô"
WORKFLOW_DESC = (
    "Quy trình 6 bước thẩm định và giải ngân vay thế chấp mua ô tô: tiếp nhận hồ sơ, "
    "thẩm định tín dụng (CIC/DTI), định giá TSĐB, phê duyệt (duyệt thật), ký hợp đồng & "
    "hoàn thiện TSĐB, đăng ký GDBĐ & giải ngân (duyệt thật)."
)


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
```

Wire into `main()`:

```python
        workflow = seed_workflow(session, people, agents)
        print(f"[auto-loan] workflow: {workflow.name} (id={workflow.id})")
```

- [ ] **Step 2: Run and verify**

Run the script. Expected: prints the workflow id. In the app: open the workflow → Graph tab shows 6 nodes wired `n1 → (n2 ‖ n3) → n4 → n5 → n6`; nodes "4. Phê duyệt khoản vay" and "6. Đăng ký GDBĐ & Giải ngân" show an approver avatar (credit_mgr / ops). Re-run — `replace_workflow_graph` wipes+rewrites, so still exactly one graph (no duplication).

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/bootstrap_auto_loan_demo.py
git commit -m "feat(demo): seed 6-node auto-loan workflow graph with 2 approval gates

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Seed the database template + customer mini-app (bound so events fire)

**Files:**
- Modify: `backend/scripts/bootstrap_auto_loan_demo.py`

**Interfaces:**
- Consumes: `seed_people` result.
- Produces: `def seed_mini_app(session, people) -> tuple["MiniAppDatabase", "MiniApp"]`. The MiniApp is created with `database_id` set (so `_emit_row_change` carries `database_id`) and `visibility_tier="public"` (any tenant user can open + submit).

- [ ] **Step 1: Add the hand-written schema + database + app seeding**

Add imports:

```python
from app.modules.mini_app import database_service
from app.modules.mini_app import service as mini_app_service
from app.modules.mini_app.database_models import MiniAppDatabase
from app.modules.mini_app.models import MiniApp
from app.modules.mini_app.schema_validation import validate_entity_schema, validate_ui_spec
from app.modules.mini_app.visibility import MiniAppPrincipal
```

Add the schema + function (hand-written schema — no LLM dependency):

```python
DATABASE_NAME = "Hồ sơ vay thế chấp ô tô"
APP_NAME = "Đăng ký vay mua ô tô (SHB)"

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
```

Wire into `main()`:

```python
        db, app = seed_mini_app(session, people)
        print(f"[auto-loan] database: {db.name} (id={db.id})")
        print(f"[auto-loan] mini-app: {app.name} (id={app.id}, database_id={app.database_id}, "
              f"build_status={app.build_status})")
```

- [ ] **Step 2: Run and verify**

Run the script. Expected: prints database id, and app line where `database_id` equals the database id (NOT None) and `build_status=pending`. Re-run — no duplicate database/app (unique by name). Do not expect the app to render yet — build is enqueued in Task 6.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/bootstrap_auto_loan_demo.py
git commit -m "feat(demo): seed loan database template + bound customer mini-app

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Seed the event→workflow ActionBinding

**Files:**
- Modify: `backend/scripts/bootstrap_auto_loan_demo.py`

**Interfaces:**
- Consumes: `seed_people` (`owner`, `credit_mgr`, `ops`), `seed_workflow` (workflow), `seed_mini_app` (database).
- Produces: `def seed_binding(session, people, workflow, db) -> "ActionBinding"`.

- [ ] **Step 1: Add binding seeding**

Add imports:

```python
from app.modules.action.models import ActionBinding
from app.modules.action.service import create_binding
```

Add the function:

```python
BINDING_NAME = "Auto-Loan Intake → Thẩm định & Giải ngân"


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
```

Wire into `main()`:

```python
        binding = seed_binding(session, people, workflow, db)
        print(f"[auto-loan] binding: {binding.name} (id={binding.id}, active={binding.is_active})")
```

- [ ] **Step 2: Run and verify**

Run the script. Expected: prints a binding line with `active=True`. Its `database_id` must equal the database from Task 4 and `workflow_id` the workflow from Task 3 (both already wired in code). Re-run — no duplicate (unique by name).

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/bootstrap_auto_loan_demo.py
git commit -m "feat(demo): seed row.created -> auto-loan workflow action binding

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Enqueue the mini-app build (async leg) + full end-to-end demo verify

**Files:**
- Modify: `backend/scripts/bootstrap_auto_loan_demo.py`

**Interfaces:**
- Consumes: `seed_mini_app` result (`app.id`, `app.build_status`), `people["tenant_id"]`.
- Produces: `async def enqueue_app_build(tenant_id, app_id) -> None`; `main()` calls it via `asyncio.run(...)` only when the app is not already `ready`.

- [ ] **Step 1: Add the async build-enqueue leg**

Add imports at the top:

```python
import asyncio

from arq import create_pool
from arq.connections import RedisSettings

from app.core.settings import get_settings
from app.modules.mini_app.lifecycle import enqueue_build
```

Add the coroutine:

```python
async def enqueue_app_build(tenant_id: uuid.UUID, app_id: uuid.UUID) -> None:
    """Enqueue the esbuild job so the mini-app renders. Needs Redis + tenant context."""
    pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        set_tenant_context(tenant_id)  # required or enqueue raises MissingTenantContextError
        await enqueue_build(pool, str(app_id))
    finally:
        await pool.aclose()
```

At the END of `main()` (after the `with AdminSessionLocal()` block closes, so `app`/`people` are captured to locals first — assign `tid = people["tenant_id"]`, `app_id = app.id`, `build_status = app.build_status` inside the block), add:

```python
    if build_status != "ready":
        print("[auto-loan] enqueuing mini-app build…")
        asyncio.run(enqueue_app_build(tid, app_id))
        print("[auto-loan] build enqueued — ensure an arq worker is running to complete it.")
    print("\n[auto-loan] DONE. Login emails (pw Password123!):")
    print("  khách:      khachhang@shb.demo")
    print("  duyệt N4:   truongphong.td@shb.demo")
    print("  duyệt N6:   vanhanh@shb.demo")
```

Note: to capture the locals, change the tail of the `with` block to also set:

```python
        tid = people["tenant_id"]
        app_id = app.id
        build_status = app.build_status
```

- [ ] **Step 2: Run and verify build**

Ensure a worker is running: `cd backend && uv run python -m scripts.run_worker` (separate terminal).
Run the script. Expected: prints "enqueuing mini-app build…" then the DONE block. Within a few seconds the worker log shows `build_mini_app` transitioning `pending→building→ready`. In the app, the mini-app catalog shows the app `build_status=ready`; opening `/mini-apps/:appId` renders the form (not "Building…").

Verify build status directly:
```bash
cd backend && uv run python -c "from app.core.db import AdminSessionLocal; from sqlalchemy import select; from app.modules.mini_app.models import MiniApp; s=AdminSessionLocal();  print([(a.name,a.build_status) for a in s.execute(select(MiniApp).where(MiniApp.name=='Đăng ký vay mua ô tô (SHB)')).scalars()])"
```
Expected: `[('Đăng ký vay mua ô tô (SHB)', 'ready')]`.

- [ ] **Step 3: Full end-to-end demo verification (manual, per runbook)**

With backend (8000), worker, and frontend (5173) all running:
1. Login `khachhang@shb.demo` / `Password123!` → open the mini-app → fill sample data (e.g. loai_xe="Xe mới", tick the document booleans) → Submit.
2. Wait ≤5s. As `truongphong.td@shb.demo`, the notifications bell shows "New submission received".
3. Open the workflow's run (Workflow Runs / RunTracking). Confirm: `rm_intake` completes → `credit_appraisal` + `collateral_valuation` both run (parallel) → `credit_memo` reaches `awaiting_approval`, run status `awaiting_human`.
4. As `truongphong.td@shb.demo`, open the run, select node "4. Phê duyệt khoản vay", click **Approve**. Run resumes; `back_office` runs; `disbursement` reaches `awaiting_approval`.
5. Login `vanhanh@shb.demo` → open the run → node "6. Đăng ký GDBĐ & Giải ngân" → **Approve**. Run reaches `completed`.
6. Open route `database` → the "Hồ sơ vay thế chấp ô tô" database → confirm the submitted row appears in the rows table.
7. Open Audit/Trace for the run → confirm the per-node agent trace.

If step 3 shows the run `failed` at an agent node instead of pausing, the LLM key is missing/invalid — fix `VAIC_LLM_API_KEY` in `backend/.env` and re-submit (see Prerequisites).

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/bootstrap_auto_loan_demo.py
git commit -m "feat(demo): enqueue mini-app build + finalize auto-loan seed runbook

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Non-negotiables (no product code; seed-only; docs=metadata; customer=demo user) → Global Constraints + all tasks touch only the one script. ✓
- 6 agents → Task 2. ✓
- 6-node graph, fan-out n2‖n3, 2 approval gates (n4/n6) → Task 3. ✓
- Database template (hand-written schema, LLM optional) → Task 4. ✓ (spec Open Q1 resolved: hand-write for determinism; LLM only needed for agent execution, documented in Prerequisites.)
- Mini-app bound to database_id (events fire) + public tier → Task 4. ✓ (spec Open Q3: customer = seeded `member` user; approvers = `manager` users; resolved.)
- ActionBinding row.created → workflow, notify approvers → Task 5. ✓
- Build enqueue (async/Redis) → Task 6. ✓
- Three UIs (customer form / database rows / run review) → verified in Task 6 Step 3, all existing screens. ✓
- Demo runbook → module docstring + Task 6 Step 3. ✓

**Placeholder scan:** No TBD/TODO; every step shows complete code, exact commands, expected output. ✓

**Type/name consistency:**
- `people` dict keys (`tenant_id/owner/customer/credit_mgr/ops/depts`) defined in Task 1, consumed identically in Tasks 2–6. ✓
- `agents` keyed by `node_key`; `seed_workflow` reads `agents[key].id` for the same 6 keys. ✓
- `seed_people/seed_agents/seed_workflow/seed_mini_app/seed_binding/enqueue_app_build` signatures match their call sites in `main()`. ✓
- `MiniAppPrincipal(user_id, tenant_id, department_id, role)` and `Principal(user_id, tenant_id, department_id, role)` used with correct field names. ✓
- `create_app_from_schema` gets pydantic `schema`/`ui_spec` (via `validate_*`), `create_database` gets dict `entity_schema` — matches verified signatures. ✓
- `replace_workflow_graph` node/edge dict keys match the verified contract (`node_key/label/agent_id/config/position/approver_user_ids`; `from/to`). ✓

## Open questions (resolved defaults; flag if you disagree)

1. **LLM at run time**: demo requires a live `VAIC_LLM_API_KEY` for agents to execute (no stub). Documented as a prerequisite; not something the seed can fix.
2. **Live builder showcase** (create a mini-app via the builder chat during the demo): omitted from the wired path because the LLM-description create path yields `database_id=NULL` and would not trigger the workflow. Can be shown separately as a UI capability, but is not part of this seed.
