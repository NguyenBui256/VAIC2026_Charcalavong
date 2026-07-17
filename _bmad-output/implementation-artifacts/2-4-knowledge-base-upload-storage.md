---
baseline_commit: 86e0dc8c653ccb3633a45d3fa8e37c53e4747fe7
---

# Story 2.4: Knowledge Base Upload & Storage

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user configuring a Specialist Agent**,
I want **to upload policy/SOP documents to my Agent's Knowledge Base**,
so that **the Agent can ground its responses in our bank's documented procedures**.

## Acceptance Criteria

1. **AC1 -- Upload a supported document into an Agent's KB**: Given an Agent exists in DepartmentX and the `McpClientPort` from Story 1.4 has a stub returning successful ingestion, when the user opens the Knowledge Base tab and uploads a document (PDF, TXT, Markdown, DOCX) up to 20MB, then the upload completes within 30s per document. (epics.md L740-742)
2. **AC2 -- Ingestion routes through McpClientPort with mandatory department scope (AD-11)**: The platform chunks, embeds, and indexes the document via `McpClientPort` with mandatory `tenant_id` + `department_id` matching the Agent's Department. A call missing either scope, or whose `department_id` does not match the calling Agent's Department, raises before the network. (epics.md L743, AD-11)
3. **AC3 -- Document appears in KB list with lifecycle status**: The document appears in the KB document list with status: `Processing` -> `Indexed` (or `Failed` with reason). (epics.md L744)
4. **AC4 -- Oversized upload rejected client-side**: When the upload exceeds 20MB, the upload is rejected client-side with a clear message before reaching the backend. (epics.md L745-746)
5. **AC5 -- Ingestion timeout produces a Failed status**: When ingestion exceeds 30s, the upload is aborted with a timeout error and the document status shows `Failed: Timeout`. (epics.md L747-748)
6. **AC6 -- Delete removes the document and all its chunks/embeddings**: When the user deletes a document, the document and all its chunks/embeddings are removed from the index (via `McpClientPort`). (epics.md L749-750)
7. **AC7 -- Every upload/delete emits an audit entry (FR-21, AD-4)**: Every upload/delete emits an `audit.log()` entry with `type: "kb.document.uploaded" | "kb.document.deleted"`. (epics.md L751, FR-21)
8. **AC8 -- No real customer PII (NFR-9)**: Documents are limited to policy/regulation/SOP content -- no real customer PII (banking data sensitivity). The KB tab surfaces a persistent notice; the audit entries capture only metadata (filename, size, status), never document contents. (epics.md L752, NFR-9)
9. **AC9 -- rag.search placeholder wired through McpClientPort (AD-3)**: A placeholder for the parallel-team MCP server's `rag.search` is invoked through `McpClientPort` -- the MCP server itself is built by another team (AD-3). VAIC ships the client-side call and scope guard only; server-side department isolation remains Open Question 5 with the parallel team. (epics.md L753, AD-3)

## Tasks / Subtasks

- [ ] **T1 -- Stub `McpClientPort` adapter with client-side AD-11 scope enforcement** (AC: #2, #6, #9)
  - [ ] T1.1 Create `backend/app/core/adapters/mcp_client.py`: `StubMcpClient` implementing `McpClientPort` (Protocol from `core/ports/mcp_client.py`). Async `call_tool(tool_name, arguments, *, tenant_id, department_id) -> ToolResult` and `list_tools(*, tenant_id, department_id) -> list[str]`.
  - [ ] T1.2 Client-side guard (AD-11): both `tenant_id` and `department_id` are required; if either is missing/None, raise `AuthorizationError` BEFORE any (stubbed) network step. Callers pass the Agent's own `department_id`; a mismatch against the Agent context raises. Never send an unscoped call.
  - [ ] T1.3 Stub behavior: `rag.ingest`/`rag.index` returns `ToolResult(success=True, output={"document_id": <uuid7>, "chunk_count": <n>})`; `rag.delete` returns `ToolResult(success=True, output={"deleted": True})`; `rag.search` returns `ToolResult(success=True, output={"passages": []})` (placeholder -- real server is out of scope, AD-3). Simulated failures return `ToolResult(success=False, error=...)`.
  - [ ] T1.4 The stub does NOT reach the network. Document in the module docstring that the real adapter (parallel-team MCP server) is out of scope per AD-3 and Open Question 5.
- [ ] **T2 -- `kb_documents` table + Alembic migration** (AC: #1, #3, #6)
  - [ ] T2.1 `uv run alembic revision -m "create kb_documents table"`.
  - [ ] T2.2 `upgrade()`: create `kb_documents` with columns `{id (PK, UUID v7), tenant_id (NOT NULL), department_id (NOT NULL), agent_id (FK -> agents), filename, content_type, size_bytes, status ('processing'|'indexed'|'failed'), failure_reason (nullable), mcp_document_id (nullable), chunk_count (nullable), created_at (timestamptz), updated_at (timestamptz)}`. Index on `(agent_id, created_at)` and `(tenant_id, agent_id)`.
  - [ ] T2.3 RLS: `ENABLE` + `FORCE ROW LEVEL SECURITY` + policy `tenant_isolation_policy` (USING + WITH CHECK on `tenant_id = current_setting('app.tenant_id')::uuid`) -- mirror Story 1.2/1.5 pattern. Grant `SELECT, INSERT, UPDATE, DELETE` to `vaic_app` (KB docs are mutable, unlike append-only `audit_trail`).
  - [ ] T2.4 `downgrade()`: drop policy, disable RLS, drop table.
  - [ ] T2.5 SQLAlchemy model `KbDocument` in `backend/app/modules/agent_builder/models.py` (co-located with the Agent record from Story 2.1).
- [ ] **T3 -- KB service layer** (AC: #1, #2, #3, #5, #6, #7, #8)
  - [ ] T3.1 In `backend/app/modules/agent_builder/service.py`, add a KB service: `upload_document(agent_id, filename, content_type, data)`, `list_documents(agent_id)`, `delete_document(agent_id, document_id)`.
  - [ ] T3.2 Server-side validation (defense in depth behind AC4/AC8): reject content types outside {PDF, TXT, Markdown, DOCX}; reject `size_bytes > 20MB`; return `ValidationError` (400 envelope).
  - [ ] T3.3 On upload: resolve the Agent's `department_id` from the Agent record (Story 2.1), insert a `kb_documents` row with `status='processing'`, then enqueue the ingest job (T4). Return the row immediately so the UI can poll.
  - [ ] T3.4 On delete: call `McpClientPort.call_tool("rag.delete", {mcp_document_id}, tenant_id=..., department_id=<agent dept>)`, then delete the `kb_documents` row.
  - [ ] T3.5 Emit audit on every upload/delete via `audit.log()` (`PostgresAuditSink` from Story 1.5): `type: "kb.document.uploaded"` / `"kb.document.deleted"`, `input`/`output` carry metadata ONLY (agent_id, filename, size_bytes, status) -- NEVER document bytes/content (NFR-9).
- [ ] **T4 -- Async ingest job with 30s timeout + status transitions** (AC: #1, #3, #5)
  - [ ] T4.1 Add an arq job (Story 1.7 foundation) that runs ingestion off the request path so the upload endpoint returns promptly.
  - [ ] T4.2 Materialize `tenant_id` + `department_id` into the job payload and re-set tenant context at worker entry (AD-10 -- ContextVar dies at the worker boundary).
  - [ ] T4.3 Job calls `McpClientPort.call_tool("rag.ingest", {agent_id, filename, ...}, tenant_id=..., department_id=<agent dept>)` under a 30s deadline (`asyncio.timeout(30)`).
  - [ ] T4.4 On success: update row `status='indexed'`, store `mcp_document_id` + `chunk_count`. On `asyncio.TimeoutError`: update `status='failed'`, `failure_reason='Timeout'` (surfaces as "Failed: Timeout"). On any other error: `status='failed'`, `failure_reason=<message>`.
- [ ] **T5 -- Backend routes** (AC: #1, #3, #4, #6)
  - [ ] T5.1 In `backend/app/modules/agent_builder/routes.py`: `POST /agents/{agent_id}/kb/documents` (multipart upload), `GET /agents/{agent_id}/kb/documents` (list), `DELETE /agents/{agent_id}/kb/documents/{document_id}`.
  - [ ] T5.2 Enforce Agent ownership/department scoping consistent with Story 2.1 (cross-tenant -> 404). Reuse auth/tenant middleware from Story 1.3.
  - [ ] T5.3 Wire router into `app/main.py` if not already registered by Story 2.1/2.2 (avoid duplicate registration).
- [ ] **T6 -- Frontend KB tab** (AC: #1, #3, #4, #8)
  - [ ] T6.1 Create the KB tab component under `frontend/src/routes/agent-builder/` (or the Agent detail tab container introduced by Story 2.2). Rendered as the "Knowledge Base" tab in the 6-tab detail nav (UX-DR16).
  - [ ] T6.2 File picker + drag/drop upload. Client-side validation: reject files > 20MB and unsupported extensions/MIME types BEFORE calling the API, with a clear inline error (AC4).
  - [ ] T6.3 Document list: each row shows filename, size, and a `StatusPill` (`components/ui/StatusPill.tsx`) mapping `processing`/`indexed`/`failed` (show `failure_reason` for failed). Empty state via `components/ui/EmptyState.tsx` (UX-DR23 pattern).
  - [ ] T6.4 Poll `GET .../kb/documents` (TanStack Query `refetchInterval`) while any document is `processing` so `Processing -> Indexed/Failed` updates live; stop polling when none are processing.
  - [ ] T6.5 Delete affordance with confirmation.
  - [ ] T6.6 Persistent banner/notice in the tab: "Upload policy / regulation / SOP documents only -- no real customer PII" (NFR-9, AC8).
  - [ ] T6.7 API client functions in a new `frontend/src/lib/` module (or extend `api.ts`) using `apiFetch`; multipart upload sends `Authorization` + `X-Tenant-Id` + `X-Department-Id` headers (do NOT force `Content-Type: application/json` for the multipart request -- let the browser set the boundary).
- [ ] **T7 -- Tests** (AC: all)
  - [ ] T7.1 Backend integration (`backend/tests/integration/`): upload happy path -> row `processing`; ingest job -> `indexed`; oversized/unsupported rejected (400); delete removes row + calls `rag.delete`; cross-tenant access -> 404.
  - [ ] T7.2 Backend unit: `StubMcpClient` raises `AuthorizationError` when `tenant_id`/`department_id` missing (AD-11); timeout path sets `Failed: Timeout`; audit entries contain metadata only, never document bytes (NFR-9).
  - [ ] T7.3 Frontend (Vitest): client-side 20MB + type rejection; status pill rendering for each state; polling stops when nothing is processing; PII banner present.
- [ ] **T8 -- Full suite GREEN + DoD evidence** (AC: all)
  - [ ] T8.1 `uv run pytest -v` (all green), `uv run ruff check app tests alembic` (clean), `uv run alembic upgrade head` (idempotent).
  - [ ] T8.2 Frontend: `npm run test` (Vitest green), lint clean.
  - [ ] T8.3 Record test evidence + production code references in the Dev Agent Record.

## Dev Notes

### Scope Boundaries -- CRITICAL

**Story 2.4 delivers KB document upload/list/delete + storage + the stub MCP client. Do NOT implement:**
- **The real MCP server** (indexing/embedding/`rag.search` backend) -- built by another team, out of scope (AD-3). This story ships the CLIENT stub only.
- **Runtime KB retrieval** (`kb_search(agent_id, query)`, `AgentProviderPort` exposure, `type: "kb.retrieval"` logging) -- that is **Story 2.5**. Story 2.4 only wires a `rag.search` *placeholder* through `McpClientPort` (AC9) to prove the call path; it does not build the retrieval feature.
- **Agent CRUD / the `agents` table / department scoping** -- **Story 2.1** (dependency, see below).
- **The Agent detail shell / 6-tab nav / Identity tab** -- **Story 2.2** (dependency, see below).
- **Tools, API Integrations, Model, Prompt tabs** -- Stories 2.3, 2.6, 2.7.
- Changes to `ports/mcp_client.py`, `ports/doc_intake.py`, `ports/audit.py` (owned by Story 1.4 -- consume as-is), `audit_postgres.py` (Story 1.5), `jobs.py` (Story 1.7).

### Dependencies (BLOCKERS -- verify before starting)

- **Story 2.1 (Agent CRUD, Identity & Department Scoping)** -- NOT YET IMPLEMENTED. `backend/app/modules/agent_builder/{models,routes,service}.py` are empty scaffolds at baseline. Story 2.4 needs: the `agents` table (with `department_id`, `owner_id`, RLS), the Agent record, and its ownership/scoping rules. The KB `department_id` is **derived from the Agent record**, never supplied by the client. If 2.1 is not merged, this story is blocked.
- **Story 2.2 (Agent List & Detail Shell with Identity Tab)** -- provides the `/agents/$id` detail view and the 6-tab nav (Identity, **Knowledge Base**, Tools, API Integrations, Prompt, Model) per UX-DR16. Story 2.4 mounts the KB tab content into this shell. If the tab container is not present, the KB tab must render standalone but should slot into 2.2's container once available.
- **Story 1.4** -- `McpClientPort` + `DocIntakePort` Protocols (present at `backend/app/core/ports/mcp_client.py`, `doc_intake.py`). Consume as-is.
- **Story 1.5** -- `PostgresAuditSink` / `audit.log()` (present at `backend/app/core/adapters/audit_postgres.py`).
- **Story 1.7** -- arq background job foundation (present at `backend/app/core/jobs.py`).

### Design Decisions

1. **Ingestion routes through `McpClientPort.call_tool`, not `DocIntakePort`.** epics.md L743 and the story brief both name `McpClientPort` explicitly with mandatory `tenant_id` + `department_id`. `DocIntakePort` (a higher-level KB-specific port) also exists from Story 1.4 and is a reasonable alternative, but to satisfy the AC verbatim and the AD-11 signature the KB service calls `McpClientPort.call_tool("rag.ingest"|"rag.delete"|"rag.search", ...)`. The stub adapter lives at `core/adapters/mcp_client.py` (the path reserved in structural-seed.md).
2. **`department_id` is derived from the Agent, never trusted from the client.** The upload endpoint takes `agent_id`; the service loads the Agent (Story 2.1) and passes the Agent's own `department_id` into every `McpClientPort` call. This is the concrete realization of AD-11's "matches the calling Agent's department."
3. **Two-phase upload (row first, ingest async).** The upload endpoint inserts a `processing` row and enqueues an arq job, returning immediately. This keeps the request off the 30s ingest deadline and lets the UI poll `Processing -> Indexed/Failed`. The 30s timeout (AC5) is enforced inside the job via `asyncio.timeout(30)`.
4. **`kb_documents` is mutable (unlike `audit_trail`).** Status transitions and deletes require `UPDATE`/`DELETE` grants. This is intentionally different from the append-only `audit_trail` (AD-4) -- KB docs are operational data, the audit of KB actions is the append-only record.
5. **Audit carries metadata only (NFR-9).** `kb.document.uploaded`/`kb.document.deleted` entries log `{agent_id, filename, size_bytes, status}` -- never document bytes or extracted text. Combined with the PII banner, this keeps banking-sensitive content out of the trail.
6. **`rag.search` placeholder (AC9) is a call-path smoke test, not the feature.** Story 2.4 may issue one `McpClientPort.call_tool("rag.search", ...)` through the stub to prove the scoped call path compiles and enforces AD-11; the returned passages are an empty placeholder. Real retrieval is Story 2.5.

### Architecture Compliance

- **AD-3 (VAIC is an MCP *client*; the MCP server is external and out of scope)**: Story 2.4 ships `StubMcpClient` implementing `McpClientPort`. The real indexing/embedding/`rag.search` server is built by the parallel team. VAIC never builds, hosts, or owns it. Open Question 5 (server-side department isolation) remains with that team -- documented in `divergence-5-mcp-server-department-isolation-whose-responsibility.md`.
- **AD-11 (client-side department scope on EVERY MCP call)**: Every `McpClientPort.call_tool` / `list_tools` call carries the Agent's `tenant_id` + `department_id`. The stub adapter raises `AuthorizationError` client-side if scope is missing or mismatched -- before any network step. VAIC never sends an unscoped MCP call. This is a client-side guard, NOT a substitute for the server's own enforcement (per divergence-5 / AD-11).
- **AD-10 (tenant context materialized in job payloads)**: The async ingest job re-sets `tenant_id` + `department_id` at worker entry -- the FastAPI-set ContextVar does not survive the arq worker boundary.
- **AD-2 (multi-tenant RLS)**: `kb_documents` carries `tenant_id NOT NULL`; RLS policy `tenant_id = current_setting('app.tenant_id')::uuid` (USING + WITH CHECK), FORCE enabled. Cross-tenant SQL returns empty; cross-tenant API returns 404 (mirrors Story 2.1).
- **AD-4 (single audit sink)**: KB upload/delete audit entries go through `PostgresAuditSink.log()` only.
- **NFR-9 (banking data sensitivity)**: KB limited to policy/regulation/SOP; UI banner enforces the policy socially; audit logs metadata only; demo data synthetic (no real PII).
- **AR-14 (consistency conventions)**: UUID v7 IDs, `timestamptz` timestamps, `snake_case` files, functions under 50 lines.
- **UX-DR16 (Agent detail 6-tab nav)**: KB tab is the 2nd tab (Identity, **Knowledge Base**, Tools, API Integrations, Prompt, Model).

### File Structure Changes

```
backend/
├── alembic/versions/
│   └── <rev>_create_kb_documents_table.py     # NEW -- kb_documents table + RLS
├── app/
│   ├── core/adapters/
│   │   └── mcp_client.py                       # NEW -- StubMcpClient (McpClientPort), AD-11 guard
│   ├── modules/agent_builder/
│   │   ├── models.py                           # UPDATED -- KbDocument model (+ Agent from 2.1)
│   │   ├── service.py                          # UPDATED -- KB upload/list/delete + ingest job
│   │   └── routes.py                           # UPDATED -- POST/GET/DELETE /agents/{id}/kb/documents
│   ├── core/jobs.py                            # (Story 1.7) -- register kb ingest job; do not restructure
│   └── main.py                                 # UPDATED only if router not already registered by 2.1/2.2
└── tests/
    ├── unit/test_mcp_client_stub.py            # NEW
    └── integration/test_kb_documents.py        # NEW

frontend/
├── src/
│   ├── routes/agent-builder/                   # KB tab component (slots into 2.2's detail shell)
│   │   └── KnowledgeBaseTab.tsx                # NEW
│   ├── lib/
│   │   └── kbApi.ts                            # NEW -- upload/list/delete via apiFetch (multipart)
│   └── hooks/
│       └── useKbDocuments.ts                   # NEW -- TanStack Query hook w/ polling
```

### Testing

- **Backend**: pytest, TDD (RED -> GREEN) as in Epic 1. Integration tests use the real Postgres test DB with RLS (mirror `tests/integration/test_audit_sink.py`). Unit tests for the stub adapter and timeout/PII-metadata logic.
- **Frontend**: Vitest + Testing Library (mirror `dashboard.test.tsx`, `EmptyState.test.tsx`). Mock `apiFetch`; assert client-side size/type rejection, status-pill states, polling behavior, and PII banner presence.
- **Key negative tests**: oversized (>20MB) rejected both client and server side; unsupported type rejected; `AuthorizationError` on missing/mismatched scope (AD-11); `Failed: Timeout` on >30s ingest; cross-tenant 404; audit entry never contains document bytes.

### Anti-Patterns to Avoid

1. **Do NOT build the MCP server.** Only the client stub. AD-3 is non-negotiable.
2. **Do NOT trust a client-supplied `department_id`.** Always derive it from the Agent record. AD-11's guarantee is that VAIC sends the *Agent's* scope.
3. **Do NOT send an unscoped MCP call.** Missing `tenant_id`/`department_id` must raise before any (stubbed) network step.
4. **Do NOT log document contents or extracted text into `audit_trail`.** Metadata only (NFR-9).
5. **Do NOT run ingestion synchronously on the request thread** -- it would block on the 30s deadline. Use the arq job (AD-10: re-set tenant context at worker entry).
6. **Do NOT force `Content-Type: application/json` on the multipart upload** -- let the browser set the multipart boundary; still send `Authorization`/`X-Tenant-Id`/`X-Department-Id`.
7. **Do NOT use `uuid.uuid4()`** for `id`/`document_id` -- AR-14 mandates UUID v7 (`uuid7()` from `app.core.ids`).
8. **Do NOT hard-delete leaving orphaned index entries** -- delete must call `rag.delete` through `McpClientPort` before/with removing the DB row.

### References

- [Source: epics.md#Story-2.4 L732-753] ACs verbatim
- [Source: epics.md#Story-2.1 L662-682] Agent CRUD, department scoping, cross-tenant 404 (dependency)
- [Source: epics.md#Story-2.2 L684-699] Agent detail 6-tab nav / UX-DR16 (dependency)
- [Source: epics.md#Story-2.5 L755-771] Runtime KB retrieval (downstream -- explicitly out of scope here)
- [Source: backend/app/core/ports/mcp_client.py] `McpClientPort.call_tool` / `list_tools` -- mandatory keyword-only `tenant_id` + `department_id`; raises `AuthorizationError` on mismatch, `UpstreamError` on server failure; `ToolResult{tool_name, output, success, error}`
- [Source: backend/app/core/ports/doc_intake.py] `DocIntakePort` (alternative port; not used -- epics names McpClientPort)
- [Source: backend/app/core/ports/audit.py + _bmad-output/implementation-artifacts/1-5-audit-sink-append-only-trail.md] `audit.log()` sink (AD-4)
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-3] MCP is external-tool protocol; server out of scope
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-11] Client-side department scope on every MCP call
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-10] Tenant context materialized in job payloads (worker boundary)
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-2] Multi-tenant RLS isolation
- [Source: ARCHITECTURE-SPINE/divergence-5-mcp-server-department-isolation-whose-responsibility.md] Client-side guard vs server-side enforcement (Open Question 5)
- [Source: ARCHITECTURE-SPINE/structural-seed.md] `core/adapters/mcp_client.py`, `modules/agent_builder/*`, `doc_intake.py` paths
- [Source: ARCHITECTURE-SPINE/stack.md] `mcp` Python SDK v1.x, arq 0.26+, FastAPI 0.139.x, React 19, TanStack Query
- [Source: prd-VAIC-2026-07-17/prd/8-constraints-guardrails-nfrs.md#8.1] NFR-9: KB limited to policy/SOP, no real customer PII
- [Source: prd-VAIC-2026-07-17/prd/4-features.md#FR-21] Per-step audit logging
- [Source: _bmad-output/implementation-artifacts/1-4-core-ports-api-error-envelope.md] Port definitions, error envelope
- [Source: _bmad-output/implementation-artifacts/1-7-arq-background-job-foundation.md] arq job foundation
- [Source: frontend/src/lib/api.ts, frontend/src/components/ui/{StatusPill,EmptyState}.tsx] Frontend fetch wrapper + primitives to reuse

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-07-17: Story 2.4 spec authored. Status: ready-for-dev.
