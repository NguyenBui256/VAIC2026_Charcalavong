# Chat-driven Mini-App editing (detail page) — Design

**Date:** 2026-07-19
**Status:** Approved (design), ready for implementation plan

## Problem

The mini-app detail page (`/mini-apps/:appId`) is a single-column sandboxed iframe host. We want it to become a **builder surface**: a **chat panel (left)** to edit the app by natural-language instruction, and a **live preview (right)** — the running app — that refreshes after each edit rebuilds.

## Decisions (locked with user)

- **Real editing**: the chat calls an LLM to **revise** the app's `entity_schema`/`ui_spec`, then **rebuilds** (reuses the existing build pipeline). Not a mock.
- **Layout**: two columns, full height — Chat left, Preview (iframe) fills the right. No separate output panel (the running app *is* the output).
- **Self-contained chat** — a small chat panel inside the mini-app page; does NOT depend on the unmerged `feat/chat-tab` branch.
- **Scope caveat (accepted)**: the generated app is a fixed template (form + table/cards) rendered from `entity_schema` + `ui_spec`. Chat edits are therefore **schema/layout-level** — add/remove/rename fields, change types/labels/validation, switch `layout` table↔cards, toggle `primary_actions`. **No** arbitrary visual restyling (colors, bespoke components); that would need free-form codegen (out of scope).

## Global Constraints

- Backend: FastAPI, thin routes returning `{"data","error","meta"}` via `_ok(...)`; `get_tenant_session`; builder/admin role gate matches mini-app creation (`create_app_from_schema` requires `builder`/`admin`).
- LLM via the existing port: `select_llm_adapter(provider)`, `Message`, `ModelRef`, `adapter.complete(messages, model, {"temperature": ...}).content`. Model from `settings.llm_provider`/`llm_model` (`emission._model()`).
- Meta-schema validation via `validate_entity_schema` / `validate_ui_spec` (raise `SchemaValidationError`); route wraps to `DomainError(..., http_status=422)`.
- Build pipeline unchanged: update row → set `build_status="pending"` → `enqueue_build(pool, app_id)`; worker does `pending→building→ready|failed`.
- Frontend: React 19 + TS + TanStack Query; `components/ui`; branch order error→loading→empty→data; mutations toast.
- **NO automated tests; do NOT run typecheck/lint/build** unless asked (project override). Verification is manual/live.
- Requires `VAIC_LLM_*` configured on the backend; without it, `/edit` returns a clear error surfaced in the chat.

## Architecture

### Backend — revise + edit endpoint

**`emission.revise_schema(current_schema, current_ui_spec, instruction, *, llm=None) → tuple[EntitySchema, UiSpec, str, str]`**
- Mirrors `emit_schema`. System prompt: "You revise a data-entry mini-app. Given the CURRENT `{entity_schema, ui_spec}` JSON and a user instruction, return STRICT JSON `{entity_schema, ui_spec, message}` — the full updated schema+ui_spec (same shape rules as emission: allowed types, `^[a-z][a-z0-9_]*$` names, enum needs options) and a one-sentence `message` describing what changed." User message = current JSON + instruction.
- Parse (strip fences) → `validate_entity_schema` + `validate_ui_spec` → return `(schema, ui_spec, message, prompt)`. Invalid JSON/schema → `SchemaValidationError`.

**`service.revise_app(session, app, principal, instruction, *, llm=None) → tuple[MiniApp, str]`**
- Role gate (builder/admin) like `create_app_from_schema`.
- `revise_schema(current)` → update `app.entity_schema`, `app.ui_spec`, set `build_status="pending"`, `build_error=None`, bump `updated_at` → commit.
- Audit `mini_app.revised` (mirror `_audit`); return `(app, message)`.

**Route `POST /mini-apps/{id}/edit`** (in `routes.py`) body `EditMiniAppRequest {instruction: str}`:
- Load app + `assert_can_access`; scoped-token guard (a scoped mini-app token cannot edit — mirror the session-token route's guard).
- `try: app, message = service.revise_app(...) except SchemaValidationError as exc: raise DomainError(exc.reason, code="schema_rejected", http_status=422)`.
- `await enqueue_build(pool, str(app.id))`.
- Return `_ok({"message": message, "app": service.serialize_app(app)})` (build_status now "pending").

### Frontend — two-column detail page + chat

**`lib/miniAppsApi.ts`** — add `editMiniApp(id, instruction) → { message: string; app: MiniApp }` (`POST /mini-apps/{id}/edit`).

**`routes/mini-app-host.tsx`** — restructure to a full-height 2-col grid:
- Left column: `<MiniAppChatPanel app={app} appId={appId} />`.
- Right column: the preview — reuse the building/failed/token/iframe branch logic, but the iframe is keyed on `app.updated_at` (and a cache-bust param) so a completed rebuild hard-reloads it.
- The existing `useMiniAppDatabases` bound-DB line stays (small, in a compact header above or within the chat column).

**`components/mini-apps/MiniAppChatPanel.tsx`** (self-contained):
- Local `messages: {role:"user"|"assistant"; text:string}[]` state (seed with a welcome/assistant hint). Optional `localStorage` persistence keyed `vaic:miniapp-chat:{appId}`.
- Input + Send. On send: push user msg; `editMiniApp.mutate(instruction)`; on success push assistant msg (fake-stream via a small `streamText` helper for feel), invalidate `["mini-app", appId]` so the app refetch flips to `building`; on error push an assistant error line + toast.
- Shows a "Rebuilding…" indicator while `app.build_status` is `pending`/`building`; input disabled during rebuild.
- Reuses existing `ui` primitives (Button, Card, Skeleton) + `CodeBlock` if we render code (optional).

## Data flow

1. User types "add a due_date field and show as cards" → `POST /mini-apps/{id}/edit`.
2. Backend LLM revises `{entity_schema+due_date, ui_spec.layout=cards}` → validates → persists → `build_status=pending` → enqueues build → returns `{message, app}`.
3. Chat appends the assistant `message`; the app query polls `pending→building→ready`.
4. On `ready`, the right iframe (keyed on new `updated_at`) reloads the freshly built bundle → preview reflects the edit.

## Error handling

- LLM/JSON/schema failure → 422 with `SchemaValidationError.reason`, surfaced as an assistant error message + toast; app stays on its previous good build.
- LLM not configured / adapter error → 5xx surfaced in chat as "Editing is unavailable (LLM not configured)".
- Build failure after a valid edit → existing `build_status="failed"` + `build_error` shown in the preview column's error state.

## Out of scope (YAGNI)

- Free-form visual restyling / arbitrary component code (fixed template only).
- Server-persisted chat history (client-side only for now).
- Streaming LLM tokens end-to-end (assistant reply is fake-streamed client-side).
- Multi-turn context sent to the LLM (each edit is stateless: current schema + one instruction). Revisit if edits need prior-turn memory.

## Open questions

- None blocking. (Conversation memory across turns is deferred; each edit is independent.)
