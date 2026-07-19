# Mini-Apps list→detail + unified Database page — Design

**Date:** 2026-07-18
**Status:** Approved (design), ready for implementation plan
**Author:** (VAIC team)

## Problem

Two related gaps in the current UI/back end:

1. **Mini-Apps landing** — `/mini-apps` mixes a card list *and* an inline create
   form on one screen. We want a clean "list first, then detail" flow: sidebar →
   full list of mini-apps (demo shows all) → click a card → detail/host page.
2. **No central Database surface** — a mini-app's data model (`entity_schema`) is
   embedded per-app; there is no reusable, selectable "database". The sidebar's
   `Knowledge Base` item is a "Coming soon" placeholder even though a tenant-wide
   KB back end already exists. We want a single **Database** page in the sidebar
   with two parts: **Knowledge Base (for agents)** and **Mini-App Databases**, and
   mini-apps should **reference** a database via a dropdown.

## Decisions (locked with user)

- **Scope:** real front end + back end (not mock-only).
- **Sidebar:** replace `Knowledge Base` nav item with `Database`; KB becomes the
  first tab inside the Database page.
- **Mini-app ↔ DB reference:** mini-app picks an existing database from a
  **dropdown** at create time.
- **"Mini-App Database" data model:** a **reusable schema template**. New table
  `mini_app_databases(name, description, entity_schema)`. Binding a database to a
  mini-app **copies** its `entity_schema` into the app and records `database_id`
  for traceability. Row data stays per-app (`mini_app_rows.app_id` unchanged) — the
  build/runtime pipeline is untouched.
- **Mini-App Database tab scope:** manage schema (list/create/edit databases) +
  **read-only** rows viewer of apps using that database.

## Global Constraints

- Back end: FastAPI, Python 3.13, hexagonal modular monolith. Routes are thin
  adapters returning the `{"data", "error", "meta"}` envelope via `_ok(...)`.
- All new tenant-scoped tables get RLS (`ENABLE` + `FORCE`,
  `tenant_id = current_setting('app.tenant_id')::uuid`) and `vaic_app` grants,
  mirroring `c4f1a9d3e7b2_create_mini_apps_rls.py`.
- Alembic head is `f7a8b9c0d1e2` — the new migration's `down_revision` is
  `"f7a8b9c0d1e2"`.
- Front end: Vite + React 19 + TS, TanStack Query, `components/ui` primitives,
  branch order error → loading → empty → data.
- **Per project working preferences: NO automated tests, and do NOT run
  typecheck/lint/build/format** unless explicitly requested. Verification is
  manual by the user.
- Files kept focused (< ~200 LOC); kebab-case, descriptive names.

## Architecture

### Back end — new "Mini-App Database" entity (reusable schema template)

**Table `mini_app_databases`:**

| column | type | notes |
|---|---|---|
| id | UUID PK | `uuid7()` default |
| tenant_id | UUID FK tenants (CASCADE) | RLS key |
| owner_id | UUID FK users (RESTRICT) | uploader/creator |
| name | String(255) NOT NULL | |
| description | Text NOT NULL default '' | |
| entity_schema | JSONB NOT NULL | validated by `validate_entity_schema` |
| created_at / updated_at | TIMESTAMPTZ default now() | |

Unique `(tenant_id, name)`. RLS tenant-isolation + full `vaic_app` CRUD grants.

**`mini_apps.database_id`** — new nullable column,
`ForeignKey("mini_app_databases.id", ondelete="SET NULL")`. Added in the same
migration. `serialize_app` gains `"database_id"`.

**Row data unchanged** — `mini_app_rows` still keyed by `app_id`. A database only
provides the *schema*; at bind time we copy `entity_schema` into the app.

**New module files** (`backend/app/modules/mini_app/`):
- `database_models.py` — `MiniAppDatabase` ORM model.
- `database_service.py` — list/get/create/update/delete + `list_database_rows`
  (aggregates `mini_app_rows` for apps where `database_id = {id}`) + serializers.
- `database_routes.py` — `mini_app_databases_router` (prefix `/mini-app-databases`).

**Endpoints:**
- `GET  /mini-app-databases` → list tenant databases.
- `POST /mini-app-databases` `{name, description?, entity_schema}` → create
  (schema validated; 422 on invalid).
- `GET  /mini-app-databases/{id}` → one.
- `PATCH /mini-app-databases/{id}` `{name?, description?, entity_schema?}` → update.
- `DELETE /mini-app-databases/{id}` → delete (sets referencing apps' `database_id`
  to NULL via FK).
- `GET  /mini-app-databases/{id}/rows` → read-only rows across apps referencing
  this DB: `[{app_id, row_id, data, created_at, updated_at}]`.

**Mini-app create flow change** (`routes.py` `CreateMiniAppRequest`,
`service.create_app_from_schema`): add optional `database_id`. Precedence:
1. `database_id` present → load database, use its `entity_schema` (copy), set
   `mini_apps.database_id`. `ui_spec` defaults to `{}` (validated → default UiSpec).
2. else `entity_schema` present → existing caller-supplied path.
3. else `description` + `expected_output` → existing LLM emission path.

`create_app_from_schema` gains a `database_id: uuid.UUID | None = None` param
threaded into `ProvisioningPlan` → `plan_to_model` → `MiniApp.database_id`.

**Wiring:** `main.py` includes `mini_app_databases_router`. Model imported so
Alembic autogenerate/metadata sees it (import in module `__init__` or migration is
explicit regardless).

### Front end — Database page + dropdown reference

**Sidebar** (`components/Sidebar.tsx`): replace the `Knowledge Base` item
(`/knowledge-base`, `BookOpen`) with `Database` (`/database`, lucide `Database`
icon). Update `navigationCommands.ts` `NAV_TARGETS` + `NAV_ICON_BY_ID`
(`knowledge-base` → `database`).

**Route** (`App.tsx`): `/database` → `DatabasePage`. Replace the
`/knowledge-base` placeholder route with a redirect to `/database`.

**`routes/database.tsx` — `DatabasePage`:** a two-tab shell (local `useState`
tab state; simple in-page tabs, no router nesting needed):
- **Tab "Knowledge Base"** → `components/database/KnowledgeBaseSection.tsx`:
  tenant-wide KB list + upload + delete using the existing `/kb/documents`
  endpoints. Reuses the visual pattern of the agent KB tab (Table, `KbStatusPill`,
  20MB/type gate, `ConfirmDialog`) but **not** agent-scoped.
- **Tab "Mini-App Databases"** → `components/database/MiniAppDatabaseSection.tsx`:
  list of databases (Table/cards) → create/edit (name, description, schema field
  editor) → per-database read-only rows viewer.

**New front-end modules:**
- `lib/miniAppDatabasesApi.ts` — types + `listDatabases/getDatabase/
  createDatabase/updateDatabase/deleteDatabase/listDatabaseRows`.
- `hooks/useMiniAppDatabases.ts` — query list + single; mutations
  (create/update/delete) invalidating `["mini-app-databases"]`.
- `lib/globalKbApi.ts` + `hooks/useGlobalKb.ts` — tenant-wide KB list/upload/delete
  against `/kb/documents` (distinct from agent-scoped `kbApi.ts`; the tenant-wide
  `serialize_document` has **no `agent_id`** but adds `effective_role`).
- `components/database/SchemaFieldEditor.tsx` — edit an `entity_schema`'s field
  list (name, type, required, label; enum options when type=enum). Emits a
  `{fields, primary_display?}` object matching `EntitySchema`.

**Mini-apps list page** (`routes/mini-apps.tsx`): landing becomes a clean grid of
**all** apps. The inline create form moves into a **modal** (`ui/Modal` or a simple
dialog) opened by a "Create Mini-App" button. The modal adds a **Database
dropdown** (options from `listDatabases`); selecting a database sends `database_id`
(server copies schema). The description/expected-output fields remain as the
fallback path when no database is selected.

**Mini-app detail page** (`routes/mini-app-host.tsx`): add a small
"**Database: `<name>`**" line (from `database_id`) linking to `/database` when set;
read-only. Requires `getMiniApp` to expose `database_id` (already added to
`serialize_app`) and a lookup of the database name (fetch single database, or
include name in a lightweight join — simplest: fetch `listDatabases` and map id→name
client-side).

## Data flow

1. User opens **Database → Mini-App Databases**, creates a database "Loan
   Applications" with fields → `POST /mini-app-databases`.
2. User opens **Mini-Apps**, clicks **Create Mini-App**, picks "Loan Applications"
   from the Database dropdown → `POST /mini-apps {name, database_id}` → server
   copies that schema into the new app, records `database_id`, enqueues build.
3. App builds; user opens it from the list → detail/host iframe. Detail shows
   "Database: Loan Applications".
4. Rows the app writes (`mini_app_rows.app_id`) are visible read-only under that
   database's rows viewer in the Database page.

## Error handling

- Schema validation failures → 422 with the existing `SchemaValidationError.reason`.
- Duplicate database name in tenant → surfaced as the API error message in a toast.
- Front end follows error → loading → empty → data; mutations toast on success/error.

## Out of scope (YAGNI)

- Migrating `mini_app_rows` to key on `database_id` (shared data store) — explicitly
  rejected in favor of the schema-template model.
- Editing/creating data rows from the Database page (read-only viewer only).
- Re-binding an existing app to a different database after creation.
- KB grants management UI on the global page (upload/list/delete only for now).

## Open questions

- None outstanding. (Re-binding an app's database post-create is deferred, not
  blocking.)
