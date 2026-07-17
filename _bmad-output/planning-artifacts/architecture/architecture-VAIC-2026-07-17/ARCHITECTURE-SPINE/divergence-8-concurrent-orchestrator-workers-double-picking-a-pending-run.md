# Divergence 8 — Concurrent Orchestrator Workers Double-Picking a `pending` Run

**Severity:** MEDIUM

**Unit A:** arq worker process 1 starts, polls for `pending` Runs, finds `run_id = abc`, transitions it to `running` via `UPDATE ... WHERE id = 'abc' AND status = 'pending'`.

**Unit B:** arq worker process 2 starts at the same time (e.g., both processes recover from a Redis restart), polls for `pending` Runs, finds the same `run_id = abc` before worker 1's transaction commits, and attempts the same transition.

**AD each obeys:**
- AD-6: Both use compare-and-set: `UPDATE ... WHERE id = ? AND status = ?`. AD-6 explicitly specifies this.

**Where they diverge:** AD-6 specifies the compare-and-set pattern, which is correct. But it doesn't address the **visibility** problem. If worker 1's transaction hasn't committed when worker 2 reads, worker 2 sees the row as still `pending` (depending on isolation level). At `READ COMMITTED` (Postgres default), worker 2's `UPDATE` will block on the row lock until worker 1 commits, then see `rowcount = 0` because the status is no longer `pending`. This is actually fine — *if* the worker checks `rowcount`. But AD-6 doesn't mandate checking `rowcount`. A builder could implement the UPDATE and then proceed to run the workflow regardless of whether the claim succeeded.

This is less severe than Divergence 4 because Postgres' row locking provides some protection, but the spine should be explicit.

**Proposed fix:** Tighten AD-6 (same addition as Divergence 4, generalized).

**Tighten AD-6 — add Rule:**

> **AD-6 Rule addition (claim verification):** Every compare-and-set transition MUST verify `rowcount == 1` before proceeding. A zero `rowcount` means the claim failed (another worker owns it); the caller must abandon the operation. This applies to both `workflow_runs.status` and `tasks.status` transitions. No transition consumer may proceed without verifying the claim.

---
