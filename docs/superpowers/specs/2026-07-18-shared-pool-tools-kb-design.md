# Design — Mô hình "pool chung + grant cho agent" cho Tools, Integrations, Knowledge Base

**Ngày:** 2026-07-18
**Branch:** rebuild
**Trạng thái:** Đã duyệt thiết kế, chờ user review → writing-plans

## Mục tiêu

Thống nhất cơ chế quản lý Tools, API Integrations và Knowledge Base thành một mô hình duy nhất:
mọi tài nguyên là **shared cấp tenant**, do **Manager/Admin quản lý**; **Agent được grant** truy cập từng
tài nguyên. Không có tài nguyên sở hữu-bởi-một-agent. Dứt điểm lệch FE/BE hiện tại và fix 500 prod
(`relation "agent_tools" does not exist` do migration reshape chưa apply).

## Bối cảnh hiện tại (đã khảo sát)

- `tools`: catalog chung tenant (rag/gmail/calendar seed sẵn, không cho user tạo — spec D4 cũ); agent tham chiếu qua `agent_tools` (M2M).
- `api_integrations`: **per-agent** (`agent_id`), auth mã hoá Fernet — điểm "lệch" duy nhất khỏi mô hình chung.
- `kb_documents`: chung tenant, `owner_id` uploader, `department_id` optional; ACL user qua `kb_document_grants` (viewer|manager); agent RAG qua `agent_kb_documents` (M2M).
- FE `toolsApi.ts` mô hình per-agent authoring (kind mcp|embedded_python, integration_id) — lệch BE catalog-chung.
- Role tenant: `tenant.users.role` (1 chuỗi/user; giá trị đang dùng `member`/`builder`). "manager/viewer" chỉ là role của KB-grant.
- Prod 500: `alembic current=39dfa51cec0c` < `heads` (thiếu reshape `agent_tools`).

## Mô hình đích

Nguyên tắc: **Tools / Integrations / KB = tài nguyên shared tenant** do Manager/Admin CRUD; **Agent grant** từ pool.

### 1. Integrations → chung (`api_integrations`)
- Bỏ cột `agent_id` (+ FK). Scope theo `tenant_id`. Giữ `owner_id` (người tạo), `name`, `base_url`, `auth_header_encrypted`, `schema_`.
- CRUD: chỉ role quản lý (xem §5). Data migration: gom integration per-agent hiện có lên tenant, giữ nguyên, dedupe theo `(tenant_id, name)` nếu trùng (giữ bản mới nhất).

### 2. Tools → chung (`tools`)
- Thêm `integration_id` (FK `api_integrations`, nullable) + `kind` (`builtin` | `integration`).
- `builtin`: rag/gmail/calendar, `tool_type` set, `integration_id=null`, route vaic_tools qua adapter hiện có. Seed sẵn, **không sửa/xoá** qua API.
- `integration`: user tạo, tham chiếu 1 `integration_id`, `params_schema`/`output_schema` do user khai.
- CRUD (chỉ với `kind=integration`): role quản lý.

### 3. KB → chung (`kb_documents`)
- Giữ tenant-wide. Upload/xoá: **chỉ role quản lý** (đổi từ "any authenticated user").
- **Bỏ** bảng `kb_document_grants` + `kb_grants_service` (ACL theo user) — thừa: quản lý theo role, truy cập theo agent-grant. `serialize_document` bỏ `effective_role`.

### 4. Agent grant (`agent_tools`, `agent_kb_documents`)
- Giữ nguyên M2M. Builder/owner của agent tick chọn từ pool chung (dùng `_authorize_mutation` sẵn có).
- Grant là hành vi trên agent (builder + owns/same-dept), **tách biệt** khỏi quản lý pool.

### 5. Permissions
- **CRUD pool** (tools/integrations/KB): yêu cầu role `builder` (CHỐT — tái dùng role elevated sẵn có, không thêm role mới). `member` chỉ xem, không CRUD pool, không grant.
- **Grant vào agent**: `builder` + (owns agent OR same-department) — giữ `_authorize_mutation`.
- Guard mới đặt ở service layer (raise `AuthorizationError code=FORBIDDEN`), không rải trong route.

### 6. Frontend
- **Trang Tools** (top-level, đã có placeholder): quản lý Tools chung + Integrations chung (chỉ role quản lý thấy nút tạo/sửa/xoá). List + create/edit form (kind=integration), test tool.
- **Trang Knowledge Base** (top-level, đã có placeholder): list/upload/xoá docs chung (chỉ role quản lý).
- **Agent Builder → tab Tools & KB**: đổi thành **bộ chọn grant** — checkbox list từ pool chung, attach/detach (POST/DELETE `agent_tools`/`agent_kb_documents`). Bỏ authoring per-agent: `ToolEditor`, tab `ApiIntegrationsTab` (tạo mới). `toolsApi.ts` per-agent-authoring nghỉ hưu → thay bằng `catalogToolsApi` (list/CRUD pool) + `agentGrantsApi` (attach/detach).

### 7. Migration & fix 500 prod
- Gộp migration đang treo (reshape `agent_tools`) + migration mới đợt này (integrations bỏ agent_id, tools thêm integration_id/kind, drop kb_document_grants) thành chuỗi liên tục tới `heads`.
- Deploy: `alembic upgrade head` (VAIC_ENV=production, backup trước) ⇒ hết 500 + lên mô hình mới.

## Data flow

- **Quản lý pool:** Manager/Admin → Trang Tools/KB → CRUD `tools`/`api_integrations`/`kb_documents` (RLS tenant).
- **Cấu hình agent:** Builder → Agent Builder tab Tools/KB → attach/detach `agent_tools`/`agent_kb_documents`.
- **Runtime:** Orchestrator/agent → `tool_service.invoke_tool` (builtin→vaic_tools; integration→HTTP qua integration) / `kb_search` (two-gate: agent có rag tool + có doc được grant) → vaic_tools retrieve.

## Isolation / boundaries

- `catalog_tool_service` (pool tools CRUD) | `integration_service` (pool integrations CRUD, đổi sang tenant-scope) | `kb_service` (pool KB CRUD, siết role) | `agent_grants_service` (attach/detach) — mỗi module một trách nhiệm, test độc lập.
- Pool tenant-wide; agent department-scoped nhưng grant được tài nguyên tenant-wide. Agent-grant là cổng truy cập runtime duy nhất. AD-11 department-match ở adapter giữ nguyên (agent truyền department của chính nó). vaic_tools là instance chung, không tách isolation theo department (đã chốt ở spec vaic-tools).

## Error handling

- CRUD pool bởi non-manager → `AuthorizationError` (403 FORBIDDEN).
- Grant tool/doc không thuộc tenant → `NotFoundError` (RLS + 404).
- Xoá integration đang được tool tham chiếu → chặn (FK RESTRICT hoặc kiểm tra trước, trả lỗi rõ) — tránh mồ côi.
- Migration: chạy trong transaction; backup trước ở prod.

## Testing

- Unit: permission guard (manager vs member) cho từng CRUD pool; attach/detach authz; migration reshape (integrations bỏ agent_id giữ data).
- Integration: `/tools`, `/integrations`, `/kb` (pool CRUD) + `/agents/{id}/tools`,`/agents/{id}/kb` (grant) end-to-end.
- (Theo working-preference: test OPTIONAL khi user chưa yêu cầu; plan sẽ đánh dấu.)

## Success criteria

- Manager tạo Integration chung + Tool (kind=integration) ở trang Tools; grant cho agent; agent invoke chạy qua integration.
- Manager upload KB chung; grant cho agent; `kb_search` trả passage đúng doc được grant.
- Member (non-manager) KHÔNG tạo/sửa/xoá pool được (403) nhưng grant vào agent mình vẫn được.
- Prod `GET /agents/{id}/tools` hết 500 sau `alembic upgrade head`.
- FE không còn màn authoring tool/integration per-agent; chỉ còn quản lý pool + grant.

## Unresolved questions

1. ~~Role quản lý pool~~ — **CHỐT: dùng `builder`** (không thêm role admin).
2. **api_integrations prod có dữ liệu per-agent không** cần gom khi migrate? (prod có thể chưa có row nào → migration đơn giản).
3. **Bỏ hẳn `kb_document_grants`** (đề xuất, YAGNI) hay giữ bảng cho tương lai? Bỏ ⇒ cần xoá `kb_grants_service` + chỗ gọi + test liên quan.
4. **Phân rã plan:** đợt này gồm 4 mảng (integrations→shared, tools authoring→shared, KB siết role + drop grants, FE grant-picker) + migration. Có thể tách plan theo mảng nếu quá lớn — quyết ở bước writing-plans.
