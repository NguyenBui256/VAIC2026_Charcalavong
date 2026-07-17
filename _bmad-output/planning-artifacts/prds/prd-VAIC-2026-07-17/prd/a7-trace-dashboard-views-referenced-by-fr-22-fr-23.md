# A7. Trace Dashboard Views (referenced by FR-22, FR-23)

Two alternate views over the same Audit Trail:

- **Timeline view (FR-22):** vertical list of step cards. Each card: `{step_id, agent, type, latency_ms, expand → {input, output, model}}`. Default view.
- **Collaboration graph view (FR-23):** Orchestrator node at top, Specialist Agent nodes below, edges labelled `{task_summary, status}`. Toggled view.

Both views read the same Audit Trail; they differ only in presentation.
