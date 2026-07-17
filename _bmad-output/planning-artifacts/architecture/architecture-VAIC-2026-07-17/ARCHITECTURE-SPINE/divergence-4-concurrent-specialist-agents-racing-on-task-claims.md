# Divergence 4 — Concurrent Specialist Agents Racing on Task Claims

**Severity:** HIGH

**Unit A:** Specialist Agent "Credit" (running in arq worker thread A) polls `tasks` for `status = 'pending' AND agent_id = 'credit-agent-uuid'` and claims a task.

**Unit B:** Specialist Agent "Credit" (running in arq worker thread B, same or different worker process) polls the same query at the same instant and claims the same task.

**AD each obeys:**
- AD-6: Both use the state machine. AD-6 specifies compare-and-set for `workflow_runs.status`.
- AD-3: Task rows live in the `tasks` Postgres table, claimed and completed by the orchestrator's worker loop.

**Where they diverge:** AD-6 specifies compare-and-set for `workflow_runs.status` transitions but says nothing about `tasks.status` transitions. The `tasks` table has its own status lifecycle (`pending | claimed | completed | failed`), but the spine only governs `workflow_runs.status`. Two concurrent agents can both successfully `UPDATE tasks SET status = 'claimed' WHERE id = ? AND status = 'pending'` — the second update is a no-op, but neither agent checks the row count. Even if they do check, the spine doesn't mandate it, so one builder might implement it and another might not. The agent that "lost" the claim proceeds with stale ownership and writes results to a task it doesn't own.

**Proposed fix:** Tighten AD-6.

**Tighten AD-6 — add Rule:**

> **AD-6 Rule addition:** Task claims use the same compare-and-set pattern as Run transitions: `UPDATE tasks SET status = 'claimed', claimed_at = now() WHERE id = ? AND status = 'pending'`. The caller MUST check `rowcount == 1`; a zero rowcount means another agent claimed it — the agent skips that task. No SELECT-then-UPDATE without the compare-and-set guard.

---
