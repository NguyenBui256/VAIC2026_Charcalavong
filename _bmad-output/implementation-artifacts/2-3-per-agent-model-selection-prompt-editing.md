---
baseline_commit: 4e2c5ad3cb823b8edb5f8ce6d0ea8b3d94a4fd1c
---

# Story 2.3: Per-Agent Model Selection & Prompt Editing

Status: ready-for-dev

## Story

As a **user configuring a Specialist Agent**,
I want **to pick the LLM provider and model for my Agent and refine the system prompt**,
So that **the Agent uses the right model for its task without code changes**.

## Acceptance Criteria

1. **AC1 — Provider dropdown lists runtime-configured providers** [Source: epics.md L717-718]: When the user opens the **Model** tab, a Provider dropdown lists providers derived from *runtime configuration*. At minimum **Anthropic** is selectable (its adapter is real per Story 1.6). **OpenAI, Google, Ollama** appear grayed out / disabled with a **"Not configured"** label. The set of enabled providers is computed from actual runtime state (configured API keys / implemented adapters), NOT hard-coded in the frontend.
2. **AC2 — Selecting a Provider populates the Model dropdown** [Source: epics.md L719]: Selecting a Provider populates a Model dropdown with that provider's available models (e.g. Anthropic → `claude-sonnet-4-5`, etc.). A disabled provider yields no selectable models.
3. **AC3 — Parameters section with sensible defaults** [Source: epics.md L720]: A Parameters section allows optional overrides — at minimum `temperature` and `max_tokens` — each with sensible defaults (e.g. `max_tokens` default 1024 matching the adapter). Leaving a field unset stores no override for that key.
4. **AC4 — Save persists `{provider, model_name, parameters}` as DATA, never code (AD-7)** [Source: epics.md L721-722]: Saving the Model tab fires `PATCH /agents/{id}` and persists the selection into the Agent record as the `model` (ModelRef) object `{provider, model_name, parameters}`. The value is stored as data — no branch, class, or import is generated per provider.
5. **AC5 — Changing the Model requires no code change (FR-5)** [Source: epics.md L723]: Switching an Agent's provider/model is a pure config update. No backend or frontend code change is required to make the Agent use the newly selected model; the Model Layer selects the adapter at run time from the stored `provider`.
6. **AC6 — Prompt tab renders a directive-aware editor** [Source: epics.md L724-725]: Opening the **Prompt** tab renders a system-prompt editor (monospace textarea) with syntax highlighting for prompt directives, e.g. `{{tool:rag.search}}` and `{{kb:agent_id}}`.
7. **AC7 — Character count + context-window warning** [Source: epics.md L726]: The editor shows a live character count and warns when the prompt exceeds the selected model's context window (estimate). The warning is non-blocking (informational).
8. **AC8 — Saving the Prompt tab persists to `system_prompt`** [Source: epics.md L727]: Saving the Prompt tab persists the text to the Agent record's `system_prompt` field via `PATCH /agents/{id}`; success shows a toast, failure shows an inline error (consistent with Story 2.2 save behavior).
9. **AC9 — Missing provider surfaces at RUN time with a clear `audit_trail` message (FR-5 consequence)** [Source: epics.md L728-729]: When an Agent runs and its configured provider is missing/unconfigured (e.g. API key revoked, or a placeholder provider like OpenAI), the error surfaces **at run time, not config time**, with a clear message recorded in `audit_trail`. Configuration and saving of such a provider must NOT be blocked at config time.
10. **AC10 — A missing provider in one Agent does not crash Agents on other providers (FR-26)** [Source: epics.md L730]: One Agent configured with an unconfigured/placeholder provider failing at run time must not affect Agents configured with a working provider (e.g. Anthropic). Provider isolation is per-Agent.

## Tasks / Subtasks

- [ ] **T1 — Backend: expose runtime provider/model catalog** (AC: #1, #2, #5)
  - [ ] T1.1 Add a read-only endpoint (e.g. `GET /agents/providers` or `/llm/providers`) in `app/modules/agent_builder/routes.py` that returns the provider catalog: for each provider `{id, label, configured: bool, models: [...]}`. `configured` is derived from runtime settings (`get_settings()`): Anthropic → `configured = bool(anthropic_api_key)` AND adapter implemented; OpenAI/Google/Ollama → implemented=false → `configured=false` ("Not configured").
  - [ ] T1.2 Source the provider/model catalog from a single backend constant/registry (do NOT duplicate model lists in the frontend). Anthropic model list is a small static list (e.g. `claude-sonnet-4-5`) plus a per-model context-window map used by AC7.
  - [ ] T1.3 Do NOT gate on live API calls; `configured` reflects whether a key is set + adapter is real, so the UI can render without making a network call to the provider.
- [ ] **T2 — Backend: persist ModelRef + system_prompt on the Agent record** (AC: #4, #5, #8)
  - [ ] T2.1 Ensure the Agent record (from Story 2.1) stores `model: {provider, model_name, parameters}` and `system_prompt: str`. If Story 2.1 already models these, reuse them; otherwise add columns/fields + an Alembic migration.
  - [ ] T2.2 `PATCH /agents/{id}` accepts partial updates for `model` and `system_prompt`; validates `provider` is a known provider id (but does NOT reject unconfigured providers — AC9). `parameters` is a free-form `dict[str, Any]` mirroring `ModelRef.parameters`.
  - [ ] T2.3 Store parameters as data verbatim; no provider-specific server code branches (AD-7).
- [ ] **T3 — Backend: runtime failure path + audit (RED then GREEN)** (AC: #9, #10)
  - [ ] T3.1 Confirm the adapter-selection helper maps `ModelRef.provider` → adapter instance. Anthropic → `AnthropicLlmAdapter`; openai/google/ollama → placeholder adapters that raise `NotImplementedError`; a missing Anthropic key raises `RuntimeError` at call time (already implemented in Story 1.6).
  - [ ] T3.2 On run-time provider failure, emit an `audit_trail` entry with a clear message (provider name + remediation hint). Reuse the `model_invocation` / error audit pattern; do NOT swallow the exception (AD-4). This story only needs the failure to be observable + isolated — full Orchestrator run wiring is Epic 3.
  - [ ] T3.3 Test: two adapters, one unconfigured provider raises on call, the Anthropic one keeps working (mirror `test_one_bad_adapter_does_not_crash_another` from Story 1.6).
- [ ] **T4 — Frontend: Model tab** (AC: #1, #2, #3, #4, #5)
  - [ ] T4.1 Build the Model tab component under the Agent detail shell (Story 2.2). Fetch the provider catalog via a TanStack Query hook using `apiFetch` (`frontend/src/lib/api.ts`).
  - [ ] T4.2 Provider `<select>` — enabled options for configured providers; disabled options render "Not configured" for OpenAI/Google/Ollama.
  - [ ] T4.3 Model `<select>` — populated from the selected provider's `models`.
  - [ ] T4.4 Parameters section — `temperature` and `max_tokens` inputs with defaults; only send keys the user set into `parameters`.
  - [ ] T4.5 Save → `PATCH /agents/{id}` with `{ model: {provider, model_name, parameters} }`; success toast, inline error on failure; dirty-dot / unsaved-changes behavior consistent with Story 2.2.
- [ ] **T5 — Frontend: Prompt tab** (AC: #6, #7, #8)
  - [ ] T5.1 Build the Prompt tab: monospace editor for `system_prompt`. Highlight directive tokens `{{tool:...}}` and `{{kb:...}}` (lightweight regex-based highlight overlay; reuse `CodeBlock` styling tokens where possible — see `frontend/src/components/ui/CodeBlock.tsx`).
  - [ ] T5.2 Live character count; non-blocking warning banner when length exceeds the selected model's context-window estimate (from the catalog in T1.2).
  - [ ] T5.3 Save → `PATCH /agents/{id}` with `{ system_prompt }`; toast + inline error; dirty-dot consistent with Story 2.2.
- [ ] **T6 — Tests** (AC: all)
  - [ ] T6.1 Backend unit tests: provider-catalog endpoint (`configured` flags), PATCH persistence of `model` + `system_prompt`, unconfigured-provider accepted at config time, run-time failure audited + isolated.
  - [ ] T6.2 Frontend component tests (Vitest + Testing Library): provider dropdown disables placeholders, model dropdown repopulates on provider change, save posts correct ModelRef, prompt char-count + directive highlight render, context-window warning appears past threshold.
- [ ] **T7 — Verification** (AC: all)
  - [ ] T7.1 `uv run pytest` + `uv run ruff check` green (backend).
  - [ ] T7.2 `npm test` / `vitest` green (frontend).

## Dev Notes

### Scope Boundaries — CRITICAL

**Story 2.3 delivers the Model tab + Prompt tab of the Agent detail shell, plus the backend catalog + persistence to make them work. It does NOT deliver:**
- The Agent CRUD record / RLS / audit-on-CRUD — that is **Story 2.1** (dependency; see below).
- The Agent list, the detail shell, its 6-tab navigation, and the Identity tab — that is **Story 2.2** (dependency; see below).
- Knowledge Base upload/retrieval — **Stories 2.4 / 2.5**. The `{{kb:agent_id}}` directive is only *highlighted* here, not resolved.
- Tool config / `{{tool:...}}` resolution — **Story 2.6**. The `{{tool:...}}` directive is only *highlighted* here.
- Full Orchestrator run wiring / Task dispatch — **Epic 3**. AC9/AC10 only require the run-time failure to be *observable and isolated*, not a full Workflow Run.
- Real OpenAI / Google / Ollama adapters — **future sprints** (they remain placeholders that raise `NotImplementedError`).

### Dependencies (BOTH not yet implemented at baseline)

- **Story 2.1 — Agent CRUD, Identity & Department Scoping** (`sprint-status`: `backlog`): provides the Agent record (`id`, `tenant_id`, `department_id`, `owner_id`, `version`, `system_prompt`, and the `model` field) plus `PATCH /agents/{id}`. This story WRITES to `model` and `system_prompt`. If those fields do not yet exist on the record when this story is implemented, add them + an Alembic migration here.
- **Story 2.2 — Agent List & Detail Shell with Identity Tab** (`sprint-status`: `backlog`): provides the `/agents/$id` detail view with the 6-tab navigation (Identity, Knowledge Base, Tools, API Integrations, Prompt, Model — UX-DR16) and the save/toast/dirty-dot/unsaved-changes conventions this story's two tabs must match. The Model and Prompt tabs slot into that shell.
- **Note:** `backend/app/modules/agent_builder/{models,routes,service}.py` currently exist only as empty docstring stubs at baseline. The concrete Agent record arrives with Story 2.1; coordinate so this story does not duplicate it.

### Architecture Compliance

- **AD-7 — Model Layer is a port; Agent picks provider+model at config time** [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-7, L42-45; binds FR-5, FR-26]. The Agent record stores `{provider, model_name, parameters}` as **data**, matching `ModelRef` exactly:
  ```python
  # backend/app/core/ports/llm.py:43-48
  class ModelRef(BaseModel):
      provider: str        # "anthropic" | "openai" | "google" | "ollama"
      model_name: str      # e.g. "claude-sonnet-4-5"
      parameters: dict[str, Any] = Field(default_factory=dict)
  ```
  Domain code imports only `LlmPort` (`backend/app/core/ports/llm.py`). Provider selection happens at run time from this data — never via a code branch, subclass, or per-provider import in `app/modules/`. Story 1.6's isolation test (`tests/unit/test_llm_port_isolation.py`) is the load-bearing guard; do not violate it.
- **Runtime-configured providers**: The Anthropic adapter (`backend/app/core/adapters/anthropic.py`) is the only real one. It resolves its key lazily from `VAIC_ANTHROPIC_API_KEY` / `ANTHROPIC_API_KEY` and raises `RuntimeError` **at call time** if missing (never at construction). Placeholder adapters (`openai.py`, `google.py`, `ollama.py`) satisfy `LlmPort` structurally and raise `NotImplementedError` from every method. The provider catalog's `configured` flag therefore = (adapter implemented) AND (key present in `Settings`), read from `get_settings()` (`backend/app/core/settings.py:53-59`: `anthropic_api_key`, `openai_api_key`, `google_api_key`, `ollama_base_url`).
- **FR-5 consequence (AC9)**: Do NOT validate provider availability at config time. A user may save `provider: "openai"` even though it is unconfigured; the failure must surface at run time with a clear `audit_trail` message.
- **FR-26 / AD-4 (AC10)**: Per-Agent provider isolation — one bad adapter must not crash another. Audit failures propagate (never swallowed); provider failures are logged, not hidden.
- **UX-DR16 — Agent Builder Surface** [Source: epics.md L233]: 6-tab detail view; this story owns the **Model** tab (provider picker, model picker, parameters) and the **Prompt** tab (system prompt editor). The Model tab also hosts a "live test" affordance per platform-design §3.2.2 (UJ-1 "Pick Claude model, live test", platform-design.md L553) — optional if time-boxed; the ACs do not require it.

### File Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── ports/llm.py                      # READ — ModelRef {provider, model_name, parameters}; LlmPort
│   │   ├── adapters/anthropic.py             # READ — only real adapter; lazy key, RuntimeError at call time
│   │   ├── adapters/{openai,google,ollama}.py# READ — placeholders raising NotImplementedError
│   │   └── settings.py                       # READ/UPDATE — *_api_key fields drive `configured` flags
│   └── modules/
│       └── agent_builder/
│           ├── models.py                     # UPDATE — Agent.model (ModelRef/JSON), Agent.system_prompt (with Story 2.1)
│           ├── routes.py                      # UPDATE — GET providers catalog; PATCH model + system_prompt
│           └── service.py                     # UPDATE — persistence + adapter-selection helper + run-time audit
└── tests/unit/                               # NEW — catalog, PATCH persistence, runtime-failure isolation

frontend/
└── src/
    ├── routes/agents.$id.tsx (or equivalent) # UPDATE — mount Model + Prompt tabs into Story 2.2 shell
    ├── components/agents/ModelTab.tsx        # NEW — provider/model/params
    ├── components/agents/PromptTab.tsx       # NEW — directive-highlight editor + char count + ctx warning
    ├── hooks/useAgentProviders.ts            # NEW — TanStack Query hook over apiFetch
    ├── lib/api.ts                            # READ — apiFetch wrapper (JWT + tenant headers, envelope unwrap)
    └── components/ui/CodeBlock.tsx           # READ — reuse monospace/highlight styling tokens
```
Exact frontend route filename depends on Story 2.2's routing choice — match it rather than inventing a new path.

### Testing

- **Backend**: pytest + ruff (see Story 1.6 for conventions). Mirror `test_one_bad_adapter_does_not_crash_another` for AC10. Assert catalog `configured` reflects settings; assert PATCH round-trips `model`/`system_prompt`; assert an unconfigured provider is accepted at config time but audited on run-time failure.
- **Frontend**: Vitest + Testing Library (see existing `*.test.tsx` under `frontend/src/components`). Test provider-disable, model repopulation, save payload shape, char count, directive highlight, and context-window warning threshold.
- **Stack is pinned** [Source: stack.md] — no web research. Backend: Python 3.13, FastAPI 0.139.x, SQLAlchemy 2.x (sync), Pydantic 2.x, `anthropic` 0.114.0. Frontend: React 19, Vite 8, TypeScript 7.x, Tailwind 4, TanStack Query, Vitest.

### Anti-Patterns to Avoid

1. **Do NOT hard-code the provider/model list in the frontend.** The catalog is a backend contract (T1); the frontend renders what the backend reports so adding a provider needs no frontend edit (FR-5, AD-7).
2. **Do NOT branch on provider in domain/module code.** Store `{provider, model_name, parameters}` as data; let the Model Layer pick the adapter at run time. Never `import` a concrete adapter in `app/modules/`.
3. **Do NOT validate/block unconfigured providers at config time.** Saving `provider: "openai"` must succeed; the failure surfaces at run time in `audit_trail` (AC9, FR-5 consequence).
4. **Do NOT construct the LLM client at config/save time** to "check" a provider — that would move the failure to config time and break AC9. Availability is inferred from settings, not from a live call.
5. **Do NOT swallow provider/audit failures** (AD-4). A failing provider is logged and propagates; it must not crash sibling Agents (AC10).
6. **Do NOT resolve `{{tool:...}}` / `{{kb:...}}` directives here** — they are only highlighted. Resolution is Stories 2.4–2.6.
7. **Do NOT re-implement the save/dirty/toast machinery** — reuse Story 2.2's conventions for the two new tabs.

### References

- [Source: epics.md#Story-2.3 L708-730] Story statement + ACs verbatim (Model tab L717-723, Prompt tab L724-727, run-time failure L728-730).
- [Source: epics.md#Story-2.1 L662-682] Agent record shape + `PATCH /agents/{id}` (dependency).
- [Source: epics.md#Story-2.2 L684-707] Detail shell + 6-tab nav + save/dirty/unsaved conventions (dependency).
- [Source: epics.md L233] UX-DR16 Agent Builder Surface — 6 tabs incl. Prompt + Model.
- [Source: epics.md L302-310] Epic 2 context; consumes `LlmPort`, `McpClientPort`; publishes `AgentProviderPort`.
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-7 L42-45] Model Layer is a port; provider+model at config time.
- [Source: backend/app/core/ports/llm.py:43-48] `ModelRef` shape.
- [Source: backend/app/core/adapters/anthropic.py] Only real adapter; lazy key, RuntimeError at call time.
- [Source: backend/app/core/adapters/{openai,google,ollama}.py] Placeholders raising `NotImplementedError`.
- [Source: backend/app/core/settings.py:53-59] LLM key/URL settings driving `configured`.
- [Source: _bmad-output/implementation-artifacts/1-6-model-layer-port-anthropic-adapter.md] Model Layer + isolation test conventions.
- [Source: platform-design.md L553] UJ-1 "Pick Claude model, live test" → §3.2.2 Model tab (FR-5).
- [Source: frontend/src/lib/api.ts] `apiFetch` wrapper (JWT + tenant headers, envelope unwrap).
- [Source: stack.md] Pinned stack — no web research.

## Change Log

- 2026-07-17: Story 2.3 spec authored. Status: ready-for-dev.
