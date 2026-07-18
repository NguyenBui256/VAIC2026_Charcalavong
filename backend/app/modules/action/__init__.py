"""Action/Event module — bind Mini-App Database row events to Workflow dispatch.

An `action_bindings` row maps (database_id, event_type) -> workflow_id + a staff
notify list. The mini_app row-change seam writes `action_events` (outbox); an ARQ
cron fan-out resolves bindings, creates + enqueues a WorkflowRun, and notifies staff.
"""
