# Divergence 6 — Audit Sink Failure Semantics Are Undefined

**Severity:** MEDIUM

**Unit A:** `orchestrator/service.py` completes a decomposition step and calls `audit.log(entry)` per AD-4. Postgres is up; the entry is appended. The Run continues.

**Unit B:** `mini_app/routes.py` processes a row update and calls `audit.log(entry)` per AD-4. Postgres is temporarily down (connection blip, pool exhaustion). `audit.log()` raises a ` psycopg2.OperationalError`.

**AD each obeys:**
- AD-4: "Every Workflow Run step MUST call `audit.log(entry)`." Both call it.

**Where they diverge:** AD-4 says every step must *call* `audit.log()`. It says nothing about what happens when that call fails. Unit A succeeds because Postgres is up. Unit B fails because Postgres is down. The question: does `audit.log()` swallow the error and continue (dropping the audit entry — violating the "MUST call" intent), or does it propagate (crashing the Run — which might be correct for audit but catastrophic for a hackathon demo)?

The convention "Error handling" says "Never swallow. Never return `None` to mean error." By that rule, `audit.log()` propagates, and the Run crashes on any transient DB error during audit. For a demo environment with a 2-day build timeline, this is likely too aggressive.

**Proposed fix:** Tighten AD-4.

**Tighten AD-4 — add Rule:**

> **AD-4 Rule addition (audit failure semantics):** `audit.log()` uses a dedicated DB connection from a separate pool (not the request's transaction). On failure: (1) write the entry to a Redis list `audit_fallback` with TTL 24h, (2) log a `WARNING`, (3) do NOT propagate the exception to the caller. A background arq job (`drain_audit_fallback`) retries entries from the Redis list into Postgres. This trades strict append-only guarantee for Run resilience during transient DB failures. If both Postgres and Redis are down, the entry is lost — acceptable for MVP, logged at `CRITICAL`.

---
