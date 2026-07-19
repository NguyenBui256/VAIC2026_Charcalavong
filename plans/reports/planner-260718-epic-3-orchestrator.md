# Planner report — Epic 3: Workflow Orchestrator & Human-in-the-Loop

## Files produced

- `plans/260718-0052-epic-3-orchestrator/plan.md` — master plan, 8 phases (P1–P8 map to Story 3.1–3.8)
- `plans/260718-0052-epic-3-orchestrator/story-3-1-workflow-crud.md` — full ready-for-dev spec
- `plans/260718-0052-epic-3-orchestrator/story-3-2-run-lifecycle-state-machine.md` — full ready-for-dev spec
- Stories 3.3–3.8 left as briefs inside `plan.md` (per instructions) — each needs expansion into its own artifact before execution.

## Phase count

8 (P1=3.1, P2=3.2 both HARD GATES/foundation; P3=3.3, P4=3.4, P5=3.5, P6=3.6 backend; P7=3.7, P8=3.8 frontend).

## Key dependencies / risks

- **Migration chaining is a moving target.** Epic 2 (Stories 2.6–2.8) is still landing alembic migrations on `rebuild`. Observed head at planning time: `f3a1c9e7b2d4`. Both story specs explicitly instruct the implementer to re-run `uv run alembic heads` at execution time rather than trust any value in these docs.
- **AgentProviderPort dispatch gap (biggest open risk, blocks P3/P4 design).** Story 2.5 published `AgentProviderPort.retrieve()` for KB only. Story 3.4 needs the Orchestrator to dispatch a full Task to a Specialist Agent (run its LlmPort config + optionally Tools via McpClientPort + KB). No existing port covers this. Two options flagged: extend `AgentProviderPort` with `execute_task(...)`, or have `orchestrator.service` call `agent_builder`'s public service interface directly (AD-1-compliant) and orchestrate LlmPort/McpClientPort itself. Not resolved in this plan — needs a decision before P3/P4 detail work.
- **AD-6 compare-and-set + AD-10 tenant-context-across-arq** are the two load-bearing architecture rules for P2; both story specs bake in the exact SQL pattern and the worker-bootstrap-first-statement rule, with a concurrency test as explicit DoD evidence (not optional).
- **Confidence threshold / escalation timeout (FR-11/FR-10 configurability)**: pre-provisioned as columns on `workflows` in Story 3.1's migration (`confidence_threshold`, `escalation_timeout_seconds`) to avoid a follow-up migration in 3.5/3.6 — flagged as a design call, not forced.
- **Escalation timeout sweep (P6)** architecturally duplicates the not-yet-built Epic 5 Schedule Trigger fan-out pattern (AD-10's `cron_jobs` style). Flagged for coordination to avoid rebuilding it twice.
- Do NOT edit `agent_builder/*`, `main.py`'s Epic-2 lines, or Epic-2 migrations — plan instructs additive-only changes to `main.py` and warns to coordinate/rebase on that file.

## Unresolved / Open Questions

1. Does `AgentProviderPort` need a `execute_task`-style extension for Task dispatch, or should the Orchestrator call `agent_builder`'s service layer directly? (blocks P3/P4)
2. Confirm pre-provisioning `confidence_threshold`/`escalation_timeout_seconds` on `workflows` now (Story 3.1) vs. deferring to 3.5/3.6's own migrations.
3. P6's 5-min escalation timeout sweep vs. Epic 5's Schedule Trigger — build once now or coordinate scope later?
4. Confirm whether an `app/workers/`/arq pool skeleton already exists from Epic 1 (Story 3.2 T4.3/T5.1 should reuse it, not duplicate — needs a grep at execution time).
