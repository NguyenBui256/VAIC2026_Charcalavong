# Report: Task 3 — shared_pool_reshape migration

STATUS: DONE

## Migration
- rev: `2848501cd966`, down_revision: `b2c3d4e5f6a7` (heads hiện tại trước khi tạo — đúng dự đoán trong prompt)
- File: `backend/alembic/versions/2848501cd966_shared_pool_reshape.py`

## Constraint names thực tế (introspect qua docker exec psql trên dev DB, `\d api_integrations` / `\d tools`)
- `api_integrations_agent_id_fkey` — đúng như plan đoán, dùng trong `op.drop_constraint`.
- `tools_integration_id_fkey` — đặt tên mới khi `op.create_foreign_key` (cột `integration_id` chưa tồn tại trên bảng `tools` ở head hiện tại — một migration cũ `f3a1c9e7b2d4` từng thêm cột này nhưng bảng `tools` đã bị recreate hoàn toàn bởi `a1b2c3d4e5f6`, nên không có xung đột tên cột/constraint).
- Cũng drop `ix_api_integrations_agent_id` (index cũ trên agent_id) và tạo `ix_tools_integration_id`.
- `kb_document_grants`: drop RLS policy + disable RLS trước khi `op.drop_table` (mirror pattern gốc ở migration `b2c3d4e5f6a7`).

## Downgrade
Đảo ngược đầy đủ: tái tạo `kb_document_grants` (đủ cột, check constraint `ck_kb_grant_role`, 2 index, RLS enable+force+policy+grant) — mirror chính xác `upgrade()` của `b2c3d4e5f6a7`; drop `tools.integration_id`/`kind`+FK+index; add lại `api_integrations.agent_id` (nullable, không backfill được data — note trong docstring) + FK + index.

## Round-trip verify (dev DB CHẠY — Postgres docker port 5434, container `vaic-postgres-1`)
- Trước khi bắt đầu, dev DB đang ở revision `39dfa51cec0c` (lag phía sau `heads` 3 migration) → đã chạy `alembic upgrade head` để đưa DB lên `b2c3d4e5f6a7` trước khi introspect (không phải prod, an toàn).
- `alembic upgrade head` → OK, schema khớp kỳ vọng (verify bằng `\d` — agent_id biến mất khỏi api_integrations, tools có kind+integration_id RESTRICT, kb_document_grants không còn tồn tại).
- `alembic downgrade -1` → OK, schema khôi phục đầy đủ (kb_document_grants đủ cột/constraint/RLS, tools/api_integrations về trạng thái cũ).
- `alembic upgrade head` (lần 2) → OK.
- Round-trip PASS, không lỗi.

## `alembic heads`
Chỉ 1 head: `2848501cd966 (head)`.

## Commit
`ca1a205 feat(db): shared pool reshape migration` — LOCAL ONLY, chưa push. Chỉ stage đúng 1 file migration (không đụng các file khác đang M/?? trong working tree — README.md, backend/.env.example, settings.py, vaic_tools/, etc. thuộc việc khác, không commit).

## Concerns
- Dev DB đã bị mutate qua các bước upgrade/downgrade/upgrade (giờ ở head `2848501cd966`) — nếu cần rollback dev DB về trạng thái ban đầu (`39dfa51cec0c`) báo tôi biết, hiện để nguyên ở head vì đó cũng là trạng thái đúng cho code hiện tại (Task 2 models đã match).
- KHÔNG động tới prod (Task 9, ngoài phạm vi task này).
- Migration `f3a1c9e7b2d4` (add tools integration_id column) trong lịch sử là dead code thực tế — cột nó thêm bị xoá khi `a1b2c3d4e5f6` recreate bảng `tools`. Không sửa gì (ngoài scope Task 3), chỉ note lại để tránh nhầm lẫn sau này.
