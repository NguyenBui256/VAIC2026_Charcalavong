# Mini-App File-Upload Field + Auto-Loan Doc Intake — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `file` field type to the mini-app engine and reshape the auto-loan credit-appraisal demo so customers upload 7 required documents plus 5 identity text fields.

**Architecture:** A `file` field value is a reference object `{id, name, mime, size}`; bytes are stored on local disk reusing the `WorkflowFile` model + `settings.workflow_files_root`. Upload/download endpoints live under the existing `/apps/{app_id}` prefix so the sandboxed iframe's scoped token authorizes them via `_load_and_gate`. The engine change (schema → validation → codegen → runtime SDK) plus a frontend schema-builder parity edit make `file` a permanent type; the demo seed script is then rewritten to use it.

**Tech Stack:** FastAPI (Python 3.13), Pydantic v2, SQLAlchemy, esbuild-compiled React/TSX mini-app runtime, Vite + React 19 + TypeScript frontend.

## Global Constraints

- **No test files** — per project working-preferences override (CLAUDE.md), do NOT write automated tests or run typecheck/lint/build/format unless explicitly asked. Each task ends with a lightweight manual/import verification instead.
- Field-name regex: `^[a-z][a-z0-9_]{0,63}$` (unchanged; new field names must comply).
- File `size` cap: **20 MB** (`20 * 1024 * 1024`), matching KB + workflow-file caps.
- `file` row value shape: `null` OR `{"id": str, "name": str, "mime": str, "size": int}`.
- Reuse existing storage: `WorkflowFile` ORM model (`app.modules.orchestrator.models`) + `get_settings().workflow_files_root`. Do NOT add S3/MinIO or new infra.
- All 7 document file fields are `required: True`.
- Keep the 6-step appraisal workflow, `AGENT_SPECS`, and the `row.created` binding untouched.
- Envelope helper: routes return `_ok(data)` → `{"data": ..., "error": None, "meta": {}}`.

---

### Task 1: Add `file` to the engine schema + validation

**Files:**
- Modify: `backend/app/modules/mini_app/schemas.py:14,19`
- Modify: `backend/app/modules/mini_app/schema_validation.py:44-59,87-124`

**Interfaces:**
- Produces: `FIELD_TYPES` now includes `"file"`; `FieldSpec.type` Literal includes `"file"`; `coerce_row_data` accepts/validates `file` values shaped `{id,name,mime,size}`; `_check_field` rejects type-specific attrs (min/max/length/pattern/options) on a `file` field.

- [ ] **Step 1: Add `"file"` to `FIELD_TYPES` and the `FieldSpec.type` Literal**

In `backend/app/modules/mini_app/schemas.py`, replace line 14:

```python
FIELD_TYPES = ("string", "longtext", "integer", "number", "boolean", "date", "enum", "file")
```

and replace line 19 (the `type:` annotation) with:

```python
    type: Literal["string", "longtext", "integer", "number", "boolean", "date", "enum", "file"]
```

- [ ] **Step 2: Guard type-specific attrs against `file` in `_check_field`**

In `backend/app/modules/mini_app/schema_validation.py`, append to the end of `_check_field` (after the `pattern` block, currently ending line 59):

```python
    if f.type == "file" and (
        f.min is not None or f.max is not None
        or f.minLength is not None or f.maxLength is not None
        or f.pattern is not None or f.options is not None
    ):
        raise SchemaValidationError(f"file field '{f.name}' cannot have value constraints")
```

- [ ] **Step 3: Validate the `file` value shape in `_coerce_value`**

In `backend/app/modules/mini_app/schema_validation.py`, insert this branch inside `_coerce_value` immediately BEFORE the `# string / longtext` comment (currently line 115):

```python
    if f.type == "file":
        if not isinstance(value, dict):
            raise SchemaValidationError(f"field '{f.name}' file must be an object")
        fid, name, mime, size = (
            value.get("id"), value.get("name"), value.get("mime"), value.get("size"),
        )
        if not isinstance(fid, str) or not isinstance(name, str) or not isinstance(mime, str):
            raise SchemaValidationError(f"field '{f.name}' file needs string id/name/mime")
        if isinstance(size, bool) or not isinstance(size, int):
            raise SchemaValidationError(f"field '{f.name}' file needs integer size")
        return {"id": fid, "name": name, "mime": mime, "size": size}
```

- [ ] **Step 4: Verify the module imports and validates as expected**

Run:

```bash
cd backend && uv run python -c "from app.modules.mini_app.schema_validation import validate_entity_schema, coerce_row_data; s = validate_entity_schema({'fields':[{'name':'doc','type':'file','label':'Doc','required':True}],'primary_display':'doc'}); print('schema ok'); print(coerce_row_data(s, {'doc': {'id':'abc','name':'x.pdf','mime':'application/pdf','size':10}}))"
```

Expected output:

```
schema ok
{'doc': {'id': 'abc', 'name': 'x.pdf', 'mime': 'application/pdf', 'size': 10}}
```

- [ ] **Step 5: Verify a malformed file value is rejected**

Run:

```bash
cd backend && uv run python -c "from app.modules.mini_app.schema_validation import validate_entity_schema, coerce_row_data, SchemaValidationError; s = validate_entity_schema({'fields':[{'name':'doc','type':'file','required':True}],'primary_display':'doc'});
try:
    coerce_row_data(s, {'doc': 'not-an-object'}); print('NO ERROR (bug)')
except SchemaValidationError as e:
    print('rejected:', e.reason)"
```

Expected output contains: `rejected: field 'doc' file must be an object`

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/mini_app/schemas.py backend/app/modules/mini_app/schema_validation.py
git commit -m "feat(mini-app): add 'file' field type to schema + validation"
```

---

### Task 2: File storage service + scoped-token upload/download routes

**Files:**
- Create: `backend/app/modules/mini_app/file_service.py`
- Modify: `backend/app/modules/mini_app/routes.py` (add imports near lines 12-37; add two routes on `mini_app_rows_router` after the delete route at line 254)

**Interfaces:**
- Consumes: `_load_and_gate(app_id, request, session)` (existing, `routes.py:203`), `WorkflowFile` (`orchestrator/models.py:425`), `get_settings().workflow_files_root`.
- Produces:
  - `file_service.save_upload(session, tenant_id, user_id, filename, content_type, reader) -> dict` returning `{"id","name","mime","size"}`.
  - `file_service.resolve_file(session, file_id) -> WorkflowFile` (raises `NotFoundError` if missing/absent on disk).
  - Routes `POST /apps/{app_id}/files` and `GET /apps/{app_id}/files/{file_id}`.

- [ ] **Step 1: Create the storage service**

Create `backend/app/modules/mini_app/file_service.py`:

```python
"""Local-disk storage for mini-app `file` field uploads.

Reuses the WorkflowFile model + `settings.workflow_files_root` (same pattern
as orchestrator/file_routes.py). Bytes land at
`{workflow_files_root}/{tenant_id}/{file_id}_{safe_name}`; the WorkflowFile
row is the tenant RLS gate. Callers gate access with the mini-app scoped
token (`_load_and_gate`) BEFORE calling here.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.ids import uuid7
from app.core.settings import get_settings
from app.modules.orchestrator.models import WorkflowFile

MAX_BYTES = 20 * 1024 * 1024  # 20 MB
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_name(name: str) -> str:
    cleaned = _SAFE.sub("_", name).strip("._") or "file"
    return cleaned[:255]


def save_upload(
    session: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID | None,
    filename: str, content_type: str, reader: Callable[[int], bytes],
) -> dict[str, Any]:
    """Stream-read via `reader(chunk_size)`, enforce the cap, persist, return a ref."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = reader(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_BYTES:
            raise ValidationError("file too large (max 20MB)", code="file_too_large")
        chunks.append(chunk)
    data = b"".join(chunks)

    file_id = uuid7()
    safe = _safe_name(filename or "file")
    root = Path(get_settings().workflow_files_root) / str(tenant_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{file_id}_{safe}"
    path.write_bytes(data)

    row = WorkflowFile(
        id=file_id, tenant_id=tenant_id, filename=safe,
        content_type=content_type or "application/octet-stream",
        size_bytes=len(data), storage_path=str(path),
        created_by=user_id,
    )
    session.add(row)
    session.commit()
    return {"id": str(row.id), "name": row.filename, "mime": row.content_type, "size": row.size_bytes}


def resolve_file(session: Session, file_id: uuid.UUID) -> WorkflowFile:
    row = session.get(WorkflowFile, file_id)  # RLS hides cross-tenant rows
    if row is None or not os.path.exists(row.storage_path):
        raise NotFoundError("file not found")
    return row
```

- [ ] **Step 2: Add imports to routes.py**

In `backend/app/modules/mini_app/routes.py`, add to the `fastapi` import (line 17) so it reads:

```python
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
```

and add these module imports alongside the other `app.modules.mini_app` imports (after line 28):

```python
from app.modules.mini_app import file_service
```

- [ ] **Step 3: Add the upload + download routes**

In `backend/app/modules/mini_app/routes.py`, append after the `delete_row_route` (end of file, after line 254):

```python
@mini_app_rows_router.post("/{app_id}/files")
def upload_app_file_route(
    app_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> JSONResponse:
    """Upload a file for a `file` field. Scoped-token authorized (same gate as
    row writes). Returns a reference `{id, name, mime, size}` to store in the row."""
    _load_and_gate(app_id, request, session)
    user_id = getattr(request.state, "user_id", None)
    ref = file_service.save_upload(
        session,
        tenant_id=uuid.UUID(str(request.state.tenant_id)),
        user_id=uuid.UUID(str(user_id)) if user_id else None,
        filename=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        reader=file.file.read,
    )
    return JSONResponse(status_code=201, content=_ok(ref))


@mini_app_rows_router.get("/{app_id}/files/{file_id}")
def download_app_file_route(
    app_id: uuid.UUID, file_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> FileResponse:
    """Download a previously uploaded file. Scoped-token authorized + RLS-scoped."""
    _load_and_gate(app_id, request, session)
    row = file_service.resolve_file(session, file_id)
    return FileResponse(row.storage_path, media_type=row.content_type, filename=row.filename)
```

- [ ] **Step 4: Verify the app boots with the new routes registered**

Run:

```bash
cd backend && uv run python -c "from app.main import app; paths = [r.path for r in app.routes]; print('/apps/{app_id}/files' in paths); print('/apps/{app_id}/files/{file_id}' in paths)"
```

Expected output:

```
True
True
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/mini_app/file_service.py backend/app/modules/mini_app/routes.py
git commit -m "feat(mini-app): scoped-token file upload/download routes + storage service"
```

---

### Task 3: Runtime codegen `file` widget + SDK upload method

**Files:**
- Modify: `backend/app/modules/mini_app/runtime_template/sdk.ts:27-33`
- Modify: `backend/app/modules/mini_app/codegen.py:15-18,67,80-88`

**Interfaces:**
- Consumes: `POST /apps/{appId}/files` (Task 2).
- Produces: `sdk.uploadFile(file: File) => Promise<{id,name,mime,size}>`; generated form renders `<input type="file">` for `file` fields and stores the returned ref in `form[f.name]`; table cell shows the filename.

- [ ] **Step 1: Add `uploadFile` to the runtime SDK**

In `backend/app/modules/mini_app/runtime_template/sdk.ts`, replace the `export const sdk = { ... }` block (lines 27-33) with:

```typescript
export const sdk = {
  list: () => call(""),
  create: (data: unknown) => call("", { method: "POST", body: JSON.stringify({ data }) }),
  update: (id: string, data: unknown, expected_updated_at: string) =>
    call(`/${id}`, { method: "PATCH", body: JSON.stringify({ data, expected_updated_at }) }),
  remove: (id: string) => call(`/${id}`, { method: "DELETE" }),
  uploadFile: async (file: File) => {
    const c = cfg();
    const fd = new FormData();
    fd.append("file", file);
    const resp = await fetch(`${c.apiBase}/apps/${c.appId}/files`, {
      method: "POST",
      headers: { Authorization: `Bearer ${c.token}` },  // no Content-Type: browser sets multipart boundary
      body: fd,
    });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body?.error?.message || "upload failed");
    return body.data as { id: string; name: string; mime: string; size: number };
  },
};
```

- [ ] **Step 2: Add the `file` widget to the codegen widget map**

In `backend/app/modules/mini_app/codegen.py`, replace the `_WIDGET` dict (lines 15-18) with:

```python
_WIDGET = {
    "string": "text", "longtext": "textarea", "integer": "number",
    "number": "number", "boolean": "checkbox", "date": "date", "enum": "select",
    "file": "file",
}
```

- [ ] **Step 3: Render file values as filenames in the table cell**

In `backend/app/modules/mini_app/codegen.py`, replace the table-cell map (line 67) with a version that shows the filename for `file` values:

```python
              {{FIELDS.map((f) => <td key={{f.name}}>{{f.type === "file" ? (r.data?.[f.name]?.name ?? "") : String(r.data?.[f.name] ?? "")}}</td>)}}
```

- [ ] **Step 4: Add the `file` branch to `renderWidget`**

In `backend/app/modules/mini_app/codegen.py`, inside the `renderWidget` function, add a `file` branch immediately after the `enum` branch (after line 85, before the `const inputType` line):

```python
  if (f.type === "file") return <span><input type="file" onChange={{async (e) => {{ const file = e.target.files?.[0]; if (file) set(await sdk.uploadFile(file)); }}}} />{{form[f.name]?.name ? <em style={{{{ marginLeft: 8 }}}}>{{form[f.name].name}}</em> : null}}</span>;
```

- [ ] **Step 5: Verify codegen produces the file widget + import stays valid**

Run:

```bash
cd backend && uv run python -c "import uuid; from app.modules.mini_app.codegen import generate_app_source; from app.modules.mini_app.schemas import EntitySchema, UiSpec; src = generate_app_source(uuid.uuid4(), 'T', EntitySchema(fields=[{'name':'doc','type':'file','label':'Doc','required':True}], primary_display='doc'), UiSpec()); print('file input' , 'type=\"file\"' in src); print('uploadFile', 'sdk.uploadFile' in src)"
```

Expected output:

```
file input True
uploadFile True
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/mini_app/runtime_template/sdk.ts backend/app/modules/mini_app/codegen.py
git commit -m "feat(mini-app): file upload widget in codegen + sdk.uploadFile"
```

---

### Task 4: Frontend schema-builder parity for `file`

**Files:**
- Modify: `frontend/src/lib/miniAppDatabasesApi.ts:3-4`
- Modify: `frontend/src/components/database/SchemaFieldEditor.tsx:9`

**Interfaces:**
- Produces: `FieldType` union includes `"file"`; the type dropdown offers `file`.

- [ ] **Step 1: Add `"file"` to the `FieldType` union**

In `frontend/src/lib/miniAppDatabasesApi.ts`, replace the `FieldType` type (lines 3-4) with:

```typescript
export type FieldType =
  | "string" | "longtext" | "integer" | "number" | "boolean" | "date" | "enum" | "file";
```

- [ ] **Step 2: Add `"file"` to the editor dropdown list**

In `frontend/src/components/database/SchemaFieldEditor.tsx`, replace line 9 with:

```typescript
const FIELD_TYPES: FieldType[] = ["string", "longtext", "integer", "number", "boolean", "date", "enum", "file"];
```

- [ ] **Step 3: Verify the edited files are syntactically consistent**

Read both edited files back and confirm `"file"` appears in the `FieldType` union and the `FIELD_TYPES` array. (No build per project override.)

Run:

```bash
cd frontend && grep -n '"file"' src/lib/miniAppDatabasesApi.ts src/components/database/SchemaFieldEditor.tsx
```

Expected: one match in each file.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/miniAppDatabasesApi.ts frontend/src/components/database/SchemaFieldEditor.tsx
git commit -m "feat(mini-app): expose 'file' field type in schema builder UI"
```

---

### Task 5: Rewrite the auto-loan demo schema (5 text + 7 file fields)

**Files:**
- Modify: `backend/scripts/bootstrap_auto_loan_demo.py:75-100`

**Interfaces:**
- Consumes: `file` field type (Task 1); `create_app_from_schema` / `create_database` (unchanged, `seed_mini_app` at line 232).
- Produces: `LOAN_ENTITY_SCHEMA` with fields `ho_ten, ngay_sinh, cccd, email, sdt` (text) + `file_cccd, file_gcn_dat, file_dang_ky_xe, file_hoa_don_xe, file_muc_dich_vay, file_hdld, file_sao_ke_luong` (file, all required); `primary_display="ho_ten"`.

- [ ] **Step 1: Replace `LOAN_ENTITY_SCHEMA`**

In `backend/scripts/bootstrap_auto_loan_demo.py`, replace the whole `LOAN_ENTITY_SCHEMA = {...}` block (lines 75-100) with:

```python
LOAN_ENTITY_SCHEMA = {
    "fields": [
        # Thông tin định danh khách hàng (tối thiểu, tượng trưng)
        {"name": "ho_ten", "type": "string", "label": "Họ và tên", "required": True, "maxLength": 255},
        {"name": "ngay_sinh", "type": "date", "label": "Ngày sinh", "required": True},
        {"name": "cccd", "type": "string", "label": "Số CCCD", "required": True, "maxLength": 20},
        {"name": "email", "type": "string", "label": "Email", "required": True,
         "maxLength": 255, "pattern": r"[^@\s]+@[^@\s]+\.[^@\s]+"},
        {"name": "sdt", "type": "string", "label": "Số điện thoại", "required": True, "maxLength": 15},
        # Văn bản khách cần nộp (upload, tất cả bắt buộc)
        {"name": "file_cccd", "type": "file", "label": "CCCD (mô phỏng)", "required": True},
        {"name": "file_gcn_dat", "type": "file", "label": "Chứng nhận quyền sử dụng đất", "required": True},
        {"name": "file_dang_ky_xe", "type": "file", "label": "Giấy đăng ký xe", "required": True},
        {"name": "file_hoa_don_xe", "type": "file", "label": "Hóa đơn mua xe", "required": True},
        {"name": "file_muc_dich_vay", "type": "file", "label": "Hồ sơ mục đích vay vốn", "required": True},
        {"name": "file_hdld", "type": "file", "label": "Hợp đồng lao động", "required": True},
        {"name": "file_sao_ke_luong", "type": "file", "label": "Sao kê lương", "required": True},
    ],
    "primary_display": "ho_ten",
}
```

- [ ] **Step 2: Verify the schema validates**

Run:

```bash
cd backend && uv run python -c "from scripts.bootstrap_auto_loan_demo import LOAN_ENTITY_SCHEMA; from app.modules.mini_app.schema_validation import validate_entity_schema; s = validate_entity_schema(LOAN_ENTITY_SCHEMA); print('fields:', len(s.fields)); print('files:', [f.name for f in s.fields if f.type=='file'])"
```

Expected output:

```
fields: 12
files: ['file_cccd', 'file_gcn_dat', 'file_dang_ky_xe', 'file_hoa_don_xe', 'file_muc_dich_vay', 'file_hdld', 'file_sao_ke_luong']
```

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/bootstrap_auto_loan_demo.py
git commit -m "feat(demo): auto-loan form = 5 identity fields + 7 required doc uploads"
```

---

### Task 6: End-to-end manual verification

**Files:** none (verification only).

**Interfaces:** Consumes everything from Tasks 1-5.

- [ ] **Step 1: Re-seed the demo (rebuilds the mini-app via esbuild)**

Ensure infra + backend deps are up (`docker compose ... up -d`, `uv sync`), then run:

```bash
cd backend && uv run python -m scripts.bootstrap_auto_loan_demo
```

Expected: completes without error; logs the mini-app build being enqueued/built.

- [ ] **Step 2: Open the mini-app host and confirm the form**

Start the frontend (`cd frontend && npm run dev`) and backend (`uv run uvicorn app.main:app --reload --port 8000`). Log in as the demo owner (`owner@shb.demo` / `Password123!`), open the "Đăng ký vay mua ô tô (SHB)" mini-app.

Confirm the form shows 5 text inputs (Họ và tên, Ngày sinh [date], Số CCCD, Email, Số điện thoại) and 7 file inputs (one per document). No income/car/checkbox fields remain.

- [ ] **Step 3: Upload the sample documents and submit**

Fill the 5 identity fields with sample data, and for each file field upload the matching PDF from `test_case/Hồ sơ cá nhân KH/`. Submit (Create).

Expected: row is created; the table lists it showing the uploaded filenames in the file columns; no validation error. Verify bytes landed under `{workflow_files_root}/{tenant_id}/`.

- [ ] **Step 4: Confirm required-file validation blocks a partial submit**

Create a second row filling only the text fields and leaving a file field empty; submit.

Expected: submit is rejected with a "missing required field" error for the empty file field.

- [ ] **Step 5: Confirm the appraisal workflow still fires**

Confirm the `row.created` binding triggered the "Thẩm định & Giải ngân Vay Thế chấp Ô tô" workflow run for the successfully created row (check the workflow runs list).

Expected: a run was created for the new row.

---

## Self-Review

**Spec coverage:**
- §1 new `file` field type → Task 1 (schema/validation), Task 3 (codegen/sdk), Task 4 (frontend builder). ✓
- §2 backend storage + endpoints under `/apps/{app_id}` → Task 2. ✓
- §3 slimmed demo schema → Task 5. ✓
- §4 workflow kept + tradeoff → Task 5 (removed numeric fields), Task 6 Step 5 (verify workflow still fires). ✓
- §5 out of scope (no OCR/S3/AV) → nothing added, honored. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. ✓

**Type consistency:** `file` value shape `{id,name,mime,size}` is identical across `_coerce_value` (Task 1), `save_upload` return (Task 2), `sdk.uploadFile` return type (Task 3), and table/widget rendering (Task 3). Endpoint paths `/apps/{app_id}/files` match between Task 2 (route) and Task 3 (sdk fetch). `_load_and_gate` signature matches its definition. ✓

## Open questions

None.
