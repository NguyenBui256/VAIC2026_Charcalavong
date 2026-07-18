# Shared Pool (Tools/Integrations/KB) — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển Tools, API Integrations, Knowledge Base sang mô hình shared-tenant do `builder` quản lý; agent chỉ grant từ pool. Fix luôn 500 prod (`relation "agent_tools" does not exist`).

**Architecture:** Backend hexagonal (FastAPI + SQLAlchemy sync + Alembic + RLS). Integrations mất `agent_id` → tenant-scope; `tools` thêm `integration_id`+`kind`; bỏ `kb_document_grants`; CRUD pool gated role=`builder`; grant vào agent giữ `_authorize_mutation`. Một migration nối tiếp `heads` hiện tại.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 (sync), Alembic, psycopg3, Postgres RLS, pytest.

## Global Constraints

- Mọi bảng shared có RLS `tenant_id = current_setting('app.tenant_id')::uuid` (ENABLE + FORCE), mirror pattern `agents`.
- CRUD pool (tools kind=integration / integrations / kb upload+delete): yêu cầu `principal.role == "builder"`; sai → `AuthorizationError(code="FORBIDDEN")`. Guard ở service layer, không rải trong route.
- Grant vào agent (`agent_tools`/`agent_kb_documents`): `_authorize_mutation(agent, principal)` (builder + owns/same-dept) — giữ nguyên.
- Built-in tools (tool_type `rag`/`gmail`/`calendar`, `kind="builtin"`, `integration_id=null`) KHÔNG sửa/xoá qua API; seed giữ.
- Soft-delete + RLS conventions giữ như module hiện có. Không commit secret. Commit LOCAL, không push.
- **User override:** test/verify OPTIONAL (bỏ qua nếu user chưa yêu cầu); các bước test đánh dấu OPTIONAL. Không tự chạy lint/format/build.
- Alembic chạy trong `backend/` với venv: `.venv\Scripts\python.exe -m alembic ...`.

---

## File Structure

- `backend/alembic/versions/<rev>_shared_pool_reshape.py` — CREATE: migration (integrations drop agent_id; tools +integration_id +kind; drop kb_document_grants; RLS).
- `backend/app/modules/agent_builder/models.py` — MODIFY: `ApiIntegration` bỏ `agent_id`; `Tool` thêm `integration_id`,`kind`.
- `backend/app/modules/agent_builder/kb_models.py` — MODIFY: bỏ class `KbDocumentGrant`.
- `backend/app/modules/agent_builder/integration_service.py` — MODIFY: tenant-scope CRUD + role guard (bỏ agent_id/_authorize_mutation).
- `backend/app/modules/agent_builder/tool_catalog_service.py` — MODIFY: thêm create/update/delete tool kind=integration (role guard), serialize +integration_id/kind.
- `backend/app/modules/agent_builder/kb_service.py` — MODIFY: upload/delete gate role=builder; bỏ dùng kb_grants_service; get/list bỏ effective_role.
- `backend/app/modules/agent_builder/kb_grants_service.py` — DELETE.
- `backend/app/modules/agent_builder/agent_kb_service.py` — MODIFY: bỏ `require_access` (grants), giữ attach/detach theo `_authorize_mutation`.
- `backend/app/modules/agent_builder/routes.py` + `kb_routes.py` + (integration routes) — MODIFY: `/integrations` tenant-level; `/tools` CRUD; bỏ `/agents/{id}/integrations`; kb routes bỏ grant endpoints.
- `backend/app/modules/agent_builder/tool_service.py` — MODIFY: `_execute` route `kind=integration` qua HTTP integration (decrypt auth), `kind=builtin` giữ MCP.
- `backend/app/core/perms.py` — CREATE: helper `require_builder(principal)`.

Thứ tự task tôn trọng phụ thuộc: perms → migration/models → integration_service → catalog_tool_service → kb (service+grants+model) → routes → tool_service execution.

---

### Task 1: Permission helper `require_builder`

**Files:**
- Create: `backend/app/core/perms.py`
- Test (OPTIONAL): `backend/tests/unit/test_perms.py`

**Interfaces:**
- Consumes: `AuthorizationError` (`app.core.errors`), `Principal` (`app.modules.agent_builder.service`).
- Produces: `require_builder(principal: Principal) -> None` — raise `AuthorizationError(code="FORBIDDEN")` nếu `principal.role != "builder"`.

- [ ] **Step 1 (OPTIONAL): test**

```python
# backend/tests/unit/test_perms.py
import uuid
import pytest
from app.core.perms import require_builder
from app.core.errors import AuthorizationError
from app.modules.agent_builder.service import Principal


def _p(role): return Principal(user_id=uuid.uuid4(), department_id=uuid.uuid4(), role=role)


def test_require_builder_allows_builder():
    require_builder(_p("builder"))  # no raise


def test_require_builder_blocks_member():
    with pytest.raises(AuthorizationError):
        require_builder(_p("member"))
```

- [ ] **Step 2: implement**

```python
# backend/app/core/perms.py
"""Shared authorization guards for tenant-scoped pool management.

`builder` is the elevated tenant role permitted to CRUD the shared pool
(tools/integrations/KB). `member` may only be granted resources onto agents
they own — never manage the pool itself.
"""
from __future__ import annotations

from app.core.errors import AuthorizationError


def require_builder(principal) -> None:  # principal: Principal (avoid import cycle)
    """Raise FORBIDDEN unless the caller holds the `builder` role."""
    if getattr(principal, "role", None) != "builder":
        raise AuthorizationError("builder role required to manage the shared pool", code="FORBIDDEN")
```

- [ ] **Step 3 (OPTIONAL): run test** — `.venv\Scripts\python.exe -m pytest tests/unit/test_perms.py -v` → PASS
- [ ] **Step 4: commit (local)** — `git add backend/app/core/perms.py backend/tests/unit/test_perms.py && git commit -m "feat(perms): add require_builder guard for shared pool"`

---

### Task 2: Models — integrations tenant-scope, tools integration_id/kind, drop KbDocumentGrant

**Files:**
- Modify: `backend/app/modules/agent_builder/models.py` (`ApiIntegration`, `Tool`)
- Modify: `backend/app/modules/agent_builder/kb_models.py` (xoá `KbDocumentGrant`)

**Interfaces:**
- Produces: `Tool.integration_id: uuid|None`, `Tool.kind: str`; `ApiIntegration` không còn `agent_id`.

- [ ] **Step 1: `ApiIntegration` bỏ `agent_id`** — trong `models.py`, xoá block:
```python
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
```
Cập nhật docstring class `ApiIntegration` dòng "registered against an Agent" → "registered at tenant level (shared pool)".

- [ ] **Step 2: `Tool` thêm 2 cột** — sau `credential_ref` (dòng ~169) thêm:
```python
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="builtin", server_default="builtin"
    )
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_integrations.id", ondelete="RESTRICT"),
        nullable=True,
    )
```

- [ ] **Step 3: xoá `KbDocumentGrant`** — trong `kb_models.py` xoá toàn bộ class `KbDocumentGrant` (dòng 71-88) và cập nhật docstring đầu file: bỏ đề cập `kb_document_grants`; access = agent-grant + role-based management.

- [ ] **Step 4: commit (local)** — `git add backend/app/modules/agent_builder/models.py backend/app/modules/agent_builder/kb_models.py && git commit -m "feat(models): tenant-scope integrations, tool integration_id/kind, drop kb grants"`

---

### Task 3: Migration — shared_pool_reshape

**Files:**
- Create: `backend/alembic/versions/<rev>_shared_pool_reshape.py` (dùng `alembic revision -m "shared pool reshape"` để sinh rev id + down_revision = heads hiện tại)

**Interfaces:**
- Consumes: schema sau reshape `agent_tools` (đã có trong versions, là `down_revision`).
- Produces: DB schema khớp models Task 2.

- [ ] **Step 1: sinh file migration rỗng** — `.venv\Scripts\python.exe -m alembic revision -m "shared pool reshape"` → mở file mới, điền `upgrade`/`downgrade`.

- [ ] **Step 2: viết `upgrade()`**
```python
def upgrade() -> None:
    # 1. api_integrations -> tenant-scope: drop agent_id (+ FK). RLS đã theo tenant_id.
    op.drop_constraint("api_integrations_agent_id_fkey", "api_integrations", type_="foreignkey")
    op.drop_column("api_integrations", "agent_id")

    # 2. tools: kind + integration_id
    op.add_column("tools", sa.Column("kind", sa.String(16), nullable=False, server_default="builtin"))
    op.add_column("tools", sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "tools_integration_id_fkey", "tools", "api_integrations",
        ["integration_id"], ["id"], ondelete="RESTRICT",
    )

    # 3. drop user-level KB grants
    op.drop_table("kb_document_grants")
```
(Thêm `from alembic import op`, `import sqlalchemy as sa`, `from sqlalchemy.dialects import postgresql` ở đầu file. Kiểm tên constraint FK thật bằng `\d api_integrations`; nếu khác, dùng tên đúng.)

- [ ] **Step 3: viết `downgrade()`** (đảo ngược, tái tạo `kb_document_grants` + agent_id). Tối thiểu:
```python
def downgrade() -> None:
    op.create_table(
        "kb_document_grants",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.drop_constraint("tools_integration_id_fkey", "tools", type_="foreignkey")
    op.drop_column("tools", "integration_id")
    op.drop_column("tools", "kind")
    op.add_column("api_integrations", sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True))
```

- [ ] **Step 4 (OPTIONAL verify local dev DB):** `.venv\Scripts\python.exe -m alembic upgrade head` rồi `... downgrade -1` rồi `... upgrade head` — round-trip không lỗi. (KHÔNG chạy trên prod ở task này.)
- [ ] **Step 5: commit (local)** — `git add backend/alembic/versions/*shared_pool_reshape* && git commit -m "feat(db): shared pool reshape migration"`

---

### Task 4: integration_service — tenant-scope CRUD + role guard

**Files:**
- Modify: `backend/app/modules/agent_builder/integration_service.py`
- Test (OPTIONAL): `backend/tests/unit/test_integration_service.py` (cập nhật signature)

**Interfaces:**
- Consumes: `require_builder` (Task 1).
- Produces: `create_integration(session, *, principal, name, base_url, auth_header, schema=None)`, `list_integrations(session)`, `update_integration(session, integration_id, *, principal, ...)`, `delete_integration(session, integration_id, *, principal)` — KHÔNG còn `agent_id`.

- [ ] **Step 1: đổi chữ ký + guard** — trong mỗi hàm CRUD: bỏ tham số `agent_id` và `get_agent`/`_authorize_mutation(agent, principal)`; thay bằng `require_builder(principal)` ở đầu. `create` set `tenant_id=tenant_context.get()`, `owner_id=principal.user_id` (không set agent_id). `list_integrations` bỏ filter agent_id (RLS lo tenant). Ví dụ create:
```python
from app.core.perms import require_builder

def create_integration(session, *, principal, name, base_url, auth_header, schema=None):
    require_builder(principal)
    integ = ApiIntegration(
        id=uuid7(), tenant_id=tenant_context.get(), owner_id=principal.user_id,
        name=name, base_url=base_url,
        auth_header_encrypted=encrypt(auth_header), schema_=schema,
    )
    session.add(integ); session.commit(); session.refresh(integ)
    return integ
```
(Giữ `encrypt`/mask hiện có. `owner_id` cần thêm cột? ApiIntegration hiện KHÔNG có owner_id → thêm ở Task 2/3 HOẶC dùng `tenant_id` only. **Quyết:** không thêm owner_id — bỏ dòng owner_id; integration thuộc tenant, không cần owner.)

- [ ] **Step 2: sửa lại Step 1 cho khớp model** — vì `ApiIntegration` không có `owner_id`, create chỉ set `tenant_id`. `delete_integration`: `require_builder` + xoá; nếu FK RESTRICT từ tools chặn → bắt `IntegrityError` trả `ValidationError("integration đang được tool tham chiếu", code="integration_in_use")`.

- [ ] **Step 3 (OPTIONAL): cập nhật test** cho signature mới (bỏ agent_id, thêm case member bị 403).
- [ ] **Step 4: commit (local)** — `git commit -m "feat(integrations): tenant-scope CRUD gated on builder role"`

---

### Task 5: tool_catalog_service — CRUD tool kind=integration

**Files:**
- Modify: `backend/app/modules/agent_builder/tool_catalog_service.py`
- Test (OPTIONAL): `backend/tests/unit/test_tool_catalog_service.py`

**Interfaces:**
- Consumes: `require_builder` (Task 1), `ApiIntegration` (verify integration_id thuộc tenant).
- Produces: `create_catalog_tool(session, *, principal, display_name, description, params_schema, output_schema, integration_id)`, `update_catalog_tool(...)`, `delete_catalog_tool(session, tool_id, *, principal)`; `serialize_tool` thêm `kind`,`integration_id`.

- [ ] **Step 1: serialize thêm field** — trong `serialize_tool` thêm `"kind": tool.kind, "integration_id": str(tool.integration_id) if tool.integration_id else None`.

- [ ] **Step 2: create/update/delete (chỉ kind=integration)**
```python
from app.core.perms import require_builder

def create_catalog_tool(session, *, principal, display_name, description, params_schema, output_schema, integration_id):
    require_builder(principal)
    integ = session.get(ApiIntegration, integration_id)
    if integ is None or integ.is_deleted:
        raise NotFoundError("Integration not found")
    tool = Tool(
        id=uuid7(), tenant_id=tenant_context.get(), owner_id=principal.user_id,
        tool_type="integration", kind="integration", display_name=display_name,
        description=description, params_schema=params_schema, output_schema=output_schema,
        config={}, integration_id=integration_id,
    )
    session.add(tool); session.commit(); session.refresh(tool)
    return tool

def delete_catalog_tool(session, tool_id, *, principal):
    require_builder(principal)
    tool = get_catalog_tool(session, tool_id)
    if tool.kind == "builtin":
        raise ValidationError("Không thể xoá built-in tool", code="builtin_tool_immutable")
    tool.is_deleted = True; tool.deleted_at = datetime.now(UTC); session.commit()
```
(`update_catalog_tool` tương tự: require_builder, chặn sửa builtin, cho sửa display_name/description/schemas/integration_id.)

- [ ] **Step 3 (OPTIONAL): test** create/delete + chặn builtin + member 403.
- [ ] **Step 4: commit (local)** — `git commit -m "feat(tools): builder-managed CRUD for integration tools"`

---

### Task 6: kb_service + agent_kb_service — siết role, bỏ grants

**Files:**
- Modify: `backend/app/modules/agent_builder/kb_service.py`
- Modify: `backend/app/modules/agent_builder/agent_kb_service.py`
- Delete: `backend/app/modules/agent_builder/kb_grants_service.py`
- Test (OPTIONAL): cập nhật test kb liên quan grants.

**Interfaces:**
- Consumes: `require_builder`.
- Produces: `upload_document`/`delete_document` gate builder; `list_documents(session)` trả mọi doc trong tenant (RLS); `get_document(session, document_id)` bỏ `require_access`; `serialize_document` bỏ `effective_role`.

- [ ] **Step 1: `upload_document`** — thêm `require_builder(principal)` đầu hàm. `delete_document` — thay `require_access(...need_manage=True)` bằng `require_builder(principal)`.
- [ ] **Step 2: `list_documents`** — bỏ nhánh grants; trả toàn bộ KbDocument trong tenant (RLS đã scope): `select(KbDocument).order_by(KbDocument.created_at.desc())`. `get_document` bỏ `require_access`. `serialize_document` bỏ param/field `effective_role`.
- [ ] **Step 3: `agent_kb_service`** — bỏ import + call `require_access` (grants); giữ `_authorize_mutation(agent, principal)` cho attach/detach. Chỉ builder + owns/same-dept mới grant doc vào agent.
- [ ] **Step 4: xoá file** `kb_grants_service.py` + mọi import còn lại của nó (`grep kb_grants_service`).
- [ ] **Step 5 (OPTIONAL): test** upload member→403, builder→ok; list trả tenant docs.
- [ ] **Step 6: commit (local)** — `git commit -m "feat(kb): builder-managed KB, drop user-level grants"`

---

### Task 7: Routes — /integrations & /tools tenant-level, kb bỏ grant endpoints

**Files:**
- Modify: `backend/app/modules/agent_builder/routes.py`, `kb_routes.py`, và file route integration hiện tại (grep `integrations` trong routes).

**Interfaces:**
- Produces: REST: `GET/POST /integrations`, `PATCH/DELETE /integrations/{id}`; `POST /tools`,`PATCH/DELETE /tools/{id}` (CRUD pool); giữ `GET /tools` (list catalog), `GET/POST/DELETE /agents/{id}/tools`,`/agents/{id}/kb` (grant). Bỏ `/agents/{id}/integrations`. Bỏ kb grant endpoints (`/kb/{id}/grants`).

- [ ] **Step 1: integration routes** — chuyển prefix từ `/agents/{agent_id}/integrations` sang `/integrations` (tenant-level); handler gọi service mới (không agent_id); `_principal(request)` như hiện có.
- [ ] **Step 2: tool CRUD routes** — thêm `POST /tools`,`PATCH /tools/{id}`,`DELETE /tools/{id}` gọi catalog_tool_service create/update/delete. Giữ `GET /tools` (list) + `GET /agents/{id}/tools` (grant list) + attach/detach.
- [ ] **Step 3: kb routes** — xoá các endpoint grants (`kb_routes.py` phần `/grants`); `serialize_document(doc)` bỏ `effective_role`.
- [ ] **Step 4: đăng ký router** — đảm bảo router `/integrations`,`/tools` mount trong `app/main.py` hoặc bootstrap (grep `include_router`).
- [ ] **Step 5 (OPTIONAL): test integration** `/integrations` + `/tools` CRUD (builder 200, member 403).
- [ ] **Step 6: commit (local)** — `git commit -m "feat(api): tenant-level integrations+tools routes, drop per-agent + kb grants"`

---

### Task 8: tool_service — thực thi tool kind=integration qua HTTP

**Files:**
- Modify: `backend/app/modules/agent_builder/tool_service.py` (`_execute`)
- Test (OPTIONAL): `backend/tests/unit/test_tool_service.py`

**Interfaces:**
- Consumes: `Tool.kind`,`Tool.integration_id`; `ApiIntegration.base_url`,`auth_header_encrypted`; `decrypt` (`app.core.crypto`).
- Produces: `_execute` route: `kind=="builtin"` → MCP (như hiện tại); `kind=="integration"` → HTTP POST tới `integration.base_url` với header auth giải mã, body=`arguments`.

- [ ] **Step 1: nhánh integration trong `_execute`**
```python
def _execute(tool, arguments, *, tenant_id, department_id, sandbox, mcp_factory, session=None):
    start = time.monotonic()
    if tool.kind == "integration":
        output = _call_integration(session, tool, arguments)
    else:
        mcp = mcp_factory(agent_department_id=department_id)
        output = _call_mcp(mcp, tool.tool_type, arguments, tenant_id, department_id).output
    return output, None, int((time.monotonic() - start) * 1000)
```
(Cần truyền `session` vào `_execute` từ `invoke_tool` để load integration.)

- [ ] **Step 2: helper `_call_integration`**
```python
def _call_integration(session, tool, arguments):
    import httpx
    from app.core.crypto import decrypt
    from app.modules.agent_builder.models import ApiIntegration
    integ = session.get(ApiIntegration, tool.integration_id)
    if integ is None:
        return {"error": "integration_missing"}
    headers = {"Content-Type": "application/json"}
    auth = decrypt(integ.auth_header_encrypted)
    if auth:
        name, _, value = auth.partition(":")
        headers[name.strip()] = value.strip()
    resp = httpx.post(integ.base_url, json=arguments, headers=headers, timeout=30)
    resp.raise_for_status()
    integ.last_used_at = datetime.now(UTC); session.commit()
    return resp.json()
```
(Giữ output_schema validation ở `invoke_tool` như hiện tại. Bắt exception → `invoke_tool` đã có path audit `tool.rejected`; nếu cần, wrap trả `{"error": ...}` để output validation fail → rejected.)

- [ ] **Step 3 (OPTIONAL): test** integration tool invoke (mock httpx) + builtin vẫn qua MCP.
- [ ] **Step 4: commit (local)** — `git commit -m "feat(tools): execute integration-kind tools via HTTP integration"`

---

### Task 9: Deploy — apply migration prod (fix 500)

**Files:** none (vận hành).

- [ ] **Step 1: backup prod DB** — `pg_dump` (VAIC_ENV=production DSN) ra file có timestamp trước khi migrate.
- [ ] **Step 2: apply** — trong `backend/`, `$env:VAIC_ENV="production"; .venv\Scripts\python.exe -m alembic upgrade head`.
- [ ] **Step 3: verify** — `.venv\Scripts\python.exe -m alembic current` == `heads`; `GET https://api.charcalavon.site/agents/<id>/tools` trả 200 (hết 500); `pm2 restart vaic-api vaic-worker`.
- [ ] **Step 4: seed built-in tools kind/integration_id** — nếu tools seed cũ thiếu `kind`, chạy 1 script/SQL set `kind='builtin'` cho rag/gmail/calendar (server_default đã lo bản ghi mới; bản cũ có thể cần backfill — kiểm `SELECT kind FROM tools`).

---

## Self-Review

**Spec coverage:**
- Integrations→chung: Task 2 (model) + 3 (migration) + 4 (service) + 7 (routes). ✔
- Tools→chung (+integration_id/kind, CRUD builder): Task 2/3/5/7. ✔
- KB siết role + drop grants: Task 2 (model) + 3 (migration) + 6 (service+delete grants) + 7 (routes). ✔
- Permissions builder: Task 1 + dùng ở 4/5/6. ✔
- Agent grant giữ nguyên: Task 6 (kb) note; agent_tools attach/detach ở routes hiện có (không đổi). ✔
- Execution integration tool: Task 8. ✔
- Migration + fix 500: Task 3 + 9. ✔
- FE: KHÔNG trong plan này (Plan 2). ✔ (đã tách)

**Placeholder scan:** không TBD/TODO; code cụ thể mỗi step. Task 3 note "kiểm tên constraint thật" là chỉ dẫn xác minh cụ thể, không phải placeholder.

**Type consistency:** `require_builder(principal)` dùng nhất quán (Task 1,4,5,6). `Tool.kind`/`integration_id` khai Task 2 → dùng Task 5,8. `create_integration` bỏ agent_id nhất quán Task 4↔7. `_execute(... session=...)` thêm ở Task 8 khớp caller `invoke_tool`.

## Unresolved questions

1. `ApiIntegration` không có `owner_id` (đã quyết bỏ) — nếu sau này cần audit "ai tạo integration", thêm cột sau. Ngoài scope.
2. Backfill `tools.kind` cho bản ghi seed cũ ở prod (Task 9 Step 4) — cần xác nhận SELECT thực tế.
3. `_call_integration` giả định auth_header dạng `"Name: value"`. Nếu integration cần scheme khác (query param, OAuth), mở rộng sau.
4. Plan 2 (Frontend): trang Tools/KB chung + grant-picker, retire authoring per-agent — viết sau khi Plan 1 xong.
