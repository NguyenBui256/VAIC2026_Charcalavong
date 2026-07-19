# Alembic Multiple Heads Check — backend (post-merge, staged, chưa commit)

## Tổng số migration files
25 files trong `backend/alembic/versions/`.

## 2 migration audit mới
- `b7a2d4e91f30_audit_v2_trace_sessions.py`: revision=`b7a2d4e91f30`, down_revision=`34cd8281e2b3`
- `d91f4a8c2e70_audit_evaluation_judge.py`: revision=`d91f4a8c2e70`, down_revision=`b7a2d4e91f30`

## `alembic heads` (chạy được qua `.venv/Scripts/python.exe -m alembic heads`)
```
ac20actions01 (head)
d91f4a8c2e70 (head)
```
Khớp 100% với phân tích thủ công cây revision (revision nào không làm down_revision của ai khác).

## KẾT LUẬN: 2 HEADS → BỊ CHIA NHÁNH

**Nguyên nhân:** `34cd8281e2b3` (create_audit_trail_table) đang có **2 nhánh con**:
1. `7e8b08b45590` (create_agents_rls) → ... → chain rebuild hiện tại → `ac20actions01` (head 1, mainline)
2. `b7a2d4e91f30` (audit_v2_trace_sessions) → `d91f4a8c2e70` (audit_evaluation_judge) (head 2, nhánh audit)

Nhánh audit lấy `34cd8281e2b3` làm down_revision — đây là ancestor cũ (không phải head cũ của rebuild tại thời điểm audit branch được tạo), nên khi merge 2 nhánh vào cùng 1 branch, tạo ra fork thật sự tại `34cd8281e2b3`.

**Cần fix:** chạy `alembic merge heads` (hoặc merge thủ công) để tạo 1 migration merge point nối `ac20actions01` + `d91f4a8c2e70` → single head. Không tự thực hiện vì yêu cầu chỉ đọc.

## Không có câu hỏi tồn đọng.
