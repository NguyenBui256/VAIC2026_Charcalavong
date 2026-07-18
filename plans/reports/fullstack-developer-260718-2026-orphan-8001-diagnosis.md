# Chẩn đoán: process cổng 8001 — có orphan không?

## Kết luận: KHÔNG có orphan. Chỉ có 1 process (pm2 vaic-api) và nó đã tự phục hồi bằng code mới.

## Chi tiết
- PID bind 8001: `20424` (python, cmdline `... -m uvicorn app.main:app --host 127.0.0.1 --port 8001 ...`), start 8:11:13 PM.
- PID pm2 vaic-api (jlist): `40568` — cmdline dùng `backend\.venv\Scripts\python.exe -m uvicorn ...`, cùng exec_cwd `backend/`.
- Quan hệ: `ParentProcessId` của 20424 = `40568`. Trên Windows, `.venv\Scripts\python.exe` là stub, tự spawn interpreter thật làm **process con** — nên 20424 chính là process con hợp lệ của pm2 vaic-api, KHÔNG PHẢI orphan riêng biệt. Không tìm thấy thư mục `backend` trùng lặp nào khác trên máy.
- `pm2 describe vaic-api`: status online, uptime 18m, restarts=3, exec cwd đúng repo, watch=off.

## Bằng chứng lỗi agent_id đã hết từ lần restart cuối
Grep timeline trong `vaic-api-error.log`:
- Các dòng lỗi `psycopg.errors.UndefinedColumn: column api_integrations.agent_id does not exist` nằm ở line 6015–6743 (nhiều lượt).
- Ngay sau đó là 2 lượt restart: `Started server process [44424]` (line 6751) rồi `Started server process [20424]` (line 6755) — đây là process đang chạy hiện tại.
- Từ sau restart tới giờ (~20 phút), **không có thêm dòng lỗi agent_id nào mới**, out log chỉ có request bình thường + 401 Unauthorized (kể cả route không tồn tại, do middleware auth chặn trước routing).

## Verify code hiện tại (working tree `backend/`)
- `app/modules/agent_builder/routes.py`: chỉ có `/integrations` (tenant-level, không prefix `/agents/{id}`), không còn route `/agents/{id}/integrations`.
- `list_integrations()` trong `integration_service.py` không query theo `agent_id`.
- Test trực tiếp: `curl http://localhost:8001/agents/019f7343-.../integrations` → `401 Unauthorized` (không phải 500) — đúng như kỳ vọng (thiếu auth header, route không match hoặc bị chặn bởi auth middleware trước, không phải lỗi DB).

## Không thực hiện
- Không kill process nào (không cần thiết — không có orphan).
- Không restart pm2 (process hiện tại đã chạy code đã fix).
- Không sửa/commit code.

## Việc còn lại (đề xuất, không tự làm)
- `restarts=3` trong 18 phút hơi bất thường — nên theo dõi `pm2 logs vaic-api` thêm để chắc chắn không crash loop do nguyên nhân khác (ví dụ DB pool, port bind race lúc khởi động).
- Nếu traffic thật vẫn báo 500 sau thời điểm 8:11:13 PM hôm nay, cần lấy thêm log/timestamp cụ thể từ phía traffic đó để đối chiếu — hiện tại log local không thấy lỗi mới.

## Câu hỏi chưa rõ
- User báo "traffic thật vẫn 500" — cần xác nhận request đó xảy ra TRƯỚC hay SAU 8:11:13 PM (giờ restart cuối) để chắc chắn đây là lỗi cũ đã fix, không phải lỗi đang tiếp diễn.
