# Debug: GET /agents/{id}/tools 500 — prod

## TRACEBACK
`sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedTable) relation "agent_tools" does not exist`
LINE: `FROM tools JOIN agent_tools ON agent_tools.tool_id = tools.id ...`
File cuối trong app code: `backend/app/modules/agent_builder/tool_catalog_service.py:136` (`list_agent_tool_refs`), gọi từ `backend/app/modules/agent_builder/routes.py:214` (`list_agent_tools_route`).

## ROOT CAUSE
Prod DB chưa apply migration tạo bảng `agent_tools`. `serialize_catalog_tool` không liên quan — lỗi xảy ra trước đó, ngay ở query DB.

## Alembic state
- current (prod): `39dfa51cec0c`
- heads (code): `b2c3d4e5f6a7`
- LỆCH — prod thiếu 2 migration:
  - `c4f1a9d3e7b2` "reshape tools catalog + agent_tools" ← tạo bảng `agent_tools`
  - `a1b2c3d4e5f6` "reshape kb store + grants + agent_kb_documents"

## pm2 vaic-api
- restarts: 1, uptime: 4m (mới restart gần đây)
- Không có ImportError lúc boot — process khởi động sạch, lỗi chỉ xảy ra khi request tới endpoint dùng bảng `agent_tools`.

## FIX ĐỀ XUẤT
Chạy `alembic upgrade head` trên prod DB (VAIC_ENV=production) để tạo bảng `agent_tools` (và các thay đổi liên quan trong `a1b2c3d4e5f6`). Trước khi upgrade, review 2 file migration để chắc không có breaking change/data loss trên prod hiện có, và backup DB trước khi chạy.

## Câu hỏi tồn đọng
- Deploy pipeline có tự động chạy `alembic upgrade head` sau deploy code không? Nếu không, đây là nguyên nhân gốc quy trình (code deploy trước, migration không đi kèm).
