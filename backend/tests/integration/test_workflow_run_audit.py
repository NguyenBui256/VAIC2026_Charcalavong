"""AC9 — every transition emits `audit.log(type="workflow_run.transition")`
with the REAL `run_id` (not the `crud_audit_ids` CRUD stopgap). Story 3.2.

Drives the happy path (`pending -> running -> completed`) through
`transition_and_audit` directly (the production call-site shape used by
`app/workers/orchestrator_worker.py`) and asserts the resulting
`audit_trail` rows.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text

from app.core.db import AdminSessionLocal, SessionLocal
from app.core.tenant_context import reset_tenant_context, set_tenant_context
from app.modules.orchestrator.models import Workflow, WorkflowRun
from app.modules.orchestrator.state import transition_and_audit


def _as_app(session: Any, tenant_id: uuid.UUID) -> None:
    session.execute(text("SET LOCAL ROLE vaic_app"))
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@pytest.fixture()
def seeded_run_for_audit(agent_seed_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    workflow_id = uuid.uuid4()
    run_id = uuid.uuid4()
    with AdminSessionLocal() as s:
        s.add(
            Workflow(
                id=workflow_id,
                tenant_id=agent_seed_data["tenant_agents_id"],
                owner_id=agent_seed_data["builder_user_id"],
                name="Audit WF",
                description="Prove AC9 transition audit entries.",
            )
        )
        s.flush()
        s.add(
            WorkflowRun(
                id=run_id,
                tenant_id=agent_seed_data["tenant_agents_id"],
                workflow_id=workflow_id,
                status="pending",
            )
        )
        s.commit()
    try:
        yield {**agent_seed_data, "workflow_id": workflow_id, "run_id": run_id}
    finally:
        with AdminSessionLocal() as s:
            s.execute(text("DELETE FROM audit_trail WHERE run_id=:id"), {"id": str(run_id)})
            s.execute(text("DELETE FROM workflow_runs WHERE id=:id"), {"id": str(run_id)})
            s.execute(text("DELETE FROM workflows WHERE id=:id"), {"id": str(workflow_id)})
            s.commit()


def test_transition_and_audit_writes_workflow_run_transition_entries(
    seeded_run_for_audit: dict[str, Any],
) -> None:
    run_id = seeded_run_for_audit["run_id"]
    tenant_id = seeded_run_for_audit["tenant_agents_id"]

    set_tenant_context(tenant_id)
    try:
        with SessionLocal() as s:
            _as_app(s, tenant_id)
            ok1 = transition_and_audit(
                s,
                kind="run",
                entity_id=run_id,
                run_id=run_id,
                from_status="pending",
                to_status="running",
            )
        assert ok1 is True

        with SessionLocal() as s:
            _as_app(s, tenant_id)
            ok2 = transition_and_audit(
                s,
                kind="run",
                entity_id=run_id,
                run_id=run_id,
                from_status="running",
                to_status="completed",
            )
        assert ok2 is True
    finally:
        reset_tenant_context()

    with AdminSessionLocal() as s:
        rows = s.execute(
            text(
                "SELECT type, input, output, run_id, agent_id FROM audit_trail "
                "WHERE run_id=:rid ORDER BY ts"
            ),
            {"rid": str(run_id)},
        ).fetchall()

    assert len(rows) == 2
    for row in rows:
        assert row[0] == "workflow_run.transition"
        assert row[3] == run_id  # real run_id, not the crud_audit_ids stopgap
        assert row[4] is None  # agent_id sentinel -> NULL (no Agent involved)

    assert rows[0][1] == {"from": "pending", "to": "running"}
    assert rows[0][2] == {"rowcount": 1}
    assert rows[1][1] == {"from": "running", "to": "completed"}
    assert rows[1][2] == {"rowcount": 1}


def test_transition_and_audit_records_rowcount_zero_on_lost_race(
    seeded_run_for_audit: dict[str, Any],
) -> None:
    """A CAS attempt against the wrong `from_status` is still audited
    (output.rowcount == 0) — AC9's `{rowcount}` shape only matters if 0 is
    captured too, not just successes."""
    run_id = seeded_run_for_audit["run_id"]
    tenant_id = seeded_run_for_audit["tenant_agents_id"]

    set_tenant_context(tenant_id)
    try:
        with SessionLocal() as s:
            _as_app(s, tenant_id)
            ok = transition_and_audit(
                s,
                kind="run",
                entity_id=run_id,
                run_id=run_id,
                from_status="running",  # wrong — Run is still 'pending'
                to_status="completed",
            )
        assert ok is False
    finally:
        reset_tenant_context()

    with AdminSessionLocal() as s:
        row = s.execute(
            text("SELECT output FROM audit_trail WHERE run_id=:rid"),
            {"rid": str(run_id)},
        ).fetchone()
    assert row[0] == {"rowcount": 0}
