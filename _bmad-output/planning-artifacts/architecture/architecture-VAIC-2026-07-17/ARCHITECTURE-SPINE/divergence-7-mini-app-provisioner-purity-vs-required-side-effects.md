# Divergence 7 — Mini-App Provisioner Purity vs Required Side Effects

**Severity:** MEDIUM

**Unit A:** `mini_app/provisioner.py` implements the pure function from AD-8: `(tenant_id, department_id, owner_id, valid_schema) -> (namespace + CRUD endpoints + UI)`.

**Unit B:** The same Provisioner must mount FastAPI routes for the CRUD endpoints (`POST /apps/{app_id}/rows`, etc.) and register a frontend route for the UI. Route mounting is a side effect on the FastAPI app object. Frontend route registration requires emitting a route file or updating a route registry.

**AD each obeys:**
- AD-8: "The Provisioner is a pure function."

**Where they diverge:** AD-8 claims purity, but the Provisioner's output includes "CRUD endpoints" and "UI" — both of which require side effects to become real (mounting routes, registering UI components). A builder reading AD-8 literally might implement a function that returns a data structure describing the endpoints and UI, leaving the route mounting to the caller. Another builder might interpret "CRUD endpoints" as the Provisioner actually calling `app.include_router()`. Both are valid readings of AD-8's prose. The first leaves dangling metadata; the second violates purity.

**Proposed fix:** Tighten AD-8 with a clarification.

**Tighten AD-8 — add Clarification:**

> **AD-8 Clarification:** "Pure function" means the Provisioner has no I/O side effects (no DB writes, no HTTP calls, no file system writes, no LLM calls) and produces deterministic output for the same input. It returns a `ProvisioningPlan` dataclass containing: the `mini_app` row to insert, the route registration descriptor, and the UI spec. A separate `mini_app/lifecycle.py` module applies the plan: inserts the row, calls `app.include_router()` for CRUD routes, and emits the UI route descriptor for the frontend. The Provisioner computes; the lifecycle module acts. This preserves the purity invariant while acknowledging that side effects exist in a separate, named component.

---
