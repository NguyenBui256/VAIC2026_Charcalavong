# Divergence 3 — Dual Ownership of `mini_app_rows`: `mini_app` vs `actions`

**Severity:** HIGH

**Unit A:** `mini_app/routes.py` auto-generated CRUD endpoint `PATCH /apps/{app_id}/rows/{row_id}`. Per AD-5 and AD-8, this endpoint writes to `mini_app_rows` with RLS-enforced visibility tiers.

**Unit B:** `actions/bus.py` processes an App Event and, as part of an Event Trigger's Workflow Run, the Orchestrator dispatches a Specialist Agent that calls a Mini-App CRUD endpoint (or writes directly to `mini_app_rows` via the ORM) to update a row as its task output.

**AD each obeys:**
- Unit A: AD-5 (RLS on `mini_app_rows`), AD-8 (Provisioner generated the endpoints).
- Unit B: AD-6 (Task is part of a Run, state machine governed), AD-9 (Event Trigger started the Run via the Action Bus).

**Where they diverge:** Both units write to the same `mini_app_rows` table for the same logical entity, but with different ownership semantics. Unit A is user-driven (a human editing a row). Unit B is agent-driven (a Specialist Agent modifying a row as task output). The spine doesn't say:
1. Whether Specialist Agents may write to `mini_app_rows` directly or must go through the CRUD endpoint.
2. What happens when a user and an Agent concurrently modify the same row (no optimistic concurrency control is specified).
3. Whether the `mini_app` module or the `orchestrator` module owns the write path for agent-initiated row mutations.

If both paths write directly to the table, there is no single owner. If the agent path must go through the CRUD endpoint, then the endpoint is being called from within a background worker (hitting the same contextvar problem from Divergence 1).

**Proposed fix:** Tighten AD-8 and add a Convention row.

**Tighten AD-8 — add Rule:**

> **AD-8 Rule addition:** `mini_app_rows` has exactly one write owner: the `mini_app` module. Specialist Agents and Orchestrator code that need to modify Mini-App rows must call through the `mini_app` module's public service interface (`mini_app.service.update_row`), not the auto-gen HTTP endpoint and not direct ORM writes. This keeps the write path, RLS scoping, and App Event emission in one place.

**New Convention row:**

> **Optimistic concurrency on `mini_app_rows`:** Every `mini_app_rows` update carries `WHERE id = ? AND updated_at = ?` (compare-and-set on the timestamp). A mismatch returns a 409 conflict. This applies to both user-initiated and agent-initiated writes, preventing silent clobber.

---
