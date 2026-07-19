# Sub-project A — Shared Tools Library + Shared KB Store (Domain Re-platform) — Design

> Part of the Platform IA/architecture redesign. This is **the spine**: it moves Tools and
> Knowledge-Base documents from *agent-owned aggregate children* to *tenant-wide shared resources*
> referenced by agents, with a document permission model. Later sub-projects (B Agents-slim,
> C Tools UI polish, D Database section, E Chat, F Apps, G Settings) build on this.

**Date:** 2026-07-18
**Branch:** `rebuild`
**Status:** Design approved (pending written-spec review)

---

## 1. Goal

One sentence: **Tools and KB documents become tenant-wide shared resources; an agent gains a
capability by *referencing* a tool (M2M) and gains data scope by *being granted* specific KB
documents (M2M), with per-document user-level access control — replacing today's agent-owned
CASCADE-child model.** Ship it behind a new 6-section sidebar so the change is visible and testable.

## 2. Current state (what we are replacing)

- `backend/app/modules/agent_builder/models.py` — `Agent` is the aggregate root. `Tool.agent_id`,
  `KbDocument.agent_id`, `ApiIntegration.agent_id` are all `ON DELETE CASCADE` children of **one**
  agent. No sharing, no M2M.
- `Tool` today can carry `embedded_python` (sandbox), route to MCP, and reference an
  `ApiIntegration` for auth headers.
- KB retrieval is **automatic** in `AgentExecutor`: any agent that owns docs gets RAG retrieval,
  scope derived from the `Agent` record (`kb_retrieval.py`).
- RAG is already **external via MCP** (`rag.ingest` / `rag.delete` / `rag.search`), currently a
  stub adapter (`core/adapters/mcp_client_stub.py`); the real `core/adapters/mcp_client.py` does
  not exist.
- Frontend: Tools & KB exist **only** as tabs inside a single agent
  (`frontend/src/components/agents/tabs/ToolsTab.tsx`, `KnowledgeBaseTab.tsx`). No standalone
  surfaces. Nav driven by `frontend/src/components/Sidebar.tsx` `NAV_ITEMS`.

## 3. Decisions (locked with the user)

| # | Decision |
|---|---|
| D1 | Sharing boundary = **tenant-wide library + per-resource ACL**. Department becomes an optional tag/filter, not an access boundary. |
| D2 | KB document user-access = **owner + explicit user grants with role** (`viewer` / `manager`). |
| D3 | KB consumption = **two gates**: an agent gets KB access only if it (a) references the `rag` tool AND (b) has specific docs granted. `rag.search` at runtime is scoped to exactly that agent's granted docs. |
| D4 | Tools = **built-in system-default catalog only**: `rag`, `gmail`, `calendar`, seeded per tenant. **No user-created custom tools** in this scope (no `embedded_python` / MCP-custom / integration authoring). Execution of `gmail` / `calendar` is **stubbed** (like RAG's MCP stub); real connector execution is deferred. |
| D5 | Every tool definition carries a required **`description`** (LLM- and human-facing) and **`params_schema`** (JSONB — the call parameters, e.g. Gmail `{to, subject, body}`). |
| D6 | Migration = **greenfield reset + reseed demo** (rebuild branch, only demo data). |
| D7 | Scope of A includes **the new 6-section sidebar** + two functional sections (Tools, Database→KB) so the change is visible; Chat/Apps/Settings are placeholders, Agents keeps reference-picker tabs until B. |
| D8 | Database→KB UI in A is **full**: upload + list + grants management (owner adds viewer/manager). |

## 4. Target domain model (backend)

All tables tenant-scoped via Postgres RLS (`tenant_id = current_setting('app.tenant_id')::uuid`,
ENABLE + FORCE), IDs uuid7, following existing patterns. Intra-tenant user ACL (owner/grants) is
enforced in the **service layer**, not RLS (RLS only isolates tenants).

### 4.1 `tools` (repurposed — tenant-wide catalog)

Drop `agent_id`, `embedded_python`, `integration_id`, `header`.

| column | type | note |
|---|---|---|
| `id` | uuid7 PK | |
| `tenant_id` | uuid FK tenants CASCADE | RLS key |
| `tool_type` | text, CHECK in (`rag`,`gmail`,`calendar`) | seeded catalog |
| `display_name` | text | |
| `description` | text NOT NULL | shown to LLM + humans (D5) |
| `params_schema` | JSONB NOT NULL | call parameters (D5) |
| `output_schema` | JSONB | may be `{}` |
| `config` | JSONB | non-secret defaults (e.g. `calendar_id`) |
| `credential_ref` | text nullable | encrypted via `core/crypto.py`; unused while stubbed |
| `created_at` / `updated_at` | timestamptz | |

Seeded per tenant at bootstrap (3 rows). No create/delete route in A (read-mostly).

### 4.2 `agent_tools` (M2M: agent references tool)

| column | type | note |
|---|---|---|
| `agent_id` | uuid FK agents CASCADE | |
| `tool_id` | uuid FK tools CASCADE | |
| `tenant_id` | uuid FK tenants CASCADE | RLS key |
| PK | (`agent_id`, `tool_id`) | |

### 4.3 `kb_documents` (repurposed — tenant-wide store)

Drop `agent_id`. Add `owner_id`.

| column | type | note |
|---|---|---|
| `id` | uuid7 PK | |
| `tenant_id` | uuid FK tenants CASCADE | RLS key |
| `owner_id` | uuid FK users RESTRICT | uploader = implicit manager |
| `display_name` | text | filename/title |
| `external_document_id` | text | id in the external RAG/MCP service |
| `chunk_count` | int | |
| `status` | text | `pending`/`ready`/`failed` (ingest lifecycle) |
| `department_id` | uuid FK departments nullable | optional tag (D1) |
| `created_at` / `updated_at` | timestamptz | |

Hard delete allowed (matches today's `kb_documents`); delete also calls `rag.delete`.

### 4.4 `kb_document_grants` (user-ACL, D2)

| column | type | note |
|---|---|---|
| `document_id` | uuid FK kb_documents CASCADE | |
| `user_id` | uuid FK users CASCADE | |
| `role` | text CHECK in (`viewer`,`manager`) | |
| `tenant_id` | uuid FK tenants CASCADE | RLS key |
| PK | (`document_id`, `user_id`) | |

Access rules (service layer):
- **Owner** is always effective `manager` (no row needed).
- `viewer` → can read the doc and tick it into an agent they can edit.
- `manager` → viewer + can add/remove grants + delete the doc.

### 4.5 `agent_kb_documents` (M2M: agent granted a doc, D3)

| column | type | note |
|---|---|---|
| `agent_id` | uuid FK agents CASCADE | |
| `document_id` | uuid FK kb_documents CASCADE | |
| `tenant_id` | uuid FK tenants CASCADE | RLS key |
| PK | (`agent_id`, `document_id`) | |

**Invariant:** a row may only be created by a user who has `viewer`+ on `document_id` **and** can
edit `agent_id`. Enforced in the service layer.

## 5. Runtime behavior changes

- **Tool resolution:** `AgentExecutor` resolves an agent's tools via `agent_tools` join, not
  `Tool.agent_id`.
- **KB retrieval (two gates, D3):** in `agent_executor.py` / `kb_retrieval.py`:
  1. If the agent does **not** reference the `rag` tool → no KB retrieval.
  2. Else gather `external_document_id`s from `agent_kb_documents` for this agent. If empty → no
     retrieval.
  3. Call `McpClientPort.call_tool("rag.search", {query, document_ids:[...], tenant_id,
     department_id})` scoped to exactly those docs. Scope is derived from `agent_kb_documents`
     (never caller-supplied).
- **gmail / calendar execution:** routed through a stub (returns a deterministic stub result,
  mirroring the RAG MCP stub). Tool *definition* and *reference* are real; *execution* is deferred.

## 6. API surface

Envelope `{data, error, meta}` as today. All under existing auth/tenant middleware.

**Tools (tenant-wide, read-mostly in A):**
- `GET /tools` — list the catalog (3 defaults).
- `GET /tools/{tool_id}` — detail (`description`, `params_schema`, `config`).

**Agent → tool references:**
- `GET /agents/{agent_id}/tools` — referenced tools.
- `POST /agents/{agent_id}/tools` `{tool_id}` — attach reference.
- `DELETE /agents/{agent_id}/tools/{tool_id}` — detach.

**KB documents (tenant-wide store):**
- `POST /kb/documents` (multipart) — upload; owner = caller; enqueue `rag.ingest`.
- `GET /kb/documents` — docs the caller can access (owned or granted).
- `GET /kb/documents/{doc_id}` — detail (403 if no access).
- `DELETE /kb/documents/{doc_id}` — manager/owner only; call `rag.delete`.
- `GET /kb/documents/{doc_id}/grants` — list grants (manager/owner only).
- `POST /kb/documents/{doc_id}/grants` `{user_id, role}` — add/update grant (manager/owner only).
- `DELETE /kb/documents/{doc_id}/grants/{user_id}` — revoke (manager/owner only).

**Agent → KB doc grants (tick):**
- `GET /agents/{agent_id}/kb-documents` — ticked docs.
- `POST /agents/{agent_id}/kb-documents` `{document_id}` — tick (requires viewer+ on doc AND edit
  on agent).
- `DELETE /agents/{agent_id}/kb-documents/{document_id}` — untick.

Old nested authoring routes (`POST /agents/{id}/tools`, upload `/agents/{id}/kb/documents`) are
removed; their function moves to the tenant-wide surfaces + reference toggles above.

## 7. Migration & seed (D6)

- New Alembic migration(s): create `agent_tools`, `kb_document_grants`, `agent_kb_documents`;
  alter `tools` (drop `agent_id`/`embedded_python`/`integration_id`/`header`, add
  `description`/`params_schema`/`config`/`credential_ref`, add `tool_type` CHECK); alter
  `kb_documents` (drop `agent_id`, add `owner_id`); RLS policies on all new tables.
- Update demo bootstrap (`backend/scripts/demo_agent_specs.py`,
  `bootstrap_demo_agents_workflow.py`): seed the 3 default tools per tenant, seed a couple of KB
  documents with an owner, wire the 3 demo agents to reference tools + grant docs in the new shape.

## 8. Frontend scope (D7, D8)

**New sidebar** (`Sidebar.tsx` `NAV_ITEMS` rewrite) — 6 primary sections:

| Section | Route | In A |
|---|---|---|
| Chat | `/chat` | `ComingSoon` placeholder (→ E) |
| Agents | `/agents` | existing list + detail; Tools tab → **select from library**, KB tab → **tick docs I can access** (full slim → B) |
| Apps | `/apps` | `ComingSoon` placeholder (→ F) |
| Tools | `/tools` | **functional**: list 3 default tools; detail shows `description` + `params` (read-mostly) |
| Database | `/database` | **functional (KB half)**: `Database → Knowledge Base` — upload, list, per-doc grants UI. Mini-app-DB half = placeholder (→ D) |
| Settings | `/settings` | mock placeholder (→ G) |

Workflows and Audit (existing, real) are **retained** as secondary sidebar entries beside the 6
primary sections (resolved with the user: they stay; only the described areas change). Final IA
polish of that grouping can happen in a later sub-project.

**Reused infra:** react-router v7 inline routes in `App.tsx`, TanStack Query hooks in `src/hooks/`,
API clients in `src/lib/*Api.ts`, in-house `ui/` design-token components. New: `toolsApi` (tenant),
`kbApi` (tenant store + grants), hooks `useTools`, `useKbDocuments`, `useKbGrants`,
`useAgentToolRefs`, `useAgentKbDocs`; components under `components/tools/` and `components/database/`.

## 9. Module boundary (AD-1)

Tools + KB stay inside `agent_builder` for now (same module as `Agent`), so no cross-module ORM
import is introduced — the shared tables live beside `Agent`. If a future sub-project extracts a
standalone `tools` / `knowledge` module, cross-access must go through `service.py` per AD-1. (Not
done in A to keep the change focused.)

## 10. Out of scope for A

Prompt versioning (B), Agents-slim final layout (B), custom/authored tools + real Gmail/Calendar
execution (later), Chat (E), Apps viewer/editor (F), mini-app database management (D), Settings
functionality (G), the real MCP RAG adapter (still stub).

## 11. Open questions

- **OQ-1 (RESOLVED)** — Workflows and Audit are shipped features and **stay**; the user's 6-section
  description covers only the areas being changed. Retained as secondary sidebar entries beside the
  6 primary sections; final IA grouping polish deferred.
- **OQ-2** — Do `gmail` / `calendar` tools need per-tenant credential capture in the Tools UI now
  (even though execution is stubbed), or is credential config deferred with execution? Default:
  deferred.
- **OQ-3** — Should uploading a KB document be restricted by role (e.g. only `builder`s), or open
  to any tenant user? Default: any authenticated tenant user; the uploader becomes owner.
