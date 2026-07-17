---
baseline_commit: 9ad9a118ddae0027006eb8a296792fe98d4282c9
---

# Story 1.4: Core Ports & API Error Envelope

Status: review

## Story

As a **backend developer on any downstream stream**,
I want **all hexagonal port interfaces defined and a consistent API error envelope**,
so that **I can develop my module against stable contracts without waiting for other modules**.

## Acceptance Criteria

1. **AC1 -- Every port is a Protocol**: `LlmPort`, `AuditPort`, `McpClientPort`, `ToolPort`, `DocIntakePort`, `SandboxPort` are `typing.Protocol` subclasses with `@runtime_checkable`, not concrete classes.
2. **AC2 -- LlmPort exposes complete, stream, embed**: Per AD-7, `LlmPort` declares `complete`, `stream` (async), and `embed` with correct signatures and Pydantic models (`Message`, `ModelRef`, `CompletionResult`, `StreamChunk`, `EmbeddingResult`).
3. **AC3 -- AuditPort.log signature matches PRD FR-21**: `AuditEntry` carries exact fields `{run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}`. `AuditPort.log(entry: AuditEntry) -> None`.
4. **AC4 -- McpClientPort REQUIRES tenant_id + department_id on EVERY method**: Per AD-11, every method signature includes `tenant_id` and `department_id` parameters. Enforced via signature inspection in test.
5. **AC5 -- DomainError raised in a route produces the envelope**: Response body is `{error: {code, message, details, trace_id}}`, status code matches `.http_status`.
6. **AC6 -- Unhandled Exception produces 500 envelope**: Response body is envelope with code `"internal_error"`, status 500, no stack trace leaked.
7. **AC7 -- Every error response includes trace_id as UUID v7**: `trace_id` is present in every error response body and is a valid UUID v7 (version nibble = 7).
8. **AC8 -- HTTP status code mapping**: `ValidationError`->400, `NotFoundError`->404, `AuthenticationError`->401, `AuthorizationError`->403, `ConflictError`->409, `RateLimitError`->429, `UpstreamError`->502, `MissingTenantContextError`->500.
9. **AC9 -- X-Trace-Id response header**: `trace_id` is also set as the `X-Trace-Id` response header on every error response.
10. **AC10 -- ToolPort, DocIntakePort, SandboxPort defined**: All three are Protocols with correct method signatures per structural-seed.md and consistency-conventions.md.

## Tasks / Subtasks

- [x] **T1 -- Write failing tests (RED phase)** (AC: all)
  - [x] T1.1 `tests/unit/test_errors.py` -- DomainError hierarchy, ErrorEnvelope shape, TraceIdContext ContextVar, new_trace_id UUID v7
  - [x] T1.2 `tests/unit/test_ports.py` -- Protocol checks, LlmPort methods, AuditEntry FR-21 fields, McpClientPort tenant_id+department_id enforcement, structural compliance for all 6 ports
  - [x] T1.3 `tests/integration/test_error_envelope.py` -- FastAPI error responses: status codes, envelope shape, trace_id UUID v7, X-Trace-Id header, unhandled exception 500, success path unaffected
- [x] **T2 -- Implement error envelope** (AC: #5, #6, #7, #8, #9)
  - [x] T2.1 `app/core/errors.py`: `DomainError` base class with `.code`, `.message`, `.details`, `.http_status`
  - [x] T2.2 Subclasses: `ValidationError` (400), `NotFoundError` (404), `AuthenticationError` (401), `AuthorizationError` (403), `ConflictError` (409), `RateLimitError` (429), `UpstreamError` (502), `MissingTenantContextError` (500)
  - [x] T2.3 `ErrorEnvelope(BaseModel)` with `{code, message, details, trace_id}`
  - [x] T2.4 `TraceIdContext` ContextVar + `new_trace_id()` (UUID v7) + `get_trace_id()`
  - [x] T2.5 `register_error_handlers(app)` -- FastAPI exception handlers for `DomainError` and `Exception`
  - [x] T2.6 `_build_error_response()` -- builds JSONResponse with `{error: {...}}` body and `X-Trace-Id` header
- [x] **T3 -- Implement port interfaces** (AC: #1, #2, #3, #4, #10)
  - [x] T3.1 `app/core/ports/llm.py` -- `LlmPort(Protocol)` with `complete`, `stream`, `embed`; models: `Message`, `ModelRef`, `CompletionResult`, `StreamChunk`, `EmbeddingResult`
  - [x] T3.2 `app/core/ports/audit.py` -- `AuditPort(Protocol)` with `log(entry: AuditEntry) -> None`; `AuditEntry` with FR-21 fields
  - [x] T3.3 `app/core/ports/mcp_client.py` -- `McpClientPort(Protocol)` with `call_tool` + `list_tools`, both requiring `tenant_id` + `department_id` (AD-11)
  - [x] T3.4 `app/core/ports/tool.py` -- `ToolPort(Protocol)` unifying MCP + embedded Python tools with `invoke`
  - [x] T3.5 `app/core/ports/doc_intake.py` -- `DocIntakePort(Protocol)` with `ingest` + `retrieve`, both requiring `tenant_id` + `department_id`
  - [x] T3.6 `app/core/ports/sandbox.py` -- `SandboxPort(Protocol)` with `run(code, stdin, timeout_s=10, memory_mb=128)` per consistency-conventions.md
  - [x] T3.7 `app/core/ports/__init__.py` -- updated docstring
- [x] **T4 -- Wire into main.py** (AC: #5, #6)
  - [x] T4.1 `app/main.py` -- call `register_error_handlers(app)` after FastAPI app creation, before routes. Existing `/health` and `/ready` untouched.
- [x] **T5 -- Run full suite (GREEN)** (AC: all)
  - [x] T5.1 `uv run pytest -v` -- **74 passed** in 2.62s (18 existing + 56 new)
  - [x] T5.2 `uv run ruff check app tests alembic` -- **All checks passed!**
  - [x] T5.3 Function size ceiling check -- no function exceeds 50 lines
- [x] **T6 -- Definition of Done evidence** (AC: all)
  - [x] T6.1 Test evidence: `tests/integration/test_error_envelope.py:88` test_domain_error_returns_correct_status_and_envelope PASSED
  - [x] T6.2 Production code reference: `backend/app/core/errors.py:75-102` (DomainError), `backend/app/core/ports/llm.py:73-105` (LlmPort), `backend/app/core/ports/audit.py:46-53` (AuditPort), `backend/app/core/ports/mcp_client.py:35-74` (McpClientPort)

## Dev Notes

### Scope Boundaries -- CRITICAL

**Story 1.4 delivers interfaces and the error envelope only. Do NOT implement:**
- AuditPort concrete adapter (the `audit_trail` table + `sink.py`) -- **Story 1.5**
- LlmPort concrete adapters (`anthropic.py`, `openai.py`, etc.) -- **Story 1.6**
- McpClientPort concrete adapter -- **future epic**
- Auth middleware / JWT / tenant_context population -- **Story 1.3**
- AgentProviderPort, WorkflowRunPort, MiniAppProvisionerPort, TriggerRegistryPort -- **deferred** (the scope instruction lists only LlmPort, AuditPort, McpClientPort, ToolPort, DocIntakePort, SandboxPort)
- Frontend changes -- out of scope

### Design Decisions

1. **`ErrorEnvelope` is flat, not nested**: The `ErrorEnvelope` Pydantic model has flat fields (`code`, `message`, `details`, `trace_id`). The `_build_error_response()` function wraps it in `{"error": <envelope>}` to produce the full response body `{error: {code, message, details, trace_id}}`. This makes the model easy to construct and test while maintaining the exact API contract.

2. **`TraceIdContext` uses the same `uuid7()` from `app.core.ids`**: Per AR-14, trace_ids are UUID v7 (time-ordered). The `get_trace_id()` function lazily generates and stores a trace_id if none exists, so it works even without middleware setting one.

3. **Exception handler ordering**: `DomainError` handler is registered before `Exception` handler. FastAPI/Starlette matches the most specific handler first, so `DomainError` subclasses are caught by the domain handler, not the catch-all.

4. **`TestClient(raise_server_exceptions=False)`**: Used in integration tests so the `Exception` handler can return a 500 response instead of re-raising in the test process.

5. **Protocol `@runtime_checkable`**: All ports use `@runtime_checkable` so `isinstance(fake_impl, Port)` works for structural compliance tests. This checks method existence but not signatures; signature compliance is verified separately via `inspect.signature()` for McpClientPort's AD-11 requirement.

6. **McpClientPort has `call_tool` and `list_tools`**: Both methods require `tenant_id` and `department_id` as keyword-only arguments. The AD-11 enforcement (client-side mismatch check) is the adapter's responsibility (future epic); the port interface enforces the parameter presence.

### Architecture Compliance

- **AD-1 (Hexagonal)**: Ports are Protocols in `core/ports/`; adapters will be in `core/adapters/`. Domain logic never imports adapter code.
- **AD-3 (MCP client)**: `McpClientPort` is the abstraction for tool invocation; VAIC is a client only.
- **AD-4 (Audit append-only)**: `AuditPort.log()` is the only path to write `audit_trail`. The Protocol signature enforces the exact FR-21 field shape.
- **AD-7 (Model Layer port)**: `LlmPort` abstracts LLM providers; Agent config stores `{provider, model_name, parameters}` as data.
- **AD-11 (Department scope on MCP)**: Every `McpClientPort` method requires `tenant_id` + `department_id`.
- **AR-14 (Error shape)**: Every API error is `{error: {code, message, details, trace_id}}`.
- **Function size**: All functions under 50 lines (verified).

### File Structure Changes

```
backend/
├── app/
│   ├── core/
│   │   ├── errors.py                      # POPULATED -- DomainError, ErrorEnvelope, handlers
│   │   └── ports/
│   │       ├── __init__.py                # UPDATED -- docstring
│   │       ├── llm.py                     # NEW -- LlmPort + models
│   │       ├── audit.py                   # NEW -- AuditPort + AuditEntry
│   │       ├── mcp_client.py              # NEW -- McpClientPort + ToolResult
│   │       ├── tool.py                    # NEW -- ToolPort + models
│   │       ├── doc_intake.py              # NEW -- DocIntakePort + models
│   │       └── sandbox.py                 # NEW -- SandboxPort + SandboxResult
│   └── main.py                            # UPDATED -- register_error_handlers(app)
└── tests/
    ├── unit/
    │   ├── test_errors.py                 # NEW -- 18 tests
    │   └── test_ports.py                  # NEW -- 26 tests
    └── integration/
        └── test_error_envelope.py         # NEW -- 12 tests
```

### Anti-Patterns to Avoid

1. **Do NOT implement concrete adapters.** Story 1.4 delivers interfaces only.
2. **Do NOT leak stack traces.** The `Exception` handler returns a generic message; the full traceback goes to `logger.exception()` server-side only.
3. **Do NOT use `uuid.uuid4()` for trace_ids.** AR-14 mandates UUID v7 (time-ordered). Use `uuid7()` from `app.core.ids`.
4. **Do NOT put domain logic in ports.** Ports are pure interface definitions; no implementation, no side effects.
5. **Do NOT make ports concrete classes.** They must be `typing.Protocol` for structural typing, so any module can satisfy them without inheritance.

### References

- [Source: epics.md#Story-1.4 L449-466] ACs verbatim
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-1] Hexagonal modular monolith
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-3] MCP client protocol
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-4] Single audit sink, append-only
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-7] Model Layer is a port
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-11] Client-side department scope on MCP
- [Source: ARCHITECTURE-SPINE/consistency-conventions.md] Error shape, audit entry shape, API envelope
- [Source: ARCHITECTURE-SPINE/structural-seed.md] Exact file paths for ports
- [Source: prd-VAIC-2026-07-17/prd/4-features.md#FR-3] Per-Agent Tool configuration
- [Source: prd-VAIC-2026-07-17/prd/4-features.md#FR-5] Per-Agent Model selection
- [Source: prd-VAIC-2026-07-17/prd/4-features.md#FR-21] Per-step Audit Trail logging
- [Source: prd-VAIC-2026-07-17/prd/4-features.md#FR-26] Model Layer (provider-agnostic)
- [Source: prd-VAIC-2026-07-17/prd/a5-app-event-envelope-referenced-by-fr-17-fr-19.md] API envelope reference

## Dev Agent Record

### Agent Model Used

Claude (via Claude Code, glm-5.2[1m] backend session)

### Debug Log References

- **Worktree rebased onto main (9ad9a11)**: The worktree branched from f72229b (Story 1.1). Rebased onto main to get Story 1.2's `db.py`, `settings.py`, `ids.py`, and tenant models. No conflicts.
- **ContextVar pollution across tests**: Initial test run showed trace_id as UUID v4 in integration tests because the unit test `test_trace_id_context_set_and_get` set a `uuid.uuid4()` into `TraceIdContext` without resetting. Fixed by adding proper `try/finally` with `TraceIdContext.reset(token)` in unit tests.
- **`runtime_checkable` Protocol `isinstance` checks method names only**: `isinstance(fake, Protocol)` verifies method existence but not signatures. The fake implementations for `McpClientPort` and `DocIntakePort` initially only implemented one of two methods. Fixed by implementing all Protocol methods in fakes.
- **`TestClient` default `raise_server_exceptions=True`**: The unhandled `Exception` handler test failed because Starlette re-raises in the test process. Fixed by using `TestClient(app, raise_server_exceptions=False)`.
- **`ErrorEnvelope` model shape**: Initially implemented as nested `{error: ErrorPayload}`. Changed to flat fields with the wrapper applied in `_build_error_response()` for easier construction and testing.
- **74/74 tests green** in 2.62s; ruff clean; no function exceeds 50 lines.

### Completion Notes List

- **AC1 ✅**: All 6 ports (`LlmPort`, `AuditPort`, `McpClientPort`, `ToolPort`, `DocIntakePort`, `SandboxPort`) are `typing.Protocol` with `@runtime_checkable`. Proven by `test_*_is_protocol` tests.
- **AC2 ✅**: `LlmPort` declares `complete`, `stream` (async), `embed`. Models: `Message`, `ModelRef`, `CompletionResult`, `StreamChunk`, `EmbeddingResult`. Proven by `test_llm_port_has_*` tests.
- **AC3 ✅**: `AuditEntry` has exact FR-21 fields `{run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}`. `AuditPort.log(entry: AuditEntry) -> None`. Proven by `test_audit_entry_has_fr21_fields`.
- **AC4 ✅**: `McpClientPort.call_tool` and `list_tools` both accept `tenant_id` + `department_id` as keyword-only args. Proven by `test_mcp_client_port_call_tool_requires_tenant_and_department` (signature inspection).
- **AC5 ✅**: DomainError in route produces `{error: {code, message, details, trace_id}}`, status matches `.http_status`. Proven by `test_domain_error_returns_correct_status_and_envelope` (8 parametrized cases).
- **AC6 ✅**: Unhandled Exception returns 500 with code `"internal_error"`, no stack trace. Proven by `test_unhandled_exception_returns_500_internal_error`.
- **AC7 ✅**: `trace_id` is UUID v7 in every error response. Proven by `_assert_trace_id_is_uuid_v7` assertion in multiple tests.
- **AC8 ✅**: HTTP status mapping: ValidationError->400, NotFoundError->404, AuthenticationError->401, AuthorizationError->403, ConflictError->409, RateLimitError->429, UpstreamError->502, MissingTenantContextError->500. Proven by parametrized test.
- **AC9 ✅**: `X-Trace-Id` header set on every error response. Proven by `test_trace_id_in_response_header`.
- **AC10 ✅**: `ToolPort.invoke`, `DocIntakePort.ingest`+`retrieve`, `SandboxPort.run` all defined as Protocol methods. Proven by `test_*_has_*` and `test_*_structural_compliance` tests.
- **Scope discipline**: No concrete adapters, no audit table, no LLM adapter, no auth middleware, no frontend changes.
- **DoD**: test evidence (`tests/integration/test_error_envelope.py:88` PASSED, 74 tests in 2.62s), production code reference (`backend/app/core/errors.py`, `backend/app/core/ports/`).

### File List

**Created (new):**
- `backend/app/core/ports/llm.py` -- `LlmPort(Protocol)` with `complete`, `stream`, `embed`; Pydantic models `Message`, `ModelRef`, `CompletionResult`, `StreamChunk`, `EmbeddingResult`
- `backend/app/core/ports/audit.py` -- `AuditPort(Protocol)` with `log(entry) -> None`; `AuditEntry` with FR-21 fields
- `backend/app/core/ports/mcp_client.py` -- `McpClientPort(Protocol)` with `call_tool` + `list_tools`, both requiring `tenant_id` + `department_id` (AD-11)
- `backend/app/core/ports/tool.py` -- `ToolPort(Protocol)` with `invoke`; models `ToolInvocation`, `ToolOutput`
- `backend/app/core/ports/doc_intake.py` -- `DocIntakePort(Protocol)` with `ingest` + `retrieve`; models `DocumentInput`, `IngestResult`, `RetrievalResult`
- `backend/app/core/ports/sandbox.py` -- `SandboxPort(Protocol)` with `run`; model `SandboxResult`
- `backend/tests/unit/test_errors.py` -- 18 tests: DomainError hierarchy, ErrorEnvelope shape, TraceIdContext, UUID v7
- `backend/tests/unit/test_ports.py` -- 26 tests: Protocol checks, method existence, structural compliance, FR-21 fields, AD-11 enforcement
- `backend/tests/integration/test_error_envelope.py` -- 12 tests: FastAPI error responses, status codes, trace_id, X-Trace-Id header, unhandled exception
- `backend/.env.example` -- environment variable documentation

**Modified (existing):**
- `backend/app/core/errors.py` -- populated from placeholder: `DomainError` hierarchy, `ErrorEnvelope`, `TraceIdContext`, `register_error_handlers()`
- `backend/app/core/ports/__init__.py` -- updated docstring
- `backend/app/main.py` -- added `register_error_handlers(app)` call after app creation

## Change Log

- 2026-07-17: Story 1.4 spec authored. Status: ready-for-dev -> in-progress.
- 2026-07-17: Story 1.4 implementation complete -- 74/74 tests green, ruff clean. Status: in-progress -> review.
