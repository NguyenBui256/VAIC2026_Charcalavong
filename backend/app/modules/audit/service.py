"""Audit read service — Trace Dashboard query + export side (Epic 6, FR-22/24).

Read-only counterpart to the write-only ``PostgresAuditSink`` (AD-4). This
module NEVER writes ``audit_trail`` — it only SELECTs for the Trace Dashboard
timeline and the audit export. Tenant isolation is enforced by RLS on the
session (the caller uses ``get_tenant_session``), so there is NO Python
``WHERE tenant_id`` here (AD-2).

The ``audit_trail`` row shape is frozen (see ``core/ports/audit.py``):
    {id, tenant_id, run_id, step_id, agent_id, ts, type,
     input, output, latency_ms, model}
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = [
    "list_audit_entries",
    "export_audit_entries",
    "entries_to_csv",
    "serialize_entry",
    "MAX_AUDIT_LIMIT",
    "EXPORT_LIMIT",
]

# Hard cap so a large tenant trail never renders an unbounded payload (R-5).
MAX_AUDIT_LIMIT: int = 500
# Higher cap for a file export (still bounded — never stream unbounded).
EXPORT_LIMIT: int = 10_000
_DEFAULT_LIMIT: int = 200

_BASE_SELECT = (
    "SELECT id, run_id, step_id, agent_id, ts, type, "
    "input, output, latency_ms, model FROM audit_trail"
)

# CSV column order — input/output serialized as JSON strings.
_CSV_COLUMNS: tuple[str, ...] = (
    "id", "run_id", "step_id", "agent_id", "ts", "type",
    "latency_ms", "model", "input", "output",
)


def _fetch_entries(
    session: Session,
    *,
    run_id: uuid.UUID | None,
    entry_type: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Run the tenant-scoped (RLS) audit query and serialize rows.

    ``run_id`` present → ``ts ASC`` (a single Run's timeline); else ``ts DESC``.
    """
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit}
    if run_id is not None:
        clauses.append("run_id = :run_id")
        params["run_id"] = str(run_id)
    if entry_type:
        clauses.append("type = :entry_type")
        params["entry_type"] = entry_type

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "ts ASC" if run_id is not None else "ts DESC"
    sql = text(f"{_BASE_SELECT}{where} ORDER BY {order} LIMIT :limit")
    rows = session.execute(sql, params).mappings().all()
    return [serialize_entry(row) for row in rows]


def list_audit_entries(
    session: Session,
    *,
    run_id: uuid.UUID | None = None,
    entry_type: str | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Tenant-scoped audit entries for the Trace Dashboard (capped)."""
    limit = max(1, min(limit, MAX_AUDIT_LIMIT))
    return _fetch_entries(session, run_id=run_id, entry_type=entry_type, limit=limit)


def export_audit_entries(
    session: Session,
    *,
    run_id: uuid.UUID | None = None,
    entry_type: str | None = None,
) -> list[dict[str, Any]]:
    """Tenant-scoped entries for a file export (higher, still-bounded cap)."""
    return _fetch_entries(
        session, run_id=run_id, entry_type=entry_type, limit=EXPORT_LIMIT
    )


def entries_to_csv(entries: list[dict[str, Any]]) -> str:
    """Serialize entries to CSV text; input/output become JSON strings."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for entry in entries:
        row = dict(entry)
        row["input"] = json.dumps(entry.get("input"), ensure_ascii=False)
        row["output"] = json.dumps(entry.get("output"), ensure_ascii=False)
        writer.writerow(row)
    return buf.getvalue()


def serialize_entry(row: Any) -> dict[str, Any]:
    """Serialize one ``audit_trail`` row to the Trace Dashboard shape.

    ``ts`` → ISO 8601 with millisecond precision (consistency convention).
    ``input``/``output`` are already ``dict`` (jsonb). UUIDs → ``str``.
    """
    ts = row["ts"]
    return {
        "id": str(row["id"]),
        "run_id": str(row["run_id"]) if row["run_id"] is not None else None,
        "step_id": str(row["step_id"]) if row["step_id"] is not None else None,
        "agent_id": str(row["agent_id"]) if row["agent_id"] is not None else None,
        "ts": ts.isoformat(timespec="milliseconds") if ts is not None else None,
        "type": row["type"],
        "input": row["input"],
        "output": row["output"],
        "latency_ms": row["latency_ms"],
        "model": row["model"] or "",
    }
