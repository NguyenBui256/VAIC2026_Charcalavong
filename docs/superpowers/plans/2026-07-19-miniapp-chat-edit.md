# Chat-driven Mini-App editing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the mini-app detail page into a builder: a left chat panel that edits the app via LLM (revise schema/ui_spec → rebuild), and a right live-preview iframe that refreshes after each rebuild.

**Architecture:** New backend `revise_schema` (LLM) + `revise_app` (service) + `POST /mini-apps/{id}/edit` route reuse the existing emission/validation/build pipeline. Frontend rewrites `mini-app-host.tsx` into a 2-col layout with a self-contained `MiniAppChatPanel`.

**Tech Stack:** FastAPI / SQLAlchemy / arq (backend); React 19 + TS + TanStack Query (frontend).

## Global Constraints

- Thin routes → `{"data","error","meta"}` via local `_ok(...)`; `get_tenant_session`; arq pool via `get_arq_pool`.
- Role gate: editing requires `principal.role in ("builder","admin")` (mirror `service.create_app_from_schema`).
- LLM via `select_llm_adapter`, `Message`, `ModelRef`, `adapter.complete(messages, model, {"temperature":0.2}).content`; model from `emission._model()`.
- Validation via `validate_entity_schema` / `validate_ui_spec` (raise `SchemaValidationError`); route wraps to `DomainError(exc.reason, code="schema_rejected", http_status=422)`.
- On edit: set `build_status="pending"`, `build_error=None`, then `enqueue_build(pool, str(app.id))`. Worker handles `pending→building→ready|failed`.
- A scoped mini-app token must NOT be able to edit (mirror the `/session-token` route's `SCOPE_MINIAPP_ROWS` guard).
- Frontend: TanStack Query, `components/ui`, branch order error→loading→empty→data, toasts.
- **NO tests. Do NOT run typecheck/lint/build/format** (project override). Each task ends in a commit.
- Requires `VAIC_LLM_*` configured for live use; code returns a clear error otherwise.

## File Structure

**Backend (modified):**
- `backend/app/modules/mini_app/emission.py` — add `revise_schema(...)`.
- `backend/app/modules/mini_app/service.py` — add `revise_app(...)`.
- `backend/app/modules/mini_app/routes.py` — add `POST /mini-apps/{id}/edit`.

**Frontend (new):**
- `frontend/src/components/mini-apps/MiniAppChatPanel.tsx`
- `frontend/src/lib/streamText.ts` — tiny fake-stream helper.

**Frontend (modified):**
- `frontend/src/lib/miniAppsApi.ts` — `editMiniApp(...)`.
- `frontend/src/routes/mini-app-host.tsx` — 2-col layout + iframe reload key.

---

## Task 1: Backend — `revise_schema` (LLM revise)

**Files:** Modify `backend/app/modules/mini_app/emission.py`

**Interfaces:**
- Produces: `revise_schema(current_schema: dict, current_ui_spec: dict, instruction: str, *, llm=None) -> tuple[EntitySchema, UiSpec, str, str]` returning `(schema, ui_spec, message, prompt)`.

- [ ] **Step 1: Add the revise system prompt + function**

Append to `emission.py` (reuses `_model`, `select_llm_adapter`, `Message`, `_strip_fences`, validators, `_ALLOWED_TYPES` already in the file):
```python
_REVISE_SYSTEM = (
    "You revise a data-entry mini-app for a bank. You are given the CURRENT "
    "app as JSON (entity_schema + ui_spec) and a user instruction describing a "
    "change. Return STRICT JSON only (no prose, no markdown fences) of the form: "
    '{"entity_schema": {"fields": [{"name","type","label","required","min","max",'
    '"minLength","maxLength","pattern","options"}], "primary_display"}, '
    '"ui_spec": {"layout":"table|cards","primary_actions":["create","edit","delete"]}, '
    '"message": "one short sentence describing what changed"}. '
    "Return the FULL updated entity_schema and ui_spec (not a diff), preserving "
    "fields the instruction does not change. "
    f"Allowed field types: {_ALLOWED_TYPES}. Field names must match ^[a-z][a-z0-9_]*$. "
    "enum fields MUST include a non-empty options array. Keep the app minimal and coherent."
)


def revise_schema(
    current_schema: dict[str, Any],
    current_ui_spec: dict[str, Any],
    instruction: str,
    *,
    llm: Any | None = None,
) -> tuple[EntitySchema, UiSpec, str, str]:
    """Ask the LLM to revise {entity_schema, ui_spec} per an instruction.

    Returns (schema, ui_spec, message, prompt). Raises SchemaValidationError if
    the model output isn't valid JSON or fails the meta-schema.
    """
    prompt = (
        "CURRENT APP JSON:\n"
        + json.dumps({"entity_schema": current_schema, "ui_spec": current_ui_spec})
        + f"\n\nINSTRUCTION:\n{instruction}"
    )
    adapter = llm or select_llm_adapter(_model().provider)
    messages = [Message(role="system", content=_REVISE_SYSTEM), Message(role="user", content=prompt)]
    completion = adapter.complete(messages, _model(), {"temperature": 0.2})
    try:
        parsed = json.loads(_strip_fences(completion.content))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"model did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SchemaValidationError("model output must be a JSON object")
    schema = validate_entity_schema(parsed.get("entity_schema", {}))
    ui_spec = validate_ui_spec(parsed.get("ui_spec", {}))
    message = str(parsed.get("message") or "Updated the app.")
    return schema, ui_spec, message, prompt
```

- [ ] **Step 2: Commit**
```
git add backend/app/modules/mini_app/emission.py
git commit -m "feat(mini-app): revise_schema — LLM revises entity_schema/ui_spec from an instruction"
```

---

## Task 2: Backend — `revise_app` service + `POST /mini-apps/{id}/edit` route

**Files:**
- Modify `backend/app/modules/mini_app/service.py`
- Modify `backend/app/modules/mini_app/routes.py`

**Interfaces:**
- Consumes: `revise_schema` (Task 1).
- Produces: `service.revise_app(session, app, principal, instruction, *, llm=None) -> tuple[MiniApp, str]`; `POST /mini-apps/{id}/edit`.

- [ ] **Step 1: Service — revise_app**

In `service.py`, add (mirrors `create_app_from_schema` role gate + `_audit`; `datetime_now()` already defined in this file):
```python
def revise_app(
    session: Session,
    app: MiniApp,
    principal: MiniAppPrincipal,
    instruction: str,
    *,
    llm: Any | None = None,
) -> tuple[MiniApp, str]:
    """LLM-revise an app's schema/ui_spec from an instruction, mark it for
    rebuild (build_status='pending'), and return (app, assistant_message).
    Caller enqueues the build + wraps SchemaValidationError -> 422."""
    from app.modules.mini_app.emission import revise_schema

    if principal.role not in ("builder", "admin"):
        from app.core.errors import AuthorizationError
        raise AuthorizationError("mini-app editing requires the builder role")

    schema, ui_spec, message, _prompt = revise_schema(app.entity_schema, app.ui_spec, instruction, llm=llm)
    app.entity_schema = schema.model_dump()
    app.ui_spec = ui_spec.model_dump()
    app.build_status = "pending"
    app.build_error = None
    app.updated_at = datetime_now()
    session.commit()
    session.refresh(app)
    _audit(app.id, "mini_app.revised", {"instruction": instruction, "message": message})
    return app, message
```
(`Any` is already imported in service.py via `from typing import Any`.)

- [ ] **Step 2: Route — POST /mini-apps/{id}/edit**

In `routes.py`, add the request model near `CreateMiniAppRequest`:
```python
class EditMiniAppRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=2000)
```
And the route (place after `rebuild_mini_app_route`), mirroring its structure + the session-token scoped-guard + the create route's 422 wrap:
```python
@mini_apps_router.post("/{app_id}/edit")
async def edit_mini_app_route(
    app_id: uuid.UUID, body: EditMiniAppRequest, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> JSONResponse:
    if getattr(request.state, "scope", None) == SCOPE_MINIAPP_ROWS:
        raise AuthorizationError("a scoped mini-app token cannot edit the app")
    app = service.get_app(session, app_id)
    principal = _principal(request)
    assert_can_access(app, principal)
    try:
        app, message = service.revise_app(session, app, principal, body.instruction)
    except SchemaValidationError as exc:
        _audit_emission(app.id, "mini_app.revise_rejected", {"reason": exc.reason})
        raise DomainError(exc.reason, code="schema_rejected", http_status=422) from exc
    await enqueue_build(pool, str(app.id))
    return JSONResponse(status_code=200, content=_ok({"message": message, "app": service.serialize_app(app)}))
```
(`SchemaValidationError` is already imported in routes.py from `schema_validation`; `AuthorizationError`, `DomainError`, `SCOPE_MINIAPP_ROWS`, `enqueue_build`, `_audit_emission`, `assert_can_access` all already imported.)

- [ ] **Step 3: Manual smoke (optional, user-run)** — `POST /mini-apps/{id}/edit {"instruction":"add a due_date date field"}` → 200 with `message` + `app.build_status=="pending"`; field appears after rebuild.

- [ ] **Step 4: Commit**
```
git add backend/app/modules/mini_app/service.py backend/app/modules/mini_app/routes.py
git commit -m "feat(mini-app): POST /mini-apps/{id}/edit — revise via LLM + rebuild"
```

---

## Task 3: Frontend — editMiniApp API + streamText helper

**Files:**
- Modify `frontend/src/lib/miniAppsApi.ts`
- Create `frontend/src/lib/streamText.ts`

**Interfaces:**
- Produces: `editMiniApp(id, instruction) -> Promise<{ message: string; app: MiniApp }>`; `streamText(full, onChunk, onDone) -> cancelFn`.

- [ ] **Step 1: editMiniApp**

Append to `miniAppsApi.ts`:
```typescript
export const editMiniApp = (id: string, instruction: string) =>
  apiFetch<{ message: string; app: MiniApp }>(`/mini-apps/${id}/edit`, {
    method: "POST",
    body: JSON.stringify({ instruction }),
  });
```

- [ ] **Step 2: streamText helper**

`frontend/src/lib/streamText.ts`:
```typescript
/* Fake-stream a string chunk-by-chunk to simulate typing in the chat.
 * Calls onChunk with the accumulated text; onDone at the end. Returns a
 * cancel fn (call on unmount / before a new stream). */
export function streamText(
  full: string,
  onChunk: (partial: string) => void,
  onDone: () => void,
): () => void {
  const STEP = 3;
  const INTERVAL_MS = 16;
  let i = 0;
  const timer = setInterval(() => {
    i = Math.min(full.length, i + STEP);
    onChunk(full.slice(0, i));
    if (i >= full.length) {
      clearInterval(timer);
      onDone();
    }
  }, INTERVAL_MS);
  return () => clearInterval(timer);
}
```

- [ ] **Step 3: Commit**
```
git add frontend/src/lib/miniAppsApi.ts frontend/src/lib/streamText.ts
git commit -m "feat(frontend): editMiniApp api + streamText helper"
```

---

## Task 4: Frontend — MiniAppChatPanel

**Files:** Create `frontend/src/components/mini-apps/MiniAppChatPanel.tsx`

**Interfaces:**
- Consumes: `editMiniApp` (Task 3), `streamText` (Task 3), `MiniApp` type, `useToast`, `ui` primitives.
- Produces: `MiniAppChatPanel` default export — props `{ app: MiniApp; appId: string }`.

- [ ] **Step 1: Component**

`frontend/src/components/mini-apps/MiniAppChatPanel.tsx`:
```typescript
/* Chat panel (left column of the mini-app detail page). Sends a natural-language
 * instruction to POST /mini-apps/{id}/edit, which LLM-revises the app's schema/
 * ui_spec and rebuilds. Client-side message history (localStorage per app);
 * assistant reply is fake-streamed. Input disabled while the app is rebuilding. */
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, useToast } from "../ui";
import { editMiniApp, type MiniApp } from "../../lib/miniAppsApi";
import { streamText } from "../../lib/streamText";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

const WELCOME: ChatMessage = {
  role: "assistant",
  text:
    "Hi! Tell me how to change this app — e.g. \"add a due_date date field\", " +
    "\"show records as cards\", or \"remove the delete action\". I'll update it and rebuild the preview.",
};

function storageKey(appId: string): string {
  return `vaic:miniapp-chat:${appId}`;
}

function loadMessages(appId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(storageKey(appId));
    if (raw) return JSON.parse(raw) as ChatMessage[];
  } catch {
    /* ignore corrupt storage */
  }
  return [WELCOME];
}

export interface MiniAppChatPanelProps {
  app: MiniApp;
  appId: string;
}

export default function MiniAppChatPanel({ app, appId }: MiniAppChatPanelProps) {
  const qc = useQueryClient();
  const { show } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadMessages(appId));
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState<string | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const isRebuilding = app.build_status === "pending" || app.build_status === "building";

  useEffect(() => {
    try {
      localStorage.setItem(storageKey(appId), JSON.stringify(messages));
    } catch {
      /* ignore quota errors */
    }
  }, [messages, appId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, streaming]);

  useEffect(() => () => cancelRef.current?.(), []);

  const edit = useMutation<{ message: string; app: MiniApp }, Error, string>({
    mutationFn: (instruction) => editMiniApp(appId, instruction),
    onSuccess: (data) => {
      // Reflect the pending/rebuild status immediately, then poll picks up ready.
      qc.setQueryData(["mini-app", appId], data.app);
      qc.invalidateQueries({ queryKey: ["mini-app", appId] });
      // Fake-stream the assistant reply for feel.
      cancelRef.current?.();
      setStreaming("");
      cancelRef.current = streamText(
        data.message,
        (partial) => setStreaming(partial),
        () => {
          setStreaming(null);
          setMessages((m) => [...m, { role: "assistant", text: data.message }]);
        },
      );
    },
    onError: (err) => {
      const text = `Sorry — I couldn't apply that: ${err.message}`;
      setMessages((m) => [...m, { role: "assistant", text }]);
      show(err.message || "Edit failed", "error");
    },
  });

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const instruction = input.trim();
    if (!instruction || edit.isPending || isRebuilding) return;
    setMessages((m) => [...m, { role: "user", text: instruction }]);
    setInput("");
    edit.mutate(instruction);
  }

  return (
    <div
      data-testid="vaic-miniapp-chat"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-control)",
        background: "var(--color-surface)",
        overflow: "hidden",
      }}
    >
      <div
        ref={scrollRef}
        style={{ flex: 1, overflowY: "auto", padding: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}
      >
        {messages.map((m, i) => (
          <ChatBubble key={i} role={m.role} text={m.text} />
        ))}
        {streaming !== null && <ChatBubble role="assistant" text={streaming || "…"} />}
        {edit.isPending && streaming === null && <ChatBubble role="assistant" text="Thinking…" />}
      </div>

      {isRebuilding && (
        <div
          className="vaic-inline-alert"
          role="status"
          style={{ margin: "0 var(--space-3) var(--space-2)", color: "var(--color-text-tertiary)", fontSize: "var(--text-small)" }}
        >
          Rebuilding the preview…
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", gap: "var(--space-2)", padding: "var(--space-3)", borderTop: "1px solid var(--color-border)" }}
      >
        <input
          className="vaic-form-input vaic-focusable"
          style={{ flex: 1 }}
          placeholder={isRebuilding ? "Rebuilding…" : "Describe a change to this app…"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={edit.isPending || isRebuilding}
          data-testid="vaic-miniapp-chat-input"
        />
        <Button variant="primary" type="submit" disabled={!input.trim() || edit.isPending || isRebuilding}>
          Send
        </Button>
      </form>
    </div>
  );
}

function ChatBubble({ role, text }: { role: "user" | "assistant"; text: string }) {
  const isUser = role === "user";
  return (
    <div
      style={{
        alignSelf: isUser ? "flex-end" : "flex-start",
        maxWidth: "85%",
        padding: "var(--space-2) var(--space-3)",
        borderRadius: "var(--radius-control)",
        background: isUser ? "var(--color-primary-soft)" : "var(--color-surface-muted)",
        color: "var(--color-text-primary)",
        fontSize: "var(--text-body)",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {text}
    </div>
  );
}
```
Note: verify `useToast` and `Button` export from `components/ui`; `var(--color-primary-soft)`, `var(--color-surface-muted)`, `var(--color-text-primary)` are used elsewhere (Sidebar/AppShell). If `--color-text-primary` isn't a token, use `var(--color-text)` / inherit.

- [ ] **Step 2: Commit**
```
git add frontend/src/components/mini-apps/MiniAppChatPanel.tsx
git commit -m "feat(frontend): MiniAppChatPanel — chat to edit a mini-app"
```

---

## Task 5: Frontend — 2-column detail layout + preview reload

**Files:** Modify `frontend/src/routes/mini-app-host.tsx`

**Interfaces:**
- Consumes: `MiniAppChatPanel` (Task 4). Keeps existing `useMiniAppDatabases` bound-DB line.

- [ ] **Step 1: Restructure into two columns**

Rewrite `mini-app-host.tsx`'s returned JSX (keep the queries + loading/error/not-found guards + `MiniAppIframe` component). Replace the single-column `return (...)` for the loaded state with a full-height 2-col grid: compact header on top, then Chat (left) | Preview (right). Add imports:
```typescript
import MiniAppChatPanel from "../components/mini-apps/MiniAppChatPanel";
```
New loaded-state return (the `if (appQuery.isLoading|isError|!app)` guards above stay unchanged):
```typescript
  return (
    <div
      data-testid="vaic-mini-app-host-page"
      style={{ display: "flex", flexDirection: "column", height: "calc(100vh - var(--topbar-h, 64px) - 2 * var(--space-4))", gap: "var(--space-3)" }}
    >
      <header>
        <h1 className="text-h1" style={{ marginBottom: "var(--space-1)" }}>{app.name}</h1>
        {app.description && (
          <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>{app.description}</p>
        )}
        {app.database_id && (
          <p className="text-small" style={{ color: "var(--color-text-tertiary)", marginTop: "var(--space-1)" }}>
            Database:{" "}
            <Link to="/database" className="vaic-focusable" style={{ color: "var(--color-primary)" }}>
              {boundDb?.name ?? "View in Database"}
            </Link>
          </p>
        )}
      </header>

      <div
        style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(320px, 2fr) 3fr", gap: "var(--space-3)" }}
      >
        <div style={{ minHeight: 0 }}>
          {appId && <MiniAppChatPanel app={app} appId={appId} />}
        </div>

        <div style={{ minHeight: 0, display: "flex", flexDirection: "column" }} data-testid="vaic-mini-app-preview">
          {(app.build_status === "pending" || app.build_status === "building") && (
            <Card title="Building your Mini-App…">
              <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
                This usually takes a few moments. The preview refreshes automatically.
              </p>
              <Skeleton height="14px" width="60%" style={{ marginTop: "var(--space-3)" }} />
            </Card>
          )}
          {app.build_status === "failed" && (
            <ErrorState
              message="Mini-App build failed"
              detail={app.build_error ?? undefined}
              retry={<Button variant="secondary" onClick={() => appQuery.refetch()}>Retry</Button>}
            />
          )}
          {isReady && tokenQuery.isLoading && <Skeleton height="100%" />}
          {isReady && tokenQuery.isError && (
            <ErrorState
              message={tokenQuery.error?.message ?? "Failed to obtain a session token"}
              retry={<Button variant="secondary" onClick={() => tokenQuery.refetch()}>Retry</Button>}
            />
          )}
          {isReady && tokenQuery.data && appId && (
            <MiniAppIframe app={app} appId={appId} token={tokenQuery.data.token} />
          )}
        </div>
      </div>
    </div>
  );
```

- [ ] **Step 2: Make the iframe hard-reload after a rebuild**

Update `MiniAppIframe` to key on `app.updated_at` and cache-bust so a completed rebuild reloads the bundle, and fill its container height:
```typescript
function MiniAppIframe({ app, appId, token }: { app: MiniApp; appId: string; token: string }) {
  const apiBase = import.meta.env.VITE_API_BASE ?? "";
  const src = `${apiBase}/mini-app-runtime/${appId}/index.html`;
  const hash = new URLSearchParams({ appId, token, apiBase, cb: app.updated_at }).toString();

  return (
    <iframe
      key={app.updated_at}
      title={app.name}
      data-testid="vaic-mini-app-host-iframe"
      src={`${src}#${hash}`}
      // CRITICAL: allow-scripts + allow-forms only — never allow-same-origin.
      sandbox="allow-scripts allow-forms"
      style={{ flex: 1, width: "100%", minHeight: 0, border: "1px solid var(--color-border)", borderRadius: "var(--radius-control)" }}
    />
  );
}
```

- [ ] **Step 3: Manual verification (user-run/live)** — open a ready app; type "add a due_date date field" → assistant replies, "Rebuilding…" shows, preview reloads with the new field; type "show records as cards" → layout changes after rebuild.

- [ ] **Step 4: Commit**
```
git add frontend/src/routes/mini-app-host.tsx
git commit -m "feat(frontend): mini-app detail = chat panel + live preview (2-col)"
```

---

## Self-Review notes (author)

- **Spec coverage:** revise LLM (Task 1), edit endpoint + role/scoped guards + 422 wrap + rebuild (Task 2), api+helper (Task 3), chat panel with rebuild-aware input + fake-stream + localStorage (Task 4), 2-col layout + iframe reload keyed on `updated_at` (Task 5). All spec sections mapped.
- **Type consistency:** `editMiniApp` returns `{message, app: MiniApp}` — matches route `_ok({"message", "app": serialize_app})`. `revise_app` returns `(MiniApp, str)`; route unpacks `app, message`. Chat panel writes `["mini-app", appId]` query data (same key `mini-app-host.tsx` reads).
- **Ordering:** Task 5 imports Task 4's `MiniAppChatPanel`; do 4 before 5 (or stub). Backend 1→2 ordered.
- **Assumptions to verify (inline):** `--color-text-primary` token name; `useToast`/`Button` exports; `serialize_app` includes `updated_at` (it does) and `build_status`; the arq worker rebuild path re-reads `entity_schema`/`ui_spec` from the row (it does — `_run_pipeline` loads from `app`).
