# Design — Nối agent platform với vaic_tools (real MCP adapter)

**Ngày:** 2026-07-18
**Branch:** rebuild
**Trạng thái:** Đã duyệt thiết kế, chờ lập plan

## Mục tiêu

Agent trong platform (VAIC2026 backend/frontend) gọi & thực thi được **thật** 3 tool của `vaic_tools`
(Banking MCP Tool Server): `retrieve_knowledge`, `create_calendar_event`, `send_gmail_email`,
kèm nối KB upload/delete qua REST của vaic_tools. Thay thế `McpClientStub` đang giả lập kết quả.

## Bối cảnh kiến trúc (đã có sẵn)

Backend VAIC được thiết kế là **MCP client** theo hexagonal port:

- `McpClientPort` (`backend/app/core/ports/mcp_client.py`) — hợp đồng `call_tool` / `list_tools`,
  bắt buộc `tenant_id` + `department_id` (AD-11).
- `McpClientStub` (`backend/app/core/adapters/mcp_client_stub.py`) — hiện giả lập `rag.*`, `gmail`, `calendar`.
- Mọi caller đi qua đúng một factory: `get_mcp_client` (`backend/app/core/deps.py`).
- Callers: `tool_service.invoke_tool` (gmail/calendar/rag qua tool_type), `kb_service` (rag.ingest/rag.delete),
  `kb_retrieval.kb_search` (rag.search).

`vaic_tools` expose đúng 3 tool đó qua **MCP Streamable HTTP** `/mcp/` (Bearer key), và ingest/delete qua **REST**
`/api/v1/documents`. `mcp~=1.0` đã là dependency của backend.

Kết luận: công việc cốt lõi ở **backend** — viết adapter thật thay stub. Frontend Tools tab / Test Tool tự chạy đúng.

## Phương án chọn: A — một `VaicToolsAdapter` implement `McpClientPort`

Một class route theo tên tool → MCP (retrieve/gmail/calendar) hoặc REST (ingest/delete).
Toàn bộ mapping tên/tham số/output gói trong adapter. Chỉ đổi `get_mcp_client` (config-gated, stub là fallback).

Đã loại:
- **B** (tách 2 adapter + composite) — dư thừa cho 5 tool (YAGNI).
- **C** (gọi vaic trực tiếp trong service) — phá ranh giới hexagonal, rải credential.

## Mapping (hợp đồng adapter)

| Platform gọi (`call_tool` name) | vaic_tools | Transport | Biến đổi |
|---|---|---|---|
| `rag.search` | `retrieve_knowledge(query, top_k, document_ids, ...)` | MCP | out: `results[]` → `passages[]`: `text`→`passage`, `source.filename`→`document_name`, `f"{source.section or ''}#{source.chunk_index}"`→`chunk_reference`, `score`→`score` |
| `rag.ingest` | `POST /api/v1/documents` (multipart file) | REST | in: b64 `data` → file phần multipart (`filename`, `content_type`); out: `id`→`document_id`, `chunk_count` |
| `rag.delete` | `DELETE /api/v1/documents/{external_id}` | REST | dùng `external_document_id`; out: `{deleted: true}` |
| `gmail` | `send_gmail_email(idempotency_key, to[list], subject, text_body, ...)` | MCP | `to`(str)→`[to]`, `body`→`text_body`, **inject `idempotency_key`**; out normalize → `{message_id, status}` |
| `calendar` | `create_calendar_event(idempotency_key, summary, start, end, attendees, ...)` | MCP | `title`→`summary`, giữ `start`/`end`/`attendees`, **inject `idempotency_key`**; out normalize → `{event_id, status}` |

Ghi chú shape vaic (tham chiếu `vaic_tools/app/schemas.py`):
`RetrieveResponse.results[] = {rank, score, text, source:{document_id, filename, page, section, chunk_index, domain}}`.

## Config mới (`backend/app/core/settings.py`, prefix `VAIC_`)

- `vaic_tools_enabled: bool = False` — false → dùng `McpClientStub` (giữ dev/test chạy không cần vaic_tools).
- `vaic_tools_base_url: str` — REST root, vd `http://localhost:8000`.
- `vaic_tools_mcp_url: str` — vd `http://localhost:8000/mcp/`.
- `vaic_tools_api_key: str` — Bearer (khớp `MCP_API_KEYS` của vaic_tools).

## Thay đổi code

**Tạo mới:**
- `backend/app/core/adapters/vaic_tools_adapter.py` — `VaicToolsAdapter(McpClientPort)`:
  - `__init__(*, agent_department_id, settings)` — giữ `_assert_scope` như stub (AD-11).
  - MCP path: `mcp` SDK streamable HTTP client + `Authorization: Bearer`, `ClientSession.call_tool`.
  - REST path: `httpx` client tới `vaic_tools_base_url`.
  - Nếu >200 dòng → tách helper mapping (`vaic_tools_mapping.py`) theo rule modularization.

**Sửa:**
- `backend/app/core/deps.py` — `get_mcp_client`: switch theo `vaic_tools_enabled`.
- `backend/app/modules/agent_builder/kb_retrieval.py` — `kb_search`: dịch platform doc UUID → `external_document_id`
  trước khi truyền `document_ids` (query nhỏ trên `KbDocument`, có sẵn session).

**Không đổi:** scope tenant/department, audit (AD-4), schema validation (AC2/AC3), toàn bộ frontend.

## Edge cases / xử lý lỗi

- `idempotency_key` = `uuid7()` mỗi call (best-effort chống trùng cho gmail/calendar).
- Lỗi mạng / timeout / lỗi vaic → `ToolResult(success=False, error=...)`; `tool_service` audit `tool.rejected`,
  `kb_service` set `status="failed"`.
- gmail/calendar là side-effect **thật** — cần `.env` Google hợp lệ ở vaic_tools; test cẩn trọng (README vaic_tools: dùng `[TEST]`, `send_updates=none`, xoá event sau).
- `retrieve_knowledge` chỉ có kết quả sau khi tài liệu đã ingest thật vào vaic (Atlas có độ trễ đồng bộ index vài giây).
- output_schema catalog hiện lỏng (`{type: object}`, không `required`) → validation không fail dù thiếu key; adapter vẫn normalize về key tài liệu hoá.

## Success criteria

- Bật `vaic_tools_enabled=true` + config → agent attach `gmail`/`calendar`/`rag` gọi tool test (Test Tool) trả kết quả thật.
- KB upload → tài liệu ingest vào vaic (status `indexed`, có `external_document_id`); delete gỡ khỏi vaic.
- `kb_search` trả passage thật từ tài liệu đã ingest, đúng scope agent (chỉ doc được grant).
- `vaic_tools_enabled=false` → hành vi cũ (stub) không đổi; test hiện tại vẫn xanh.

## Unresolved questions

1. vaic REST `POST /api/v1/documents` có nhận id client-cấp không, hay luôn tự sinh id? (Giả định: tự sinh → phải track
   `external_document_id` và dịch id lúc search. Xác minh khi viết plan bằng cách đọc `vaic_tools/app/api/documents.py`.)
2. Đa tenant: vaic_tools là instance chia sẻ, không hiểu tenant/department. Bản này chấp nhận single shared instance
   (isolation dựa trên `document_ids` filter). Nhiều tenant thật cần tách instance/DB — ngoài scope đợt này.
3. gmail `send_gmail_email` trả shape chính xác gì (`message_id`/`thread_id`/`status`)? Xác minh ở
   `vaic_tools/app/google/operations.py` để map output cho khớp.
