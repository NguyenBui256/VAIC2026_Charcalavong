# Chẩn đoán CORS login — 2026-07-18

## Kết quả kiểm tra

1. **So sánh VAIC_CORS_ORIGINS 2 file env**
   - `backend/.env.production:23` → `VAIC_CORS_ORIGINS=https://charcalavon.site` (đúng như kỳ vọng)
   - `backend/.env` → KHÔNG có dòng `VAIC_CORS_ORIGINS` (dev dùng default trong `Settings` field, không override)

2. **Settings load theo VAIC_ENV**
   - `VAIC_ENV=production` → `cors_origins = https://charcalavon.site` (đúng)
   - Không set VAIC_ENV (dev) → `cors_origins = http://localhost:5173,http://127.0.0.1:5173` (default, KHÔNG có domain prod)

3. **Preflight thực tế trên localhost:8000 (process đang chạy)**
   ```
   HTTP/1.1 400 Bad Request
   ...
   Disallowed CORS origin
   ```
   → Process uvicorn ĐANG CHẠY trả về **"Disallowed CORS origin"** cho `Origin: https://charcalavon.site`. Điều này chỉ xảy ra khi app load bằng **dev config** (chỉ allow localhost:5173/127.0.0.1:5173), tức process hiện tại KHÔNG được khởi động với `VAIC_ENV=production`.

4. **Qua tunnel public (api.charcalavon.site)**
   - Cùng lỗi y hệt: `HTTP/1.1 400 Bad Request` + `Disallowed CORS origin`, response có header `server: cloudflare`, `cf-ray` → tunnel routing OK, request tới đúng backend qua Cloudflare. Không phải vấn đề tunnel/network.
   - **Xác nhận: tunnel hoạt động bình thường, root cause nằm ở chính backend process, không phải ở tầng network/tunnel.**

5. **Middleware order trong `backend/app/main.py`**
   ```
   line 54: app.add_middleware(AuthMiddleware)
   line 63: app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, ...)
   ```
   Comment code xác nhận CORS được add SAU AuthMiddleware để nằm ngoài cùng (Starlette middleware chạy theo thứ tự add ngược — cái add sau bọc ngoài). Thứ tự này ĐÚNG chuẩn, không phải nguyên nhân.

## Kết luận — nguyên nhân gốc

**Backend production đang chạy KHÔNG có biến môi trường `VAIC_ENV=production`.**

Bằng chứng: preflight cả qua localhost:8000 lẫn qua tunnel public đều trả "Disallowed CORS origin" — đúng hành vi của dev config (chỉ allow `localhost:5173`/`127.0.0.1:5173`), trong khi `.env.production` có origin đúng `https://charcalavon.site` và code load theo `VAIC_ENV` hoạt động chính xác khi test thủ công. Middleware order cũng đúng. Vậy vấn đề KHÔNG phải code/config sai, mà là **process khởi động thiếu env var** — không tìm thấy script (.ps1/.bat/.sh/docker-compose) nào set `VAIC_ENV=production` trước khi launch uvicorn, nên có khả năng người vận hành start bằng `uvicorn app.main:app` trực tiếp mà quên set biến, hoặc dùng lại session/service cũ không có nó.

## Cách khắc phục
- Set `VAIC_ENV=production` trong môi trường/service khởi động uvicorn (systemd unit `Environment=VAIC_ENV=production`, hoặc PowerShell `$env:VAIC_ENV="production"` trước khi chạy, hoặc trong file `.env` của process manager/pm2/nssm nếu có dùng).
- Sau khi set đúng, restart uvicorn process, kiểm tra lại bằng lệnh preflight ở mục 3 — kỳ vọng `access-control-allow-origin: https://charcalavon.site` xuất hiện thay vì "Disallowed CORS origin".
- Khuyến nghị thêm: log `VAIC_ENV` + `cors_origins` resolved ra stdout lúc startup app để tránh lặp lại lỗi này (không thuộc phạm vi điều tra này, chỉ đề xuất).

## Unresolved
- Không xác định được cách backend hiện tại được khởi động (không tìm thấy script/service definition set VAIC_ENV) — cần hỏi người vận hành cách deploy/start service thực tế (systemd? pm2? task scheduler? chạy tay trong terminal?) để sửa đúng chỗ.
- Không kiểm tra được nhiều process python.exe đang chạy (11 process) cái nào là uvicorn backend — không có quyền xem cmdline chi tiết trong phạm vi read-only này.
