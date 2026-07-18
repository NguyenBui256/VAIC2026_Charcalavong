# Typed Node I/O + Refuse Insight (3E) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let workflow node/run input & output be JSON, plain **text**, or an uploaded **file** (user-selectable, with a shared typed-value input + viewer and tenant-scoped file storage), and give a **refused rollback** feedback — capture the refuser's reason and surface the original request + both reasons on the rejecting node.

**Architecture:** A typed-value envelope (`{type:"json"|"text"|"file", …}`) rides inside the existing JSONB I/O columns — no column-type change; untyped legacy/agent values normalize to `json` client-side. Files store to local disk under a settings root with a new tenant-scoped `workflow_files` table (RLS) + a run-agnostic multipart upload and an **authenticated** (JWT, blob-fetch) download. Refuse gets a `refuse_reason` column plumbed through the confirm endpoint and the nodes read-model. The engine, `create_run`, and the decision endpoint are unchanged (they already store JSONB verbatim).

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Alembic, Postgres RLS; React 18 + TypeScript + TanStack Query + the app's custom `ui/` primitives.

## Global Constraints

- **No new test files** unless explicitly requested (CLAUDE.md override). Per-task verification is a smoke check: backend = venv import/route check (`backend/.venv/Scripts/python.exe`), frontend = `npx tsc --noEmit` from `frontend/` (only NEW errors referencing changed files matter; the pre-existing `react-grab` error is not a finding — and react-grab is now installed).
- **Do not auto-run** lint/build/format. Backend `alembic upgrade head` is NOT a task step (run manually before Task 9).
- All backend code under `backend/`, frontend under `frontend/`. Paths are repo-relative.
- **RLS:** new table gets ENABLE+FORCE+`tenant_isolation_policy`+`GRANT SELECT, INSERT, UPDATE` to `APP_ROLE = "vaic_app"`, matching 3A/3B migrations. After every `commit()` in a job, `_reassert_rls` — N/A here (endpoints run one request-scoped session; no mid-request CAS commits added).
- **Migration head** is `d5e6f7a8b9c0`; the new migration's `down_revision` is `d5e6f7a8b9c0`; keep a single linear head.
- **JSONB writes** unchanged — the frontend sends the typed envelope as the `input`/`output` value; the backend stores it verbatim (as `create_run`/override already do).
- **Envelope helper** for JSON API responses mirrors `orchestrator/routes.py::_ok` (`{"data":…, "error":None, "meta":{}}`); `apiFetch` unwraps `data`.
- **Auth’d file download:** a plain `<a href>` will NOT carry the JWT, so downloads MUST be a blob-fetch with `authHeaders()` (see Task 4) — never a bare link to the protected endpoint.
- **Modularize** files over ~200 lines; PascalCase components, camelCase lib/hooks.

---

### Task 1: `WorkflowFile` model + `refuse_reason` column + migration

**Files:**
- Modify: `backend/app/modules/orchestrator/models.py`
- Create: `backend/alembic/versions/e6f7a8b9c0d1_workflow_files_and_refuse_reason.py`

**Interfaces:**
- Produces: ORM `WorkflowFile` (table `workflow_files`: `id, tenant_id, filename, content_type, size_bytes, storage_path, created_by, created_at`); `RunRollbackRequest.refuse_reason: Mapped[str | None]`.

- [ ] **Step 1: Add `refuse_reason` to `RunRollbackRequest`**

In `backend/app/modules/orchestrator/models.py`, in `RunRollbackRequest`, add after the `reason` column (the line `reason: Mapped[str | None] = mapped_column(Text, nullable=True)`):

```python
    refuse_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Add the `WorkflowFile` model**

At the end of `backend/app/modules/orchestrator/models.py`, add (`Integer`, `Text`, `String`, `DateTime`, `ForeignKey`, `UUID`, `func`, `uuid7`, `Mapped`, `mapped_column`, `datetime`, `uuid` are already imported — used by existing models):

```python
class WorkflowFile(Base):
    """A tenant-scoped uploaded file referenced by a typed node/run value (3E).

    Bytes live on local disk at `storage_path`; this row is the metadata +
    tenant RLS gate. Referenced from JSONB I/O as
    {"type":"file","file_id":<id>,"name":…,"mime":…,"size":…}.
    """

    __tablename__ = "workflow_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 3: Create the migration**

Create `backend/alembic/versions/e6f7a8b9c0d1_workflow_files_and_refuse_reason.py`:

```python
"""workflow_files table + run_rollback_requests.refuse_reason (3E)

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-18 20:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy
            ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
        """
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO {APP_ROLE};")


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def upgrade() -> None:
    op.add_column(
        "run_rollback_requests",
        sa.Column("refuse_reason", sa.Text(), nullable=True),
    )
    op.create_table(
        "workflow_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_workflow_files_tenant_id", "workflow_files", ["tenant_id"]
    )
    _enable_rls("workflow_files")


def downgrade() -> None:
    _disable_rls("workflow_files")
    op.drop_table("workflow_files")
    op.drop_column("run_rollback_requests", "refuse_reason")
```

- [ ] **Step 4: Verify model imports + single head**

```bash
cd backend && .venv/Scripts/python.exe -c "from app.modules.orchestrator.models import WorkflowFile, RunRollbackRequest; print(WorkflowFile.__tablename__, hasattr(RunRollbackRequest, 'refuse_reason'))"
```
Expected: `workflow_files True`
```bash
cd backend && .venv/Scripts/python.exe -m alembic heads
```
Expected: exactly one head, `e6f7a8b9c0d1 (head)`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/orchestrator/models.py backend/alembic/versions/e6f7a8b9c0d1_workflow_files_and_refuse_reason.py
git commit -m "feat(orchestrator): workflow_files model + refuse_reason column + migration (3E)"
```

---

### Task 2: `workflow_files_root` setting

**Files:**
- Modify: `backend/app/core/settings.py`

**Interfaces:**
- Produces: `Settings.workflow_files_root: str` (default `.workflow-files`).

- [ ] **Step 1: Add the setting**

In `backend/app/core/settings.py`, immediately after the `mini_app_bundle_root` Field (ends at the line with the closing `)` around line 162), add:

```python
    # 3E — root directory for uploaded workflow files (typed node/run I/O of
    # type "file"). Bytes land at `{workflow_files_root}/{tenant_id}/{id}_{name}`.
    # Repo-relative default under `backend/` (resolves to `backend/.workflow-files`).
    # Served ONLY via the authenticated GET /workflows/files/{id} route (never a
    # public StaticFiles mount) — run data is tenant-private.
    workflow_files_root: str = Field(
        default=".workflow-files",
        description="Root directory for uploaded workflow files (relative to cwd `backend/`).",
    )
```

- [ ] **Step 2: Verify**

```bash
cd backend && .venv/Scripts/python.exe -c "from app.core.settings import get_settings; print(get_settings().workflow_files_root)"
```
Expected: `.workflow-files`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/settings.py
git commit -m "feat(core): workflow_files_root setting (3E)"
```

---

### Task 3: `file_routes.py` — upload + download endpoints + mount + startup mkdir

**Files:**
- Create: `backend/app/modules/orchestrator/file_routes.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `get_tenant_session`, `tenant_context`, `WorkflowFile`, `get_settings`, `NotFoundError`, `ValidationError`, `uuid7`.
- Produces: `router` with `POST /workflows/files` → `201 {data:{id,name,mime,size}}`; `GET /workflows/files/{file_id}` → `FileResponse`.

- [ ] **Step 1: Write the router**

Create `backend/app/modules/orchestrator/file_routes.py`:

```python
"""Tenant-scoped uploaded-file storage for typed workflow I/O (3E).

Run-agnostic upload (POST /workflows/files) + authenticated download
(GET /workflows/files/{id}). Bytes on local disk under
`settings.workflow_files_root/{tenant_id}/{id}_{safe_name}`; the row is the
tenant RLS gate. NOT a StaticFiles mount — download is JWT/tenant-scoped.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.context import tenant_context
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import uuid7
from app.core.settings import get_settings
from app.core.deps import get_tenant_session
from app.modules.orchestrator.models import WorkflowFile

router = APIRouter(prefix="/workflows/files", tags=["workflows-files"])

_MAX_BYTES = 20 * 1024 * 1024  # 20 MB, matches KB upload cap
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _safe_name(name: str) -> str:
    cleaned = _SAFE.sub("_", name).strip("._") or "file"
    return cleaned[:255]


@router.post("")
def upload_file_route(
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> JSONResponse:
    data = file.file.read()
    if len(data) > _MAX_BYTES:
        raise ValidationError("file too large (max 20MB)", code="file_too_large")
    tenant_id = tenant_context.get()
    file_id = uuid7()
    safe = _safe_name(file.filename or "file")
    root = Path(get_settings().workflow_files_root) / str(tenant_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{file_id}_{safe}"
    path.write_bytes(data)

    user_id = getattr(request.state, "user_id", None)
    row = WorkflowFile(
        id=file_id,
        tenant_id=tenant_id,
        filename=safe,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        storage_path=str(path),
        created_by=uuid.UUID(str(user_id)) if user_id else None,
    )
    session.add(row)
    session.commit()
    return JSONResponse(
        status_code=201,
        content=_ok(
            {
                "id": str(row.id),
                "name": row.filename,
                "mime": row.content_type,
                "size": row.size_bytes,
            }
        ),
    )


@router.get("/{file_id}")
def download_file_route(
    file_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> FileResponse:
    row = session.get(WorkflowFile, file_id)  # RLS hides cross-tenant rows
    if row is None or not os.path.exists(row.storage_path):
        raise NotFoundError("file not found")
    return FileResponse(
        row.storage_path,
        media_type=row.content_type,
        filename=row.filename,
    )
```

Notes for the implementer:
- `tenant_context` import path: the codebase reads `tenant_context.get()` in `orchestrator/service.py` and `kb_service.py`. Confirm the module (`grep -rn "tenant_context" backend/app/core | head`) and fix the `from app.core... import tenant_context` line if it differs. The smoke import (Step 3) surfaces a wrong path.
- `session.get(WorkflowFile, file_id)` runs under RLS from `get_tenant_session` (role + `app.tenant_id` set), so a cross-tenant id returns `None` → 404.

- [ ] **Step 2: Mount + startup mkdir in `main.py`**

In `backend/app/main.py`, next to `from app.modules.orchestrator.graph_routes import router as workflows_graph_router` (line 35), add:

```python
from app.modules.orchestrator.file_routes import router as workflows_files_router
```

Next to `app.include_router(workflows_graph_router)` (line 107), add:

```python
app.include_router(workflows_files_router)
```

After the mini-app bundle `mkdir` block (the `_mini_app_bundle_root.mkdir(...)` around line 122), add:

```python
# 3E — ensure the uploaded-workflow-files root exists at boot.
Path(get_settings().workflow_files_root).mkdir(parents=True, exist_ok=True)
```

(`Path` and `get_settings` are already imported in `main.py`.)

- [ ] **Step 3: Verify routes present + app imports**

```bash
cd backend && .venv/Scripts/python.exe -c "from app.modules.orchestrator.file_routes import router; print(sorted(r.path for r in router.routes)); import app.main"
```
Expected includes: `['/workflows/files', '/workflows/files/{file_id}']` and no import error.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/orchestrator/file_routes.py backend/app/main.py
git commit -m "feat(orchestrator): tenant-scoped workflow file upload/download endpoints (3E)"
```

---

### Task 4: Refuse-reason plumb-through (backend)

**Files:**
- Modify: `backend/app/modules/orchestrator/graph_review.py`
- Modify: `backend/app/modules/orchestrator/graph_routes.py`

**Interfaces:**
- Consumes: existing `confirm_rollback`, `_refuse_rollback`, `_ser_req` (graph_review), `ConfirmRequest` (graph_routes).
- Produces: `confirm_rollback(..., refuse_reason: str | None = None)`; refused `_ser_req` entries include `refuse_reason`; `ConfirmRequest.reason`.

- [ ] **Step 1: Thread `refuse_reason` through `confirm_rollback` + `_refuse_rollback`**

In `backend/app/modules/orchestrator/graph_review.py`:

Change `confirm_rollback`'s signature and the refuse call. Replace the current signature block and the `if accept:` block (lines ~242–263) so the function accepts `refuse_reason` and passes it on:

```python
def confirm_rollback(
    session: Session,
    run_id: uuid.UUID | str,
    rollback_id: uuid.UUID | str,
    *,
    accept: bool,
    actor_user_id: uuid.UUID | str,
    refuse_reason: str | None = None,
) -> dict[str, Any]:
    req = session.get(RunRollbackRequest, uuid.UUID(str(rollback_id)))
    if req is None or str(req.run_id) != str(run_id):
        raise ReviewError(404, "rollback request not found")
    if req.status != "pending":
        raise ReviewError(409, "rollback already resolved")
    target_row = _get_node(session, run_id, req.target_node_key)
    _require_approver(target_row, actor_user_id)

    if accept:
        _accept_rollback(session, run_id, req, decided_by=actor_user_id)
    else:
        _refuse_rollback(
            session, run_id, req, decided_by=actor_user_id, refuse_reason=refuse_reason
        )
    _reassert_rls(session)
    return {"id": str(req.id), "status": "accepted" if accept else "refused"}
```

Change `_refuse_rollback` to accept and store `refuse_reason`. Replace its signature and the first `UPDATE run_rollback_requests` statement (lines ~337–352) with:

```python
def _refuse_rollback(
    session: Session,
    run_id: uuid.UUID | str,
    req: RunRollbackRequest,
    *,
    decided_by: uuid.UUID | str,
    refuse_reason: str | None = None,
) -> None:
    _reassert_rls(session)
    session.execute(
        text(
            "UPDATE run_rollback_requests SET status='refused', decided_by=:by, "
            "refuse_reason=:refuse_reason, decided_at=now() WHERE id=:id"
        ),
        {"by": str(decided_by), "refuse_reason": refuse_reason, "id": str(req.id)},
    )
    session.commit()
```

(Leave the rest of `_refuse_rollback` — the requester-node decision clear + audit — unchanged.)

- [ ] **Step 2: Expose `refuse_reason` in the read model**

In the same file, in `list_run_nodes`, extend `_ser_req` to include `refuse_reason`:

```python
    def _ser_req(r: RunRollbackRequest) -> dict[str, Any]:
        return {
            "id": str(r.id),
            "requester_node_key": r.requester_node_key,
            "target_node_key": r.target_node_key,
            "reason": r.reason,
            "refuse_reason": r.refuse_reason,
            "status": r.status,
        }
```

- [ ] **Step 3: Accept `reason` on the confirm endpoint**

In `backend/app/modules/orchestrator/graph_routes.py`, find `class ConfirmRequest(BaseModel)` (body `{"accept": bool}`) and add the optional reason:

```python
class ConfirmRequest(BaseModel):
    accept: bool
    reason: str | None = None
```

Then in `rollback_confirm_route`, pass it through to the service — change the `confirm_rollback(...)` call to include `refuse_reason=body.reason`:

```python
        data = confirm_rollback(
            session,
            run_id,
            rollback_id,
            accept=body.accept,
            actor_user_id=_actor_user_id(request),
            refuse_reason=body.reason,
        )
```

- [ ] **Step 4: Verify imports**

```bash
cd backend && .venv/Scripts/python.exe -c "from app.modules.orchestrator.graph_review import confirm_rollback, list_run_nodes; from app.modules.orchestrator.graph_routes import router; import inspect; print('refuse_reason' in inspect.signature(confirm_rollback).parameters)"
```
Expected: `True`

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/orchestrator/graph_review.py backend/app/modules/orchestrator/graph_routes.py
git commit -m "feat(orchestrator): capture + expose rollback refuse_reason (3E)"
```

---

### Task 5: `typedValue.ts` + `runsApi.ts` additions

**Files:**
- Create: `frontend/src/lib/typedValue.ts`
- Modify: `frontend/src/lib/runsApi.ts`

**Interfaces:**
- Produces (`typedValue.ts`): `FileRef`, `TypedValue`, `TypedValueDraft`, `emptyDraft()`, `toTyped(raw)`, `resolveDraft(draft)`, `uploadWorkflowFile(file)`, `downloadWorkflowFile(ref)`.
- Produces (`runsApi.ts`): `RollbackRequest.refuse_reason?: string | null`; `confirmRollback(runId, rollbackId, accept, reason?)`.

- [ ] **Step 1: Write `typedValue.ts`**

Create `frontend/src/lib/typedValue.ts`:

```typescript
/* 3E — typed workflow I/O values (json | text | file) + file upload/download.
 * Untyped legacy/agent values normalize to {type:"json"}. File download is a
 * JWT-authed blob fetch (a bare <a href> would not carry the Authorization
 * header the protected endpoint requires).
 */
import { apiFetch, authHeaders } from "./api";

export interface FileRef {
  file_id: string;
  name: string;
  mime: string;
  size: number;
}

export type TypedValue =
  | { type: "json"; value: unknown }
  | { type: "text"; value: string }
  | ({ type: "file" } & FileRef);

/** Normalize any stored value to a TypedValue (legacy/agent dicts → json). */
export function toTyped(raw: unknown): TypedValue {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const t = (raw as { type?: unknown }).type;
    const r = raw as Record<string, unknown>;
    if (t === "text" && typeof r.value === "string") {
      return { type: "text", value: r.value };
    }
    if (t === "file" && typeof r.file_id === "string") {
      return {
        type: "file",
        file_id: r.file_id as string,
        name: String(r.name ?? "file"),
        mime: String(r.mime ?? "application/octet-stream"),
        size: Number(r.size ?? 0),
      };
    }
    if (t === "json" && "value" in r) {
      return { type: "json", value: r.value };
    }
  }
  return { type: "json", value: raw };
}

/** Editing draft held by TypedValueInput; resolved at submit. */
export interface TypedValueDraft {
  type: "json" | "text" | "file";
  jsonText: string;
  text: string;
  file: FileRef | null;
}

export function emptyDraft(): TypedValueDraft {
  return { type: "json", jsonText: "{}", text: "", file: null };
}

export function resolveDraft(
  d: TypedValueDraft,
): { ok: true; value: TypedValue } | { ok: false; error: string } {
  if (d.type === "json") {
    try {
      return { ok: true, value: { type: "json", value: JSON.parse(d.jsonText) } };
    } catch {
      return { ok: false, error: "Input must be valid JSON" };
    }
  }
  if (d.type === "text") {
    return { ok: true, value: { type: "text", value: d.text } };
  }
  if (!d.file) return { ok: false, error: "Choose a file to upload" };
  return { ok: true, value: { type: "file", ...d.file } };
}

export async function uploadWorkflowFile(file: File): Promise<FileRef> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await apiFetch<{ id: string; name: string; mime: string; size: number }>(
    "/workflows/files",
    { method: "POST", body: fd },
  );
  return { file_id: r.id, name: r.name, mime: r.mime, size: r.size };
}

/** Download via authed blob fetch (protected endpoint needs the JWT header). */
export async function downloadWorkflowFile(ref: FileRef): Promise<void> {
  const resp = await fetch(`/workflows/files/${ref.file_id}`, {
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error("Download failed");
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = ref.name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

(`authHeaders` is exported from `frontend/src/lib/api.ts`.)

- [ ] **Step 2: Extend `runsApi.ts`**

In `frontend/src/lib/runsApi.ts`, add `refuse_reason` to `RollbackRequest`:

```typescript
export interface RollbackRequest {
  id: string;
  requester_node_key: string;
  target_node_key: string;
  reason: string | null;
  refuse_reason?: string | null;
  status: string;
}
```

And change `confirmRollback` to take an optional `reason`:

```typescript
export function confirmRollback(
  runId: string,
  rollbackId: string,
  accept: boolean,
  reason?: string,
): Promise<{ id: string; status: string }> {
  return apiFetch<{ id: string; status: string }>(
    `/workflows/runs/${runId}/rollbacks/${rollbackId}/confirm`,
    { method: "POST", body: JSON.stringify({ accept, reason }) },
  );
}
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing `typedValue.ts` or `runsApi.ts`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/typedValue.ts frontend/src/lib/runsApi.ts
git commit -m "feat(runs): typed-value model + file upload/download + confirm reason (3E)"
```

---

### Task 6: `TypedValueViewer` + `NodeIoViewer` refit

**Files:**
- Create: `frontend/src/components/workflows/runs/TypedValueViewer.tsx`
- Modify: `frontend/src/components/workflows/runs/NodeIoViewer.tsx`

**Interfaces:**
- Consumes: `toTyped`, `downloadWorkflowFile` (Task 5), `Button`, `useToast`.
- Produces: `TypedValueViewer({ value }: { value: unknown })`; `NodeIoViewer` renders `label` + `TypedValueViewer`.

- [ ] **Step 1: Write `TypedValueViewer.tsx`**

Create `frontend/src/components/workflows/runs/TypedValueViewer.tsx`:

```tsx
/* 3E — render a stored I/O value by its type: json (pre), text (plain), file
 * (authed download button). Legacy/agent dicts normalize to json via toTyped.
 */
import { Button, useToast } from "../../ui";
import { downloadWorkflowFile, toTyped } from "../../../lib/typedValue";

export interface TypedValueViewerProps {
  value: unknown;
}

export default function TypedValueViewer({ value }: TypedValueViewerProps) {
  const toast = useToast();
  if (value == null) {
    return <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>—</span>;
  }
  const tv = toTyped(value);

  if (tv.type === "file") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <Button
          variant="secondary"
          onClick={() =>
            downloadWorkflowFile(tv).catch((e) =>
              toast.show((e as Error).message, "error"),
            )
          }
        >
          Download {tv.name}
        </Button>
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          {tv.mime} · {(tv.size / 1024).toFixed(1)} KB
        </span>
      </div>
    );
  }

  const text =
    tv.type === "text" ? tv.value : JSON.stringify(tv.value, null, 2);
  return (
    <pre
      style={{
        margin: 0,
        padding: "var(--space-2)",
        background: "var(--color-surface-inset, var(--color-surface))",
        borderRadius: "var(--radius-control, 6px)",
        overflow: "auto",
        maxHeight: 200,
        fontSize: "0.85em",
        whiteSpace: "pre-wrap",
      }}
    >
      {text}
    </pre>
  );
}
```

- [ ] **Step 2: Refit `NodeIoViewer.tsx`**

Replace the body of `frontend/src/components/workflows/runs/NodeIoViewer.tsx` with a thin label + `TypedValueViewer`:

```tsx
/* 3E — labelled typed I/O value (json | text | file). */
import TypedValueViewer from "./TypedValueViewer";

export interface NodeIoViewerProps {
  label: string;
  value: unknown;
}

export default function NodeIoViewer({ label, value }: NodeIoViewerProps) {
  return (
    <div style={{ marginBottom: "var(--space-3)" }}>
      <div
        className="text-body"
        style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-1)" }}
      >
        {label}
      </div>
      <TypedValueViewer value={value} />
    </div>
  );
}
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing the two files.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workflows/runs/TypedValueViewer.tsx frontend/src/components/workflows/runs/NodeIoViewer.tsx
git commit -m "feat(runs): typed-value viewer (json/text/file) + NodeIoViewer refit (3E)"
```

---

### Task 7: `TypedValueInput`

**Files:**
- Create: `frontend/src/components/workflows/runs/TypedValueInput.tsx`

**Interfaces:**
- Consumes: `TypedValueDraft`, `uploadWorkflowFile` (Task 5), `Button`, `useToast`.
- Produces: `TypedValueInput({ value, onChange }: { value: TypedValueDraft; onChange: (d: TypedValueDraft) => void })`.

- [ ] **Step 1: Write `TypedValueInput.tsx`**

Create `frontend/src/components/workflows/runs/TypedValueInput.tsx`:

```tsx
/* 3E — controlled input for a typed value: a type selector (JSON | Text |
 * File) + the matching editor. File selection uploads immediately and stores
 * the returned ref on the draft. The parent resolves the draft at submit
 * (resolveDraft) so JSON parsing / file-required checks happen on submit.
 */
import { useState } from "react";
import { Button, useToast } from "../../ui";
import { uploadWorkflowFile, type TypedValueDraft } from "../../../lib/typedValue";

export interface TypedValueInputProps {
  value: TypedValueDraft;
  onChange: (draft: TypedValueDraft) => void;
}

export default function TypedValueInput({ value, onChange }: TypedValueInputProps) {
  const toast = useToast();
  const [uploading, setUploading] = useState(false);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const ref = await uploadWorkflowFile(f);
      onChange({ ...value, file: ref });
    } catch (err) {
      toast.show((err as Error).message, "error");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <select
        className="vaic-form-input vaic-focusable"
        value={value.type}
        onChange={(e) =>
          onChange({ ...value, type: e.target.value as TypedValueDraft["type"] })
        }
      >
        <option value="json">JSON</option>
        <option value="text">Text</option>
        <option value="file">File</option>
      </select>

      {value.type === "json" && (
        <textarea
          className="vaic-form-input vaic-focusable"
          value={value.jsonText}
          onChange={(e) => onChange({ ...value, jsonText: e.target.value })}
          rows={3}
        />
      )}

      {value.type === "text" && (
        <textarea
          className="vaic-form-input vaic-focusable"
          placeholder="Plain text"
          value={value.text}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          rows={3}
        />
      )}

      {value.type === "file" && (
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <input type="file" onChange={onFile} disabled={uploading} />
          {uploading && <span className="text-body">Uploading…</span>}
          {value.file && (
            <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
              {value.file.name} ({(value.file.size / 1024).toFixed(1)} KB)
            </span>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing `TypedValueInput.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workflows/runs/TypedValueInput.tsx
git commit -m "feat(runs): typed-value input with type picker + file upload (3E)"
```

---

### Task 8: Wire `TypedValueInput` into the Runs tab + Override

**Files:**
- Modify: `frontend/src/components/workflows/RunsTab.tsx`
- Modify: `frontend/src/components/workflows/runs/RunReviewPanel.tsx`

**Interfaces:**
- Consumes: `TypedValueInput` (Task 7), `emptyDraft`/`resolveDraft` (Task 5).

- [ ] **Step 1: Runs-tab "New run" uses the typed input**

In `frontend/src/components/workflows/RunsTab.tsx`:

Add imports:
```tsx
import TypedValueInput from "./runs/TypedValueInput";
import { emptyDraft, resolveDraft } from "../../lib/typedValue";
```

Replace the input state `const [inputText, setInputText] = useState("{}");` with:
```tsx
const [draft, setDraft] = useState(emptyDraft());
```

Replace the `onCreate` JSON-parse block (the `let parsed…; try { parsed = JSON.parse(inputText); } catch {…}` and the object guard) with a `resolveDraft` call. The `onCreate` body becomes:
```tsx
  async function onCreate() {
    const resolved = resolveDraft(draft);
    if (!resolved.ok) {
      toast.show(resolved.error, "error");
      return;
    }
    setCreating(true);
    try {
      const run = await createRun(workflowId, resolved.value as Record<string, unknown>);
      queryClient.invalidateQueries({ queryKey: ["runs", workflowId] });
      navigate(`/workflows/${workflowId}/runs/${run.id}`);
    } catch (e) {
      toast.show((e as Error).message, "error");
    } finally {
      setCreating(false);
    }
  }
```

Replace the label + `<textarea …value={inputText}…/>` JSX with:
```tsx
        <label className="text-body">New run input</label>
        <TypedValueInput value={draft} onChange={setDraft} />
```

- [ ] **Step 2: Override editor uses the typed input**

In `frontend/src/components/workflows/runs/RunReviewPanel.tsx`:

Add imports:
```tsx
import TypedValueInput from "./TypedValueInput";
import { emptyDraft, resolveDraft } from "../../../lib/typedValue";
```

Replace `const [overrideText, setOverrideText] = useState("{}");` with:
```tsx
  const [overrideDraft, setOverrideDraft] = useState(emptyDraft());
```

Replace `onOverride` with:
```tsx
  function onOverride() {
    const resolved = resolveDraft(overrideDraft);
    if (!resolved.ok) {
      toast.show(resolved.error, "error");
      return;
    }
    submit({ action: "override", output: resolved.value as Record<string, unknown> });
  }
```

Replace the Override block JSX (`<label…>Override output (JSON)</label>` + its `<textarea …value={overrideText}…/>`) with:
```tsx
              <label className="text-body">Override output</label>
              <TypedValueInput value={overrideDraft} onChange={setOverrideDraft} />
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing `RunsTab.tsx` or `RunReviewPanel.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workflows/RunsTab.tsx frontend/src/components/workflows/runs/RunReviewPanel.tsx
git commit -m "feat(runs): typed input for New-run + Override (json/text/file) (3E)"
```

---

### Task 9: Refuse insight — reason capture + refused card

**Files:**
- Modify: `frontend/src/components/workflows/runs/RollbackConfirmCard.tsx`
- Modify: `frontend/src/components/workflows/runs/RunReviewPanel.tsx`

**Interfaces:**
- Consumes: `confirmRollback` reason arg (Task 5), `RollbackRequest.refuse_reason` (Task 5).

- [ ] **Step 1: Refuse-reason input on `RollbackConfirmCard`**

Replace `frontend/src/components/workflows/runs/RollbackConfirmCard.tsx` with a version that captures an optional refuse reason and passes it up:

```tsx
/* 3C/3E — target node's approver confirms a pending rollback: Accept (re-run
 * subtree) or Refuse (with an optional reason shown back to the rejecter).
 */
import { useState } from "react";
import { Button, Card } from "../../ui";
import type { RollbackRequest } from "../../../lib/runsApi";

export interface RollbackConfirmCardProps {
  rollback: RollbackRequest;
  onConfirm: (accept: boolean, reason?: string) => void;
  pending: boolean;
}

export default function RollbackConfirmCard({
  rollback,
  onConfirm,
  pending,
}: RollbackConfirmCardProps) {
  const [reason, setReason] = useState("");
  return (
    <Card>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        <strong className="text-body">Rollback requested to this node</strong>
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          From node “{rollback.requester_node_key}”. Reason: {rollback.reason || "—"}
        </span>
        <textarea
          className="vaic-form-input vaic-focusable"
          placeholder="Reason (shown to the requester if you refuse)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
        />
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button variant="primary" disabled={pending} onClick={() => onConfirm(true)}>
            Accept
          </Button>
          <Button
            variant="secondary"
            disabled={pending}
            onClick={() => onConfirm(false, reason)}
          >
            Refuse
          </Button>
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Pass the reason through + show the refused card in `RunReviewPanel`**

In `frontend/src/components/workflows/runs/RunReviewPanel.tsx`:

Update the confirm mutation call to forward the reason — change the `onConfirm` prop passed to `RollbackConfirmCard`:

```tsx
          onConfirm={(accept, reason) =>
            mutations.confirm.mutate(
              { rollbackId: pendingForThisTarget.id, accept, reason },
              {
                onError: (err) => toast.show(err.message, "error"),
              },
            )
          }
```

Add a refused-insight card. Right after the `pendingForThisTarget` block (the `{pendingForThisTarget && isApprover && (…)}` JSX) add:

```tsx
      {rollbacks.refused
        .filter((r) => r.requester_node_key === node.node_key)
        .map((r) => (
          <Card key={r.id}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <strong className="text-body">
                Rollback to “{r.target_node_key}” was refused
              </strong>
              <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
                Your reason: {r.reason || "—"}
              </span>
              <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
                Refuse reason: {r.refuse_reason || "—"}
              </span>
              <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
                Resolve via Approve / Retry / Override.
              </span>
            </div>
          </Card>
        ))}
```

The `mutations.confirm.mutate` variables now include `reason`; that matches `useRunMutations`' `confirm` mutation shape `{ rollbackId, accept }` — **update that mutation to accept `reason`** (Task 9 Step 3).

- [ ] **Step 3: Thread `reason` through the confirm mutation**

In `frontend/src/hooks/useRunMutations.ts`, widen the `confirm` mutation's variables and call:

Change the `confirm` `UseMutationResult` generic and `mutationFn`:
```tsx
  const confirm = useMutation<
    { id: string; status: string },
    Error,
    { rollbackId: string; accept: boolean; reason?: string }
  >({
    mutationFn: ({ rollbackId, accept, reason }) =>
      confirmRollback(runId, rollbackId, accept, reason),
    onSuccess: invalidate,
  });
```

And update the `UseRunMutationsResult` interface's `confirm` type accordingly:
```tsx
  confirm: UseMutationResult<
    { id: string; status: string },
    Error,
    { rollbackId: string; accept: boolean; reason?: string }
  >;
```

- [ ] **Step 4: Verify**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors referencing `RollbackConfirmCard.tsx`, `RunReviewPanel.tsx`, or `useRunMutations.ts`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workflows/runs/RollbackConfirmCard.tsx frontend/src/components/workflows/runs/RunReviewPanel.tsx frontend/src/hooks/useRunMutations.ts
git commit -m "feat(runs): refuse-reason capture + refused-rollback insight card (3E)"
```

---

### Task 10: End-to-end manual verification (acceptance gate)

**Files:** none.

Needs the stack up (Postgres + Redis + backend + arq worker + frontend) and `alembic upgrade head` (applies `e6f7a8b9c0d1`). If exercising agent nodes without a real LLM key, run the worker with the temporary mock adapter (`VAIC_LLM_MOCK=1`) as in the 3C E2E.

- [ ] **Step 1: Apply the migration**

```bash
cd backend && .venv/Scripts/python.exe -m alembic upgrade head
```
Expected: upgrades to `e6f7a8b9c0d1`.

- [ ] **Step 2: Drive in the browser (client-side nav; `/workflows/*` is dev-proxied to the API)**

1. On a graph workflow's **Runs** tab, set the "New run" type to **Text**, enter some text, **Run** → open the run → the node **Input** renders as text (not JSON).
2. New run with type **File**, pick a small file → it uploads → **Run** → the run's node **Input** shows a **Download** button; click it → the file downloads (authed).
3. At a gated node, **Override** with type **Text** (or File) → the node **Output** renders that type.
4. Reject a gated node to a **gated** parent → as that parent's approver, **Refuse** with a reason → select the rejecting node → the **"Rollback to X was refused"** card shows your original reason + the refuse reason; the parent stays disabled in the reject picker.

Expected: each type round-trips (input → display), file download works, refuse reason is captured and surfaced. No console errors.

---

## Notes for the executor

- **`tenant_context` import (Task 3):** confirm the module via `grep -rn "tenant_context" backend/app/core | head` and fix the import line if needed — the smoke import surfaces it.
- **Auth’d download (Task 5):** the blob-fetch + `authHeaders()` approach is deliberate — a bare `<a href="/workflows/files/…">` would 401 (no JWT). Do not "simplify" it to a link.
- **Back-compat:** `toTyped` makes every pre-3E value (plain agent JSON) render as JSON — existing runs display unchanged.
- **Migration:** `alembic upgrade head` is manual (project preference), done in Task 10 Step 1.
- **Temp E2E scaffolding:** the 3C mock LLM adapter (`app/core/adapters/mock_llm.py` + the `VAIC_LLM_MOCK` short-circuit in `registry.py`) is uncommitted and may still be present; it is NOT part of 3E and must not be committed. Revert it after E2E.

## Open questions

- **Downstream agent consuming file bytes:** a node receiving a parent's `{type:file}` envelope sees metadata only (no fetch). Fine for the demo; revisit if a node must read file contents.
- **Orphaned uploads:** a `workflow_files` row/disk file for a never-triggered run leaks; a later GC can sweep unreferenced files. Accepted for the demo.
- **Override type vs node expected type:** stored verbatim, no validation (consistent with 3A/3C).
