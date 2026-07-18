# Graph Workflow — Typed Node I/O + Refuse Insight (Sub-project 3E)

**Date:** 2026-07-18
**Status:** Design approved, pending spec review
**Depends on:** 3A (data model), 3B (engine + review/rollback), 3C (run-tracking UI).
**Scope:** Two independent enhancements surfaced during the 3C live E2E: (1) node/run input & output are not always JSON — support **Text** and **File** alongside JSON, user-selectable, with a shared typed-value input + viewer; (2) a **refused rollback** must give the rejecting node feedback — capture the refuser's reason and surface the original request + both reasons.

## 1. Context & Problem

3C shipped the run-tracking + review UI. Two gaps emerged in use:

- **Rigid JSON I/O.** The Runs-tab "New run" input and the human **Override** editor accept only JSON; the I/O viewer renders only JSON. Real workflow data is often plain text or a file (a document to process, a generated report). Users need to choose the type.
- **Opaque refuse.** When a rollback target's approver **refuses**, 3C only disables that parent in the reject picker. The rejecting node gets no explanation — not the original request, not why it was refused — so the reviewer can't act on feedback before Approve/Retry/Override.

Both are additive. The engine, the four decisions, and the rollback protocol are unchanged.

## 2. Design Decisions (locked)

| Decision | Choice |
|---|---|
| Value types | `json`, `text`, `file` — user-selectable on human-supplied surfaces. |
| Storage of typed values | The existing JSONB columns (`run_node_executions.input/output`, `workflow_runs.input/result`) hold a **typed envelope**; no schema change to those columns. |
| Back-compat | An untyped value (plain dict, as agents produce) is normalized **client-side** to `{type:"json", value:<raw>}`. No engine/data migration. |
| File storage | **Local filesystem** under a settings root (mirrors mini-app bundles), + a new tenant-scoped `workflow_files` table (RLS). |
| File upload | **Run-agnostic** `POST /workflows/files` (multipart) — avoids the run-doesn't-exist-yet problem for run-level input. 20 MB cap (matches KB). |
| File download | **Authenticated** `GET /workflows/files/{id}` (tenant-scoped `FileResponse`) — NOT a public `StaticFiles` mount, since run data is tenant-private. |
| Type-picker surfaces | Runs-tab "New run" input **and** the Override editor. Agent outputs stay JSON. |
| Display | A shared `TypedValueViewer` renders every stored value by its `type` everywhere I/O is shown. |
| Refuse reason | New nullable `refuse_reason` column on `run_rollback_requests`; confirm body gains optional `reason` (used only when `accept=false`). |
| Refuse display | The rejecting node shows a "rollback refused" card: original reject reason + refuse reason; the parent stays disabled in the reject picker (3C behavior). |

## 3. Feature 1 — Typed input/output

### 3.1 Typed-value envelope

A value stored in any I/O JSONB is one of:

```json
{"type": "json", "value": { … }}
{"type": "text", "value": "…"}
{"type": "file", "file_id": "uuid", "name": "report.pdf", "mime": "application/pdf", "size": 12345}
```

**Normalization (client-side, `typedValue.ts`):** `toTyped(raw)` → if `raw` is an object with `type ∈ {json,text,file}` and the shape matches, return it; else return `{type:"json", value: raw}`. This makes every legacy/agent output render correctly with no backend change. `fromTyped(tv)` returns the wire value to send (the envelope itself — the backend stores it verbatim).

The engine's parent-output merge (`{parent_key: parent.output}`) passes envelopes through unchanged; a downstream agent receives the parent's typed envelope in its input dict (acceptable — agents already receive arbitrary JSON).

### 3.2 Backend — file storage

- **Settings:** `workflow_files_root: str = ".workflow-files"` (resolved from cwd like `mini_app_bundle_root`); `mkdir(parents=True, exist_ok=True)` at app startup.
- **Model + migration:** `workflow_files` table, tenant-scoped RLS (ENABLE+FORCE+policy+GRANT SELECT/INSERT/UPDATE, `APP_ROLE = "vaic_app"`), one Alembic migration (down_revision = 3C/3B head `d5e6f7a8b9c0`):

  | Column | Type | Notes |
  |---|---|---|
  | `id` | UUID PK | uuid7 |
  | `tenant_id` | UUID FK tenants CASCADE | RLS |
  | `filename` | String(255) | original name |
  | `content_type` | String(128) | MIME |
  | `size_bytes` | Integer | |
  | `storage_path` | Text | absolute/rooted path on disk |
  | `created_by` | UUID FK users RESTRICT, nullable | uploader |
  | `created_at` | timestamptz | |

- **Upload** `POST /workflows/files` (new router `orchestrator/file_routes.py`, `get_tenant_session`, `UploadFile`): read bytes (`.read()`, like KB), reject > 20 MB (`ValidationError`), write to `{root}/{tenant_id}/{id}_{safe_filename}` (sanitize filename), insert row (`tenant_id=tenant_context.get()`, `created_by=user`), return `201 {id, name, mime, size}`.
- **Download** `GET /workflows/files/{id}`: RLS-scoped fetch (404 cross-tenant/missing), `FileResponse(storage_path, media_type=content_type, filename=filename)`.
- **Auth:** both under the middleware that sets tenant context; download streams only the caller's tenant's file (RLS on the metadata row gate + tenant subdir).

### 3.3 Frontend — shared typed-value components

- `lib/typedValue.ts` — `TypedValue` type + `toTyped`/`fromTyped` + `uploadWorkflowFile(file): Promise<FileRef>` (POST multipart via `apiFetch` with FormData) + `fileDownloadUrl(id)`.
- `components/workflows/runs/TypedValueInput.tsx` — a `type` selector (JSON | Text | File) + the matching editor: JSON textarea (parse+validate, as 3C), Text textarea, File `<input type=file>` that on select uploads and stores the returned `FileRef` (shows name + size + a "replace" affordance). Emits a `TypedValue`. Controlled (`value`, `onChange`).
- `components/workflows/runs/TypedValueViewer.tsx` — renders a stored value via `toTyped`: JSON (existing `<pre>` styling), Text (plain), File (download link `GET /workflows/files/{id}` with name + size). Replaces `NodeIoViewer`'s body (NodeIoViewer becomes a thin label + `TypedValueViewer`).
- **Wiring:** Runs-tab "New run" uses `TypedValueInput` → `createRun` sends the envelope as `input`. RunReviewPanel Override uses `TypedValueInput` → `postDecision({action:"override", output: <envelope>})`. NodeIoViewer (input/output display) uses `TypedValueViewer`.

## 4. Feature 2 — Refuse insight

### 4.1 Backend

- **Migration:** add `refuse_reason Text NULL` to `run_rollback_requests` (same migration file as Feature 1, or a second — one is fine; both extend head `d5e6f7a8b9c0`; single linear head).
- **Model:** `RunRollbackRequest.refuse_reason: Mapped[str | None]`.
- **Confirm endpoint** `POST /workflows/runs/{run_id}/rollbacks/{rollback_id}/confirm` body `{accept: bool, reason?: str}`. `graph_review.confirm_rollback(..., refuse_reason=reason)`. `_refuse_rollback` stores `refuse_reason` on the request row (alongside the existing `refused` status + `decided_by`/`decided_at`).
- **Read model:** `list_run_nodes` `rollbacks.refused[]` entries already carry `requester_node_key, target_node_key, reason`; add `refuse_reason`. (`pending` entries unchanged.)

### 4.2 Frontend

- `RollbackConfirmCard` gains an optional reason `<textarea>` shown for the **Refuse** path; `onConfirm(accept, reason?)`; `confirmRollback(runId, id, accept, reason)`.
- `RunReviewPanel`: when the selected node is the **requester** of a refused rollback (`rollbacks.refused` where `requester_node_key === node.node_key`), render a "Rollback refused" card above the actions: target parent, original reject `reason`, and `refuse_reason`. The reject picker keeps disabling that parent (3C).
- `runsApi.ts`: `RollbackRequest` gains `refuse_reason?: string | null`; `confirmRollback` signature gains `reason?`.

## 5. APIs summary (new/changed)

| Method + path | Change |
|---|---|
| `POST /workflows/files` | NEW — multipart upload, returns `{id,name,mime,size}` |
| `GET /workflows/files/{id}` | NEW — authenticated tenant-scoped file download |
| `POST /workflows/runs/{run_id}/rollbacks/{rollback_id}/confirm` | body gains optional `reason` (refuse) |
| `GET /workflows/runs/{run_id}/nodes` | `rollbacks.refused[]` gains `refuse_reason` |

No change to the engine, `create_run`, the decision endpoint, or the graph/nodes topology.

## 6. Out of scope

- File previews/thumbnails (download link only), binary transforms, image rendering inline.
- File versioning / dedup / GC of orphaned uploads (a demo cleanup note is enough).
- Typed values for agent-produced outputs (they stay JSON; only human surfaces pick a type).
- Schema validation of Override against the node's expected type (verbatim store, per 3A/3C).
- Streaming/chunked upload (whole-file `.read()`, like KB).

## 7. Deliverables

1. Backend: `workflow_files` model + migration (RLS) + `refuse_reason` column; `file_routes.py` (upload + download) mounted; `workflow_files_root` setting + startup mkdir.
2. Backend: `confirm_rollback` refuse-reason plumb-through; `list_run_nodes` refused entries expose `refuse_reason`.
3. Frontend: `lib/typedValue.ts`; `TypedValueInput`, `TypedValueViewer`; NodeIoViewer refit; Runs-tab + Override wiring.
4. Frontend: refuse-reason input on `RollbackConfirmCard`; refused-rollback insight card in `RunReviewPanel`; `runsApi` type/signature updates.
5. Manual E2E: text + file run input, file output display/download, refuse-with-reason → insight card.

## 8. Open questions

- **Orphaned uploads:** a `workflow_files` row + disk file created for a run that's never triggered leaks. Leaning: accept for the demo (note it); a later GC can sweep files not referenced by any run I/O.
- **File ref in parent-output merge:** a downstream agent receives a parent's `{type:file,…}` envelope as input — the agent can't read the bytes (no fetch). Acceptable for the demo (the agent sees the metadata); flag if a node must consume file *contents*.
- **Filename sanitization:** strip path separators + control chars; keep extension. Confirm the sanitizer is sufficient (no need for content-type sniffing for the demo).
