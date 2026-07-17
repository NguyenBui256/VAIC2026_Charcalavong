"""PostgresAuditSink — the ONLY path to write ``audit_trail`` (AD-4).

Implements ``AuditPort`` by INSERTing into the ``audit_trail`` table.

Critical contract (AD-4):
    - ``log()`` is the single path to write audit entries.
    - On ANY failure (DB down, constraint violation, RLS rejection), it
      RAISES — it NEVER swallows. The calling Workflow Run transitions to
      ``failed``. Trace completeness outranks Run completion (SM-C1).
    - Each ``log()`` call commits independently — durability means entries
      written before a crash survive.

Design:
    - Uses a dedicated session from ``SessionLocal`` (the runtime engine,
      subject to RLS).
    - Tenant context is read from ``tenant_context`` ContextVar (AD-2) and
      set on the session via ``set_tenant_session_var()``.
    - ``step_id`` and ``id`` are UUID v7 (``app.core.ids.uuid7``).
    - ``ts`` is stored as ``timestamptz`` — the caller passes an ISO 8601
      string; we parse it to ensure UTC + millisecond precision.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.ids import uuid7
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.tenant_context import set_tenant_session_var, tenant_context

logger = logging.getLogger(__name__)

__all__ = ["PostgresAuditSink"]


_INSERT_SQL = text(
    """
    INSERT INTO audit_trail
        (id, tenant_id, run_id, step_id, agent_id, ts, type,
         input, output, latency_ms, model)
    VALUES
        (:id, :tenant_id, :run_id, :step_id, :agent_id, :ts, :type,
         :input, :output, :latency_ms, :model)
    """
)


class PostgresAuditSink(AuditPort):
    """Concrete audit sink backed by Postgres ``audit_trail`` table.

    This is the ONLY class in the codebase that writes to ``audit_trail``.
    All Workflow Run steps must route audit writes through this adapter
    (via the ``AuditPort`` interface) — AD-4.
    """

    def __init__(self, session: Session | None = None) -> None:
        """Initialise with an optional session.

        If no session is provided, a new one is created per ``log()`` call
        so that each entry commits independently (durability).
        """
        self._session = session

    def log(self, entry: AuditEntry) -> None:
        """Persist a single audit entry. Commits immediately.

        RAISES on any failure — the caller's Run must transition to
        ``failed``. Never swallows, never silently drops (AD-4).
        """
        # Resolve tenant_id from the contextvar (AD-2).
        tenant_id = tenant_context.get()
        if tenant_id is None:
            msg = (
                "PostgresAuditSink.log: tenant_context is None — "
                "cannot write audit_trail without tenant scope (AD-2)"
            )
            raise RuntimeError(msg)

        # Parse ts to ensure UTC datetime for timestamptz.
        ts_dt = datetime.fromisoformat(entry.ts.replace("Z", "+00:00"))

        # Generate the row id as UUID v7 (AR-14).
        row_id = uuid7()

        # Use provided session or create a dedicated one.
        owns_session = self._session is None
        session = self._session if self._session is not None else SessionLocal()

        try:
            # Set the tenant GUC so RLS allows the INSERT.
            set_tenant_session_var(session, tenant_id)

            # Parse UUIDs — AuditEntry stores them as strings.
            params = {
                "id": str(row_id),
                "tenant_id": str(tenant_id),
                "run_id": str(uuid.UUID(entry.run_id)),
                "step_id": str(uuid.UUID(entry.step_id)),
                "agent_id": (
                    str(uuid.UUID(entry.agent_id))
                    if entry.agent_id
                    else None
                ),
                "ts": ts_dt,
                "type": entry.type,
                "input": _to_jsonb(entry.input),
                "output": _to_jsonb(entry.output),
                "latency_ms": entry.latency_ms,
                "model": entry.model or None,
            }
            session.execute(_INSERT_SQL, params)
            session.commit()
        except Exception:
            # AD-4: NEVER swallow. Log and re-raise so the caller's
            # Workflow Run transitions to 'failed'.
            session.rollback()
            logger.exception(
                "audit.log FAILED — entry dropped, Run must fail. "
                "run_id=%s step_id=%s type=%s",
                entry.run_id,
                entry.step_id,
                entry.type,
            )
            raise
        finally:
            if owns_session:
                session.close()


def _to_jsonb(value: dict) -> str:
    """Serialise dict to JSON string for psycopg/jsonb binding."""
    return json.dumps(value)
