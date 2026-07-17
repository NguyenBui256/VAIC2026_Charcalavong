---
baseline_commit: 4e2c5ad3cb823b8edb5f8ce6d0ea8b3d94a4fd1c
---

# Story 2.5: Knowledge Base Retrieval at Runtime

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Specialist Agent running inside a Workflow**,
I want **to retrieve cited passages from my Department-scoped Knowledge Base**,
so that **my responses are grounded in bank policy without leaking other Departments' documents**.

## Acceptance Criteria

Verbatim from [epics.md#Story-2.5 L761-771].

1. **AC1 -- `kb_search(agent_id, query)` routes through `McpClientPort`** (epics.md L763-765): Given documents are indexed in DepartmentX's KB (Story 2.4), when runtime code calls the Agent-internal retrieval function `kb_search(agent_id, query)`, then the call routes through `McpClientPort.call_tool("rag.search", {agent_id, query, tenant_id, department_id})` using the Agent's **own** `department_id` (AD-11). The `tenant_id` and `department_id` are ALSO passed as the mandatory keyword-only arguments on `call_tool` (they appear both in the `arguments` payload the MCP server expects and as the port's scope parameters).
2. **AC2 -- Client-side department-scope enforcement raises before the network** (epics.md L766): The `McpClientPort` implementation enforces client-side that the `department_id` parameter matches the calling Agent's `department_id`; a mismatch RAISES (`AuthorizationError`) **before** the request hits the network. VAIC never emits an unscoped or cross-department MCP call.
3. **AC3 -- Result is a list of cited-passage entries** (epics.md L767): The retrieval result is a list of `{passage, document_name, chunk_reference, score}` entries.
4. **AC4 -- Cross-department retrieval yields an empty result set** (epics.md L768-769, FR-2): When a Credit-department Agent attempts a `kb_search` against an HR-department KB, the result set is empty -- never the HR documents. Cross-department isolation is absolute.
5. **AC5 -- Retrieval is logged to `audit_trail` with `type: "kb.retrieval"`** (epics.md L770, FR-21): The retrieval is logged via `audit.log()` with `type: "kb.retrieval"`, `input: {agent_id, query}`, `output: {passage_count, top_score}`.
6. **AC6 -- Retrieval exposed via `AgentProviderPort`** (epics.md L771): The retrieval function is exposed via `AgentProviderPort` so the Orchestrator (Epic 3) can dispatch retrieval Tasks to Specialist Agents.

## Tasks / Subtasks

- [ ] **T1 -- Write failing tests (RED phase)** (AC: all)
  - [ ] T1.1 `tests/unit/test_kb_retrieval.py` -- `kb_search` builds the correct `call_tool("rag.search", {...})` payload with `agent_id`, `query`, `tenant_id`, `department_id`; result mapping to `{passage, document_name, chunk_reference, score}` entries (AC1, AC3)
  - [ ] T1.2 `tests/unit/test_kb_retrieval.py` -- department-scope mismatch RAISES `AuthorizationError` **before** any network/`call_tool` dispatch (assert the fake MCP client's `call_tool` was never awaited) (AC2)
  - [ ] T1.3 `tests/unit/test_kb_retrieval.py` -- **cross-department empty-result test**: a Credit-department Agent querying an HR-scoped KB returns an empty passage list, never HR docs (AC4, FR-2)
  - [ ] T1.4 `tests/unit/test_kb_retrieval.py` -- retrieval calls `audit.log()` exactly once with `type="kb.retrieval"`, `input={agent_id, query}`, `output={passage_count, top_score}`; verify `passage_count`/`top_score` computed from the mapped results (empty result -> `passage_count=0`, `top_score` null/0.0) (AC5)
  - [ ] T1.5 `tests/unit/test_ports.py` (extend) -- `AgentProviderPort` is a `typing.Protocol` with `@runtime_checkable`; exposes the retrieval method with the expected signature (AC6)
  - [ ] T1.6 `tests/unit/test_ports.py` (extend) -- structural compliance: a fake implementation satisfies `isinstance(fake, AgentProviderPort)`
- [ ] **T2 -- Define `AgentProviderPort`** (AC: #6)
  - [ ] T2.1 `app/core/ports/agent_provider.py` -- NEW file. `AgentProviderPort(Protocol)` with `@runtime_checkable`; declares the retrieval capability the Orchestrator dispatches to (e.g. `async def retrieve(agent_id, query, *, tenant_id, department_id, top_k=5) -> list[RetrievalPassage]`). Mirror the AD-11 keyword-only `tenant_id` + `department_id` convention used by `McpClientPort`/`DocIntakePort`.
  - [ ] T2.2 Define a `RetrievalPassage` Pydantic model with exact fields `{passage, document_name, chunk_reference, score}` (AC3). Reuse/align with `RetrievalResult` shape in `doc_intake.py` where sensible.
  - [ ] T2.3 `app/core/ports/__init__.py` -- update docstring/exports to include `AgentProviderPort`.
- [ ] **T3 -- Implement the runtime retrieval function** (AC: #1, #2, #3, #4, #5)
  - [ ] T3.1 `app/modules/agent_builder/kb_retrieval.py` (NEW) -- `kb_search(agent_id, query, ...)` Agent-internal retrieval function. Loads the Agent record (Story 2-1) to obtain the Agent's own `tenant_id` + `department_id`; NEVER accepts a caller-supplied department that overrides it.
  - [ ] T3.2 Build the MCP payload `{"agent_id": ..., "query": ..., "tenant_id": ..., "department_id": ...}` and call `McpClientPort.call_tool("rag.search", payload, tenant_id=<agent's>, department_id=<agent's>)` (AC1).
  - [ ] T3.3 Rely on `McpClientPort`'s client-side AD-11 check to RAISE on mismatch before the network; the retrieval function does not duplicate the network call but MUST surface the raise (do not swallow) (AC2).
  - [ ] T3.4 Map `ToolResult.output` into a list of `RetrievalPassage` `{passage, document_name, chunk_reference, score}`; an empty/absent result maps to `[]` (AC3, AC4).
  - [ ] T3.5 Emit `audit.log(AuditEntry(type="kb.retrieval", input={agent_id, query}, output={passage_count, top_score}, ...))` after retrieval (AC5). Compute `passage_count = len(results)` and `top_score = max(score) or None/0.0` for empty.
  - [ ] T3.6 Wire `kb_search` as the concrete implementation behind `AgentProviderPort.retrieve` so the Orchestrator (Epic 3) can dispatch to it (AC6).
- [ ] **T4 -- Run full suite (GREEN)** (AC: all)
  - [ ] T4.1 `uv run pytest -v` -- all new + existing tests green
  - [ ] T4.2 `uv run ruff check app tests` -- clean
  - [ ] T4.3 Function size ceiling check -- no function exceeds 50 lines
- [ ] **T5 -- Definition of Done evidence** (AC: all)
  - [ ] T5.1 Test evidence: cite the passing cross-department empty-result test and the pre-network-raise test by file:line
  - [ ] T5.2 Production code reference: `app/core/ports/agent_provider.py`, `app/modules/agent_builder/kb_retrieval.py`

## Dev Notes

### Scope Boundaries -- CRITICAL

**Story 2.5 delivers the runtime retrieval path and the `AgentProviderPort` interface. This is a backend / runtime story -- NO new UI tab.**

Do:
- Define `AgentProviderPort` (deferred from Story 1.4 -- see below).
- Implement the Agent-internal `kb_search(agent_id, query)` runtime function.
- Route retrieval through `McpClientPort.call_tool("rag.search", ...)` with AD-11 scope.
- Log every retrieval to `audit_trail` via the audit sink.

Do NOT:
- Build any Knowledge Base UI (upload/list UI is Story 2.4; there is no retrieval tab).
- Implement the parallel-team MCP **server** or the real `rag.search` tool -- VAIC is a client only (AD-3). Depend on the `McpClientPort` adapter / stub.
- Implement the Orchestrator dispatch loop (Epic 3) -- only EXPOSE retrieval via `AgentProviderPort`.
- Re-implement document indexing/ingestion -- that is Story 2.4 (`DocIntakePort.ingest`).

### Dependencies -- CRITICAL

- **Story 2-4 (Knowledge Base Upload & Storage)** -- documents must be chunked, embedded, and indexed (via `McpClientPort` / `DocIntakePort.ingest`) before retrieval returns anything. Retrieval against an un-indexed KB yields an empty set (which is also the correct cross-department behavior, so tests must distinguish "empty because wrong department" from "empty because nothing indexed"). NOTE: Story 2-4 has no story file yet at baseline; confirm its delivered shape before implementing.
- **Story 2-1 (Agent record -> `department_id`)** -- `kb_search` derives the Agent's own `tenant_id` + `department_id` from the Agent record. At baseline `backend/app/modules/agent_builder/models.py` is an empty placeholder (only a module docstring). The Agent model with `department_id` is delivered by Story 2-1; this story depends on that field existing. Do NOT invent a competing Agent model.

### Architecture Compliance

- **AD-11 (Client-side department scope on MCP)** -- The single most important invariant for this story. Every MCP call carries `tenant_id` + `department_id`. The `McpClientPort` implementation verifies client-side that `department_id` matches the calling Agent's department and **RAISES before the network** on mismatch. `kb_search` MUST derive scope from the Agent record itself, never from a caller-supplied argument that could be spoofed. [Source: backend/app/core/ports/mcp_client.py L7-11, L38-62]
- **AD-3 (MCP client)** -- VAIC is an MCP client. `rag.search` is owned by the parallel-team MCP server; it is invoked via `McpClientPort.call_tool("rag.search", ...)`. Do not build the server. [Source: backend/app/core/ports/mcp_client.py L1-11]
- **FR-2 (Cross-department isolation)** -- A wrong-department retrieval returns an EMPTY result set, never another department's documents. This is enforced twice: (1) the pre-network AD-11 raise on explicit mismatch, and (2) the MCP server scoping the index by `department_id` so a legitimate-but-empty scope yields `[]`. The cross-department empty-result test is mandatory. [Source: backend/app/core/ports/doc_intake.py L5-8, L80-82; epics.md L768-769]
- **AD-4 (Single audit sink, append-only)** -- Retrieval logging goes through the audit sink only (`PostgresAuditSink.log` at `backend/app/core/adapters/audit_postgres.py:71`, implementing `AuditPort`). `type: "kb.retrieval"`. Never write `audit_trail` directly. [Source: backend/app/core/ports/audit.py L1-12]
- **AD-1 (Hexagonal)** -- `AgentProviderPort` is a Protocol in `core/ports/`; the retrieval implementation lives in `modules/agent_builder/`. Domain logic depends on ports, not adapters.
- **AgentProviderPort was DEFERRED in Story 1.4** -- Story 1.4 explicitly deferred `AgentProviderPort` (see `1-4-...md` L68: "AgentProviderPort, WorkflowRunPort, MiniAppProvisionerPort, TriggerRegistryPort -- deferred"). Therefore **no `agent_provider.py` port file exists at baseline** and this story must CREATE it. Follow the established port conventions: `typing.Protocol`, `@runtime_checkable`, Pydantic models, keyword-only `tenant_id`/`department_id`. [Source: backend/app/core/ports/mcp_client.py, doc_intake.py, audit.py as pattern references]
- **Function size**: keep all functions under 50 lines (project convention, per Story 1.4 DoD).

### Design Decisions / Guidance

1. **Two ports touch retrieval -- pick per the epic.** `DocIntakePort.retrieve(agent_id, query, *, tenant_id, department_id, top_k=5)` already exists (`doc_intake.py` L69-83) and models the same capability. However, epics.md L765 is explicit that runtime retrieval routes through `McpClientPort.call_tool("rag.search", {...})`. Implement AC1 as the `McpClientPort.call_tool` path. If a shared adapter already fulfils `DocIntakePort.retrieve` via the same `rag.search` call, `kb_search` may delegate to it -- but the observable behavior in AC1 (the `call_tool("rag.search", ...)` invocation) must hold. Flag any reconciliation as an open question rather than silently choosing.
2. **Scope is derived, not passed.** `kb_search(agent_id, query)` takes only `agent_id` + `query` from the caller. It looks up the Agent record to get `tenant_id` + `department_id`. This is what makes AC4 airtight: a caller cannot request another department's KB because it cannot supply the department.
3. **The mismatch case (AC2) vs. the empty case (AC4) are different.** AC2 is an explicit `department_id` mismatch -> `AuthorizationError` raised before the network. AC4 is a legitimate call whose scope simply has no matching documents -> empty list, no raise. Tests must cover both distinctly.
4. **Audit output aggregates, not passages.** `output` carries `{passage_count, top_score}` only -- never the passage text (keeps `audit_trail` lean and avoids logging document content). `input` carries `{agent_id, query}`.
5. **`RetrievalPassage` field names are load-bearing.** Exact keys `{passage, document_name, chunk_reference, score}` per AC3 -- downstream Orchestrator/citations depend on them. Do not rename.

### File Structure Changes

```
backend/
├── app/
│   ├── core/
│   │   └── ports/
│   │       ├── __init__.py                 # UPDATED -- export AgentProviderPort
│   │       └── agent_provider.py           # NEW -- AgentProviderPort(Protocol) + RetrievalPassage
│   └── modules/
│       └── agent_builder/
│           └── kb_retrieval.py             # NEW -- kb_search() runtime retrieval function
└── tests/
    └── unit/
        ├── test_kb_retrieval.py            # NEW -- payload, pre-network raise, cross-dept empty, audit
        └── test_ports.py                   # UPDATED -- AgentProviderPort protocol + structural checks
```

Reference (unchanged, cited): `backend/app/core/ports/mcp_client.py`, `backend/app/core/ports/doc_intake.py`, `backend/app/core/ports/audit.py`, `backend/app/core/adapters/audit_postgres.py`, `backend/app/modules/agent_builder/models.py` (Story 2-1 Agent model).

### Testing

- Framework: `pytest` + `uv run pytest` (backend convention, per Story 1.4).
- Use fakes for `McpClientPort` and `AuditPort` -- do NOT hit a real MCP server (AD-3: server is another team's).
- **Mandatory cross-department empty-result test** (AC4/FR-2): construct a Credit-department Agent, invoke `kb_search` such that only HR-scoped documents exist, assert the returned passage list is empty and contains none of the HR document names.
- **Pre-network raise test** (AC2): assert that on an explicit department mismatch the fake `call_tool` is never awaited and an `AuthorizationError` propagates.
- **Audit test** (AC5): assert `audit.log()` called once with the exact `type`, `input`, and `output` shape, including `passage_count=0` / null `top_score` for the empty case.
- **Protocol tests** (AC6): extend `test_ports.py` with `@runtime_checkable` isinstance + signature checks matching the Story 1.4 pattern.
- Keep tests deterministic; no network, no sleep.

### Anti-Patterns to Avoid

1. **Do NOT accept a caller-supplied `department_id` in `kb_search`.** Derive it from the Agent record. Accepting it reopens the FR-2 leak.
2. **Do NOT swallow the AD-11 mismatch raise.** AC2 requires it to propagate before the network -- catching it and returning `[]` violates the "raise before network" contract and hides misconfiguration.
3. **Do NOT build the MCP server or a real `rag.search`.** VAIC is a client (AD-3); use the `McpClientPort` adapter/stub.
4. **Do NOT write `audit_trail` directly.** Only via the audit sink (`AuditPort.log`) -- AD-4.
5. **Do NOT log passage text.** `output` is `{passage_count, top_score}` only.
6. **Do NOT make `AgentProviderPort` a concrete class.** It must be `typing.Protocol` + `@runtime_checkable` so the Orchestrator can depend on the interface (Epic 3) without inheritance.
7. **Do NOT add a UI tab.** Runtime/backend story only.
8. **Do NOT rename `RetrievalPassage` fields.**

### References

- [Source: epics.md#Story-2.5 L755-771] ACs verbatim
- [Source: epics.md#Story-2.4 L732-753] KB upload/index dependency (Story 2-4)
- [Source: backend/app/core/ports/mcp_client.py L7-11, L43-62] `McpClientPort.call_tool` shape + AD-11 client-side scope raise-before-network
- [Source: backend/app/core/ports/doc_intake.py L39-44, L69-83] `RetrievalResult`, `DocIntakePort.retrieve`, empty-on-wrong-department
- [Source: backend/app/core/ports/audit.py L23-68] `AuditEntry` FR-21 fields, `AuditPort.log`
- [Source: backend/app/core/adapters/audit_postgres.py:55-82] `PostgresAuditSink` -- the only audit writer (AD-4)
- [Source: _bmad-output/implementation-artifacts/1-4-core-ports-api-error-envelope.md L68] AgentProviderPort explicitly deferred -> this story creates it
- [Source: _bmad-output/implementation-artifacts/1-4-core-ports-api-error-envelope.md L17, L81-83] Port conventions: Protocol, @runtime_checkable, AD-11 keyword-only params
- [Source: ARCHITECTURE-SPINE/structural-seed.md L15-16, L33-40] Module paths: `modules/agent_builder/`, `core/ports/`
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-11] Client-side department scope on MCP
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-3] MCP client
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-4] Single audit sink, append-only
- [Source: ARCHITECTURE-SPINE/stack.md L16] `mcp` Python SDK v1.x (MCP client)
- [Source: prd FR-2] Cross-department Knowledge Base isolation
- [Source: prd FR-21] Per-step audit trail logging

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-07-17: Story 2.5 spec authored by story-context engine. Status: ready-for-dev.
