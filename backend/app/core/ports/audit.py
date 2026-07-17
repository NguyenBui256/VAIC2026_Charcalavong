"""AuditPort -- hexagonal port for the audit sink (AD-4).

``audit.log(entry)`` is the ONLY path to write to ``audit_trail``. Every
Workflow Run step MUST call it. The ``audit_trail`` table grants INSERT only;
UPDATE and DELETE are revoked. Append-only is enforced at the DB.

If an ``audit.log()`` call fails (DB down, constraint violation), the calling
Workflow Run transitions to ``failed`` -- never silently drop an entry.

AuditEntry field names are exact per PRD FR-21 and consistency-conventions.md:
    {run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

__all__ = ["AuditPort", "AuditEntry"]


class AuditEntry(BaseModel):
    """A single append-only audit trail entry (PRD FR-21).

    Field names are exact -- DO NOT rename. The audit table schema and the
    Trace Dashboard both depend on these names.

    Attributes:
        run_id: the Workflow Run this entry belongs to.
        step_id: the step within the run.
        agent_id: the Specialist Agent (or orchestrator) that produced this step.
        ts: UTC ISO 8601 with milliseconds (consistency convention).
        type: entry type (e.g. "decomposition", "task_dispatch", "tool_call",
              "model_invocation", "aggregation", "escalation", "mini_app_emission").
        input: the input to the step (prompt, task, etc.).
        output: the output of the step (response, result, etc.).
        latency_ms: wall-clock latency of the step in milliseconds.
        model: model name if this was a model invocation, else None/empty.
    """

    run_id: str
    step_id: str
    agent_id: str
    ts: str
    type: str
    input: dict[str, Any]
    output: dict[str, Any]
    latency_ms: int
    model: str = ""


@runtime_checkable
class AuditPort(Protocol):
    """Hexagonal port for the audit sink.

    Implementation: ``app/modules/audit/sink.py`` (Story 1.5).

    The implementation MUST be append-only and MUST crash the calling Run on
    failure (AD-4). Never swallow, never silently drop.
    """

    def log(self, entry: AuditEntry) -> None:
        """Write a single audit entry. Must not return until persisted.

        Raises on failure -- the caller (Workflow Run) transitions to ``failed``.
        """
        ...
