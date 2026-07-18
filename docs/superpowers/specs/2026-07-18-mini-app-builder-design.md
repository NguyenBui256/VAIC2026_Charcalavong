# Mini-App Builder — Demo Vertical Slice + Sandbox (Epic 4)

- **Date:** 2026-07-18
- **Epic:** 4 — Mini-App Builder & Visibility Tier Enforcement
- **Slice:** Stories 4-1, 4-2, 4-3, 4-4, 4-5, 4-7 + sandbox layer
- **Deferred to Epic 5 pairing:** 4-6 (App Event emission), 4-8 (live event stream)
- **PRD:** §4.3 FR-12..FR-16 (FR-17 deferred)
- **Spine ADs honored:** AD-5 (RLS), AD-8 (pure provisioner), Divergence-3 (single writer + CAS), Divergence-7 (provisioner purity vs side effects)

## 1. Goal & Success Criteria

From a **description + expected output**, a builder generates a live **Mini-App**: an LLM emits an entity schema + UI spec, the platform validates and provisions a JSONB namespace, auto-generates visibility-gated CRUD endpoints, compiles a per-app UI bundle in an isolated build sandbox, and serves it inside a sandboxed iframe. Delivers rubric **SM-5** (a live Mini-App with real storage, CRUD, and an auth-gated UI a judge can open and edit).

**Success (testable, from PRD consequences):**
- A valid emission provisions a writeable namespace with a unique `app_id`; every row carries the four access fields, none null (FR-13).
- CRUD endpoints exist and enforce tier: `Private` rejects non-whitelisted (403), `Need-Auth` rejects out-of-department (403), anonymous → 401, `Public` allows any same-tenant user (FR-14, FR-16).
- A generated UI is reachable and enforces the same rules server-side (no client-only gating) (FR-15).
- Invalid emissions are rejected and audited; valid emissions are audited with originating agent + prompt (FR-12).
- A generated Mini-App cannot affect the main platform backend (sandbox requirement).

## 2. Key Decisions (locked with user)

1. **Scope:** demo vertical slice (4-1,2,3,4,5,7) + sandbox. App Event emission (4-6) and live stream (4-8) deferred; design leaves a single `_emit_row_change()` seam.
2. **Creation path:** LLM-generate `{entity_schema, ui_spec}` from a description + expected output, validate, provision. Core `service.provision()` reusable by the orchestrator later.
3. **Generated UI:** true per-app `.tsx` codegen + compiled per-app bundle, **served as a separate bundle in a sandboxed iframe — NOT merged into the platform SPA** (required for the sandbox to hold). Rebuild latency accepted.
4. **Visibility model:** app-level `visibility_tier` + `whitelist_user_ids` on the `mini_apps` record; rows inherit via an RLS policy that joins to the parent app.
5. **Schema scope:** field types `string, longtext, integer, number, boolean, date, enum`; validations `required, min, max, minLength, maxLength, pattern, options`. Anything outside the set is rejected.
6. **Sandbox tier:** worker-isolated build (AST allowlist + arq resource-capped subprocess) + iframe runtime + per-app scoped JWT + build-status state machine + rebuild/deprovision lifecycle. No Docker-per-app.

## 3. Backend Architecture

Hexagonal, matching existing `agent_builder` / `orchestrator` module conventions.

```
backend/app/modules/mini_app/
  models.py            # MiniApp, MiniAppRow ORM + enums (VisibilityTier, BuildStatus)
  schemas.py           # Pydantic DTOs: EntitySchema, UiSpec, request/response models
  schema_validation.py # validate emitted schema against the meta-schema (Story 4-1)
  emission.py          # LLM-generate {entity_schema, ui_spec} from a description (ModelPort)
  provisioner.py       # PURE fn: (tenant,dept,owner,schema,ui_spec,visibility) -> ProvisioningPlan (AD-8)
  codegen.py           # PURE: EntitySchema + UiSpec -> generated .tsx source string
  lifecycle.py         # applies a ProvisioningPlan: insert row, enqueue build job (side effects)
  service.py           # SOLE WRITER: create_app, list/get apps, row CRUD (CAS), update_row
  crud_engine.py       # generic row CRUD parameterized by app_id + entity_schema
  visibility.py        # tier resolution + scoped-token minting/verification
  routes.py            # /mini-apps (catalog CRUD) + /apps/{app_id}/rows/* (generic CRUD)
```

**Ports:**
- Reuse `ModelPort` (LLM emission), `AuditPort` (audit trail).
- **New `BuildPort`** (`core/ports/build.py`): `build(app_id, tsx_source, out_dir, *, timeout_s, memory_mb) -> BuildResult`. Adapter = arq-worker-driven resource-capped `esbuild` step (`core/adapters/esbuild_build.py`), mirroring the `SandboxPort` philosophy (impure work behind a port).

**AD-8 compliance:** `provisioner.py` and `codegen.py` are pure (no I/O, deterministic). All side effects (DB insert, build enqueue, file writes) live in `lifecycle.py` and the build adapter.

**Divergence-3 compliance:** `mini_app.service` is the sole writer to `mini_app_rows`. Any agent/orchestrator row mutation calls `service.update_row(...)`, never the HTTP endpoint and never raw ORM. Every update is CAS on `updated_at` → 409 on mismatch.

## 4. Data Model

Two tables, RLS on both. New Alembic migration `create_mini_apps_rls`.

**`mini_apps`** (one row per app):

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| tenant_id | uuid | RLS scope |
| department_id | uuid | |
| owner_id | uuid | |
| name | text | |
| slug | text | unique per tenant; validated `^[a-z0-9-]{1,64}$` (used in paths — no traversal) |
| description | text | |
| entity_schema | jsonb | validated against meta-schema |
| ui_spec | jsonb | |
| visibility_tier | enum | `public` / `need_auth` / `private` |
| whitelist_user_ids | uuid[] | used when tier = private |
| build_status | enum | `pending` / `building` / `ready` / `failed` |
| build_error | text null | populated on failed build |
| bundle_path | text null | dir of the compiled per-app bundle |
| created_by_agent_id | uuid null | audit provenance (FR-12) |
| created_at, updated_at | timestamptz | |

**`mini_app_rows`** (all apps share this table):

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| app_id | uuid FK → mini_apps | ON DELETE CASCADE |
| tenant_id | uuid **NOT NULL** | four access fields, none null (FR-13) |
| department_id | uuid **NOT NULL** | |
| owner_id | uuid **NOT NULL** | |
| data | jsonb **NOT NULL** | schema-defined fields |
| created_at, updated_at | timestamptz | CAS target |

**Two-layer enforcement (revised after codebase check):** the platform only propagates **`app.tenant_id`** as a DB session GUC (`core/tenant_context.py`); `user_id`/`department_id`/`role` live on `request.state`/`Principal`, *not* as GUCs. Pushing tier logic into an RLS policy would require adding `app.user_id`/`app.department_id` GUCs to the core auth/session path — a HIGH-impact edit to a shared boundary (`get_tenant_session`, `tenant_context`, arq `jobs.py`) touching every module. We avoid that:

- **DB layer (RLS, AD-5):** `mini_app_rows` gets the *same* tenant-isolation policy as every other table — `tenant_id = current_setting('app.tenant_id')::uuid`, ENABLE + FORCE. This is the hard cross-tenant boundary.
- **App layer (`visibility.py`):** the visibility tier (`public`/`need_auth`/`private` + whitelist) is enforced in the service/crud path using the caller's `Principal(user_id, department_id, role)` (already on `request.state`). This mirrors how role checks (`builder`/`admin`) are *already* enforced at the app layer in existing services — authorization, not tenant isolation, lives in the service.
  - `public` → any user in the same tenant (RLS already guarantees tenant).
  - `need_auth` → `principal.department_id == app.department_id`, else 403 (401 if anonymous — the auth middleware already blocks anon on protected paths).
  - `private` → `principal.user_id == app.owner_id` OR `principal.user_id in app.whitelist_user_ids`, else 403.

Defense in depth: tenant isolation is guaranteed at the DB even if an app-layer check is bypassed; the tier check produces the exact 401/403 distinctions FR-16 requires.

## 5. Schema Meta-Schema (Story 4-1)

`entity_schema = { fields: [ {name, type, label?, validations?} ], primary_display? }`

- **Allowed types:** `string`, `longtext`, `integer`, `number`, `boolean`, `date`, `enum`.
- **Allowed validations:** `required` (bool), `min`/`max` (numeric fields), `minLength`/`maxLength` (string/longtext), `pattern` (regex, string), `options` (list, required for `enum`).
- `field.name` must be a safe identifier (`^[a-z][a-z0-9_]{0,63}$`) — used as a JSONB key and a form field id.
- Validation rejects: unknown type, unknown validation key, validation/type mismatch (e.g. `min` on a boolean), missing `options` on enum, duplicate field names, empty field list.
- Invalid emission → HTTP 422 + audit `mini_app.schema_rejected` (with reason). Valid emission → audit `mini_app.schema_emitted` (agent id + prompt).

`ui_spec = { layout: 'table'|'cards', components: [...derived from fields...], primary_actions: ['create'|'edit'|'delete'] }`. Drives widget selection: text input / textarea / number / checkbox / date picker / select.

## 6. Creation & Provisioning Flow (FR-12 → 13 → 14 → 15)

1. `POST /mini-apps` `{ name, description, expected_output, visibility_tier, whitelist_user_ids? }` — role `builder`.
2. `emission.py` → `ModelPort` returns `{entity_schema, ui_spec}` (prompt + agent id retained for provenance).
3. `schema_validation.py` validates. Invalid → 422 + audit `mini_app.schema_rejected` (reason). Valid → audit `mini_app.schema_emitted` (agent id + prompt). Audit fires *after* the validation verdict, matching §5.
4. `provisioner.py` (pure) → `ProvisioningPlan { mini_app_row, tsx_source, ui_route }`.
5. `lifecycle.py` inserts the `mini_apps` row (`build_status = pending`), enqueues an arq build job. Response returns the `app_id` immediately; **row CRUD is live at once** and does not wait on the UI build.
6. Build worker (§7) validates `tsx_source` via AST allowlist → resource-capped `esbuild` → writes bundle to `bundle_path` → sets `build_status = ready | failed` (+ `build_error`).

## 7. Sandbox Management (user requirement)

Three planes; the generated app is untrusted at the build and browser-runtime planes only.

- **Data plane:** declarative-only backend → no per-app server code → RLS *is* the sandbox. A Mini-App cannot reach platform tables (no code path, tenant-scoped single table).
- **Build plane:** `codegen.py` output must pass an **AST allowlist** before any build:
  - imports limited to a fixed vendored set (React + the app runtime SDK only);
  - forbid `eval`, `Function`, `window.parent/top/opener`, `document.cookie`, dynamic `import()`, and network calls to anything but the app's own scoped API base;
  - reject on any violation → `build_status = failed`, `build_error` set, audited.
  - Build runs in the **arq worker** as a resource-capped subprocess (CPU / memory / wall-timeout, mirroring `SubprocessSandbox` limits) via `esbuild`, producing a **separate per-app bundle**. A broken/hostile app can only fail its own build; it cannot take down the platform API process or the platform SPA build.
- **Runtime plane:** bundle served as static assets at `/mini-app-runtime/{app_id}/`; the catalog host page embeds it in `<iframe sandbox="allow-scripts allow-forms">`. The iframe is handed a **per-app scoped JWT** (audience = that `app_id`; authorizes only `/apps/{app_id}/rows/*`) — never the platform session token. Cross-document isolation + the sandbox attribute prevent the generated code from reading the real session or calling privileged platform APIs.
- **Lifecycle management:** `build_status` state machine (`pending → building → ready | failed`); `POST /mini-apps/{id}/rebuild`; `DELETE /mini-apps/{id}` deprovisions (remove bundle dir + cascade `mini_app_rows`).

## 8. CRUD Endpoints (Story 4-4)

Single generic router, parameterized by `app_id` (no per-app route mounting):
- `POST   /apps/{app_id}/rows` — validate `data` against `entity_schema`, inject four access fields from session, insert. → 201.
- `GET    /apps/{app_id}/rows` — list (paginated, RLS-scoped).
- `GET    /apps/{app_id}/rows/{row_id}` — read (RLS-scoped).
- `PATCH  /apps/{app_id}/rows/{row_id}` — CAS on `updated_at`; validate patched `data`. → 200 / 409.
- `DELETE /apps/{app_id}/rows/{row_id}` — RLS-scoped delete.

All routes: tier enforced at DB (RLS) and re-checked at API (401 anon / 403 forbidden). Row writes call `service` → single write path → the deferred `_emit_row_change()` seam (no-op now).

## 9. Frontend (Stories 4-5, 4-7)

- **`/mini-apps` catalog:** list apps (name, tier badge, build-status pill), "Create Mini-App" form (name, description, expected output, tier, whitelist picker for private), "View generated code" modal (renders the codegen `.tsx` artifact — honors the codegen intent), open button.
- **`/mini-apps/$appId` host page:** mounts the sandboxed iframe; renders build-status / empty / error states; requests the scoped token on load.
- **Generated app (inside iframe):** compiled per-app bundle rendering a data table + create/edit/delete form from the UI spec, talking only to the scoped CRUD API.

## 10. Error Handling

Reuse the platform API error envelope. Status codes: `401` (anon on gated app), `403` (tier violation), `409` (CAS conflict), `422` (schema-invalid emission or row write), build-status surfaced as a field while `building` (UI shows a pending state, not an error).

## 11. Testing (only when the user requests — per working preferences)

- Meta-schema accept/reject matrix.
- RLS tier matrix reproducing FR-16 consequences (401 anon, 403 wrong-dept need_auth, 403 non-whitelisted private, 200 public same-tenant).
- CAS 409 on concurrent row update.
- Provisioner + codegen purity (deterministic, no I/O).
- AST allowlist rejects escape attempts (`window.parent`, arbitrary import, `eval`).
- Scoped token cannot read a different `app_id`.

## 12. Deferred Seams (Epic 5 pairing)

- `_emit_row_change(app_id, event_type, payload)` in `service.py` — no-op stub now; becomes the Action Bus publish (FR-17) later.
- Orchestrator-triggered emission mid-Workflow-Run: `service.provision()` is already callable by the orchestrator; the mid-run trigger wiring is deferred.

## 13. Resolved Defaults (were open questions)

1. **Build toolchain:** standalone `esbuild` step (faster, simpler to resource-cap) rather than a full Vite rebuild of the SPA.
2. **Emission LLM:** the FPT DeepSeek-V4-Flash adapter already wired via the `.env`-driven `ModelPort` (commit `cb20c5b`) is the emission provider in the demo env.
3. **Scoped-token issuance:** `POST /mini-apps/{id}/session-token`, gated by the platform session's tier check; returns the per-app audience-scoped JWT the iframe uses.

## 14. Story → Deliverable Map

| Story | Deliverable |
|---|---|
| 4-1 | `schema_validation.py`, `emission.py`, meta-schema, audit events |
| 4-2 | `provisioner.py`, `lifecycle.py`, `mini_apps`/`mini_app_rows` tables + migration |
| 4-3 | RLS policies + `visibility.py` tier resolution |
| 4-4 | `crud_engine.py`, generic `/apps/{app_id}/rows/*` router |
| 4-5 | `codegen.py`, `BuildPort` + esbuild adapter, build worker job, iframe host, scoped token |
| 4-7 | `/mini-apps` catalog route + create form + "view generated code" |
| sandbox | AST allowlist, resource-capped build, separate bundle, sandboxed iframe, scoped JWT, build-status lifecycle |

## 15. Open Questions (unresolved)

- None blocking. Confirm during implementation: exact GUC names for the RLS join (reuse whatever the tenant middleware sets), and whether the per-app runtime SDK (the small JS the generated app imports for CRUD calls) is vendored as a static asset or inlined by codegen.
