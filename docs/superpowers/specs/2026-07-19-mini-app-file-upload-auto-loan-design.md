# Design: File-upload documents for the auto-loan mini-app

**Date:** 2026-07-19
**Status:** Approved (design), pending implementation plan
**Topic:** Add a real `file` field type to the mini-app engine and reshape the
auto-loan credit-appraisal demo to collect uploaded customer documents.

## Problem

The car-loan credit-assessment demo (`backend/scripts/bootstrap_auto_loan_demo.py`)
must let a customer **upload the actual application documents** instead of ticking
"đã nộp" checkboxes. The 7 documents (from `test_case/Hồ sơ cá nhân KH/`):

1. CCCD Mô phỏng
2. Chứng nhận quyền sử dụng đất
3. Giấy đăng ký xe
4. Hóa đơn mua xe
5. Hồ sơ mục đích vay vốn
6. Hợp đồng lao động
7. Sao kê lương

The mini-app engine currently has **no file/upload field type** at all. Mini-app
forms are code-generated on the backend from a typed `EntitySchema` and run in a
sandboxed iframe (`sandbox="allow-scripts allow-forms"`, no `allow-same-origin`)
whose runtime SDK is JSON-only. So the demo fakes documents with boolean
checkboxes + a longtext "link to scans" field.

## Decisions (from brainstorming)

- **Real upload with backend storage** (not UI-only / not checkbox-only).
- **All 7 documents required.**
- **Keep** the 6-step appraisal workflow + `row.created` binding.
- **Slim** the form to 5 required text fields + 7 required file fields.
- Add `file` as a **permanent, first-class engine field type** (not a one-off).

## Architecture

### Field-type value shape

A `file` field value in a row is either `null` or a **file reference object**:

```json
{ "id": "<uuid>", "name": "sao-ke-luong.pdf", "mime": "application/pdf", "size": 51234 }
```

The bytes are NOT stored in the row — only the reference. Bytes live on local
disk, mirroring the existing `WorkflowFile` pattern.

### Auth / sandbox boundary

The iframe authenticates with a **scoped token** (`scope="miniapp:rows"`,
`miniapp_id=<app_id>`) that is authorized ONLY for `/apps/{app_id}/rows*` via
`_load_and_gate` in `mini_app/routes.py`. Therefore the upload/download endpoints
must live **under the same `/apps/{app_id}` prefix** and reuse `_load_and_gate`,
so the scoped token authorizes them without any privilege escalation.

### Storage (reuse, no new infra)

Reuse the `WorkflowFile` model + `settings.workflow_files_root` local-disk
storage used by `orchestrator/file_routes.py`:
- 20 MB cap, `_safe_name()` sanitization, `{file_id}_{safe_name}` on disk under
  `{workflow_files_root}/{tenant_id}/`.
- Tenant RLS row is the access gate; download is token/tenant-scoped (not a
  StaticFiles mount).

No S3/MinIO. Postgres + Redis infra unchanged.

## Components / Changes

### Backend — engine

1. `backend/app/modules/mini_app/schemas.py`
   - Add `"file"` to `FIELD_TYPES` tuple and to `FieldSpec.type` Literal.

2. `backend/app/modules/mini_app/schema_validation.py`
   - `_check_field`: enforce `required` for `file` (value present & non-null).
   - `_coerce_value`: a `file` value must be `null` or an object with keys
     `id` (str), `name` (str), `mime` (str), `size` (int). Reject other shapes.

3. `backend/app/modules/mini_app/codegen.py`
   - `renderWidget`: `file` type → `<input type="file">`; on change, call
     `sdk.uploadFile(file)` and store the returned reference object in `form`.
   - Table cell for a `file` value shows `value?.name` (filename), not `[object]`.

4. `backend/app/modules/mini_app/runtime_template/sdk.ts`
   - Add `uploadFile(file: File)`: `multipart/form-data` POST to
     `${apiBase}/apps/${appId}/files` with `Authorization: Bearer <token>`
     (own fetch, NOT the JSON `call()` helper). Returns `{id, name, mime, size}`.

5. `backend/app/modules/mini_app/routes.py`
   - `POST /apps/{app_id}/files` (multipart, `_load_and_gate`) → store bytes →
     create `WorkflowFile` row → return `{id, name, mime, size}`.
   - `GET /apps/{app_id}/files/{file_id}` (`_load_and_gate`) → `FileResponse`,
     RLS-scoped.
   - Shared helpers (`_safe_name`, size cap) factored from / aligned with
     `orchestrator/file_routes.py`.

### Frontend — schema builder parity

6. `frontend/src/lib/miniAppDatabasesApi.ts`
   - Add `"file"` to the `FieldType` union.

7. `frontend/src/components/database/SchemaFieldEditor.tsx`
   - Add `"file"` to the `FIELD_TYPES` array (type dropdown).

### Demo seed

8. `backend/scripts/bootstrap_auto_loan_demo.py`
   - Replace `LOAN_ENTITY_SCHEMA` with 5 text + 7 file fields (below).
   - `primary_display` stays `ho_ten`.

New schema fields:

| name | type | label | required |
|---|---|---|---|
| `ho_ten` | string | Họ và tên | ✔ (maxLength 255) |
| `ngay_sinh` | date | Ngày sinh | ✔ |
| `cccd` | string | Số CCCD | ✔ (maxLength 20) |
| `email` | string | Email | ✔ (pattern email) |
| `sdt` | string | Số điện thoại | ✔ (maxLength 15) |
| `file_cccd` | file | CCCD (2 mặt) | ✔ |
| `file_gcn_dat` | file | Chứng nhận quyền sử dụng đất | ✔ |
| `file_dang_ky_xe` | file | Giấy đăng ký xe | ✔ |
| `file_hoa_don_xe` | file | Hóa đơn mua xe | ✔ |
| `file_muc_dich_vay` | file | Hồ sơ mục đích vay vốn | ✔ |
| `file_hdld` | file | Hợp đồng lao động | ✔ |
| `file_sao_ke_luong` | file | Sao kê lương | ✔ |

Removed: `tinh_trang_hon_nhan`, `thu_nhap_thang`, `loai_xe`, `hang_dong_xe`,
`gia_xe`, `so_tien_vay_de_nghi`, all `gt_*` booleans, `link_ho_so`.

## Workflow tradeoff (accepted)

The 6-step appraisal workflow + `row.created` binding + `AGENT_SPECS` are kept
unchanged. Because the slim form drops `thu_nhap_thang` / `so_tien_vay_de_nghi` /
`gia_xe`, the appraisal agents reason from the uploaded documents + 5 identity
fields only (no numeric DTI inputs in the row). Accepted per "gọn text" — data
now lives in the documents.

## Error handling

- Upload > 20 MB → `ValidationError("file too large", code="file_too_large")`.
- Missing required file on row create → existing required-field validation path
  (now covers `file`) rejects with a validation error before insert.
- Download of a missing/cross-tenant file → `NotFoundError` (RLS hides the row;
  disk-missing also 404s).
- Malformed `file` value shape on row write → `_coerce_value` rejects.

## Testing

Per project working-preferences override, tests are NOT written unless the user
asks. Manual verification path: run the demo seed, open the mini-app host, upload
a PDF per field, confirm the row persists file references and the file downloads.

## Out of scope (YAGNI)

OCR / document parsing, antivirus scan, thumbnail/preview, multi-file per field,
S3/object storage, drag-and-drop styling polish.

## Open questions

None.
