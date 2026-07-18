# Alembic upgrade head — prod DB fix

## Summary
Upgrade thành công, không lỗi. Revision before: `2848501cd966`. Revision after: `ac20actions01` (head). Single head confirmed trước khi chạy (no multiple heads).

## Migrations applied (order)
1. `b2c3d4e5f6a7 -> c3d4e5f6a7b8` create graph workflow tables (3A)
2. `c3d4e5f6a7b8 -> d4e5f6a7b8c9` create run_rollback_requests table (3B)
3. `d4e5f6a7b8c9 -> d5e6f7a8b9c0` add run status completed_with_failures (3B)
4. `d5e6f7a8b9c0 -> e6f7a8b9c0d1` workflow_files table + refuse_reason (3E)
5. `e6f7a8b9c0d1 -> f7a8b9c0d1e2` GRANT DELETE on graph authoring tables to vaic_app (3D)
6. `2848501cd966, f7a8b9c0d1e2 -> aa10database01` (mergepoint) create mini_app_databases + mini_apps.database_id
7. `aa10database01 -> ac10notify01` create notifications table with RLS
8. `ac10notify01 -> ac20actions01` create action_bindings + action_events tables with RLS

Note: DB trước đó đã ở branch `2848501cd966` (parent `b2c3d4e5f6a7`); branch song song `c3d4e5f6a7b8...f7a8b9c0d1e2` chưa apply. Alembic tự apply nhánh còn thiếu rồi merge tại `aa10database01` — không phải multiple-heads, chỉ là branch chưa đồng bộ, xử lý tự động, không cần can thiệp.

## Verify schema (via psycopg, DSN từ backend/.env VAIC_DATABASE_ADMIN_URL, port 5434 — đây là DB instance đang trỏ bởi backend config, giả định = prod theo yêu cầu user)
- `to_regclass`: action_events, notifications, action_bindings, mini_app_databases → đều tồn tại
- `mini_apps.database_id` column → tồn tại
- RLS policies count trên (action_events, notifications, mini_app_databases) = 3
- `alembic_version` table = `ac20actions01` (khớp head)
- GRANT DELETE cho role `vaic_app` trên workflow_edges, workflow_nodes/approvers → confirmed (DELETE, INSERT, SELECT, UPDATE đều có)

## Lỗi gặp phải
Không có lỗi trong quá trình upgrade. Chỉ có lỗi phụ khi thử dùng `psql` binary (không có trong PATH của môi trường bash) và khi import `app.core.config` (module không tồn tại/path issue) — cả hai đều là vấn đề tooling, không phải lỗi DB; đã workaround bằng parse `.env` trực tiếp + psycopg thuần.

## Unresolved questions
- Chưa xác nhận 100% DSN `localhost:5434` trong `backend/.env` chính là PROD (user nói "Đây là DB PROD" nên tin theo, nhưng port 5434 + localhost hơi bất thường cho prod — có thể là SSH tunnel/port-forward tới prod). Nên double-check với user nếu cần chắc chắn tuyệt đối.
