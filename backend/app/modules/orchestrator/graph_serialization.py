"""Response shapes for graph runtime entities (3A).

Consumed by the Tracking UI + review endpoints (3C). Timestamps are ISO 8601
with millisecond precision (AR-14), matching `service.serialize_run`.
"""

from __future__ import annotations

from app.modules.orchestrator.models import RunNodeExecution

__all__ = ["serialize_run_node_execution", "serialize_graph_snapshot"]


def _iso_ms(dt) -> str | None:
    return dt.isoformat(timespec="milliseconds") if dt else None


def serialize_run_node_execution(row: RunNodeExecution) -> dict:
    """Response payload for one per-node runtime row."""
    return {
        "id": str(row.id),
        "run_id": str(row.run_id),
        "node_key": row.node_key,
        "agent_id": str(row.agent_id),
        "status": row.status,
        "input": row.input,
        "output": row.output,
        "approver_user_ids": row.approver_user_ids or [],
        "decision": row.decision,
        "decided_by": str(row.decided_by) if row.decided_by else None,
        "reason": row.reason,
        "guidance": row.guidance,
        "decided_at": _iso_ms(row.decided_at),
        "started_at": _iso_ms(row.started_at),
        "completed_at": _iso_ms(row.completed_at),
        "created_at": _iso_ms(row.created_at),
    }


def serialize_graph_snapshot(snapshot: dict | None) -> dict | None:
    """The stored snapshot is already response-ready; return it verbatim."""
    return snapshot
