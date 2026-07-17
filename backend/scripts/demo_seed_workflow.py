"""Demo Workflow seeding hook (Epic 7-thin, roadmap §2 — "chừa Workflow 1 hook").

The `workflows` table is created by Epic 3 Story 3.1 (owned by another stream).
This module is a DEFENSIVE HOOK: it introspects for the table at run time and
only seeds when 3.1 has landed. Until then it prints a deferral notice — no
crash, no coupling to the orchestrator module's Python models (which are still
stubs). When 3.1 lands, re-running the bootstrap auto-seeds the demo workflow.

We insert via raw SQL against the KNOWN 3.1 contract columns rather than
importing `orchestrator.models.Workflow` (that symbol does not exist yet).
The insert is wrapped so a column-shape drift degrades to a message instead of
failing the whole bootstrap.

Contract source: plans/260718-0052-epic-3-orchestrator/story-3-1-workflow-crud.md
  workflows(id, tenant_id, owner_id, name, description, constraints,
            confidence_threshold, escalation_timeout_seconds, version,
            created_at, updated_at)
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import inspect, text

from app.core.ids import uuid7
from app.modules.tenant.models import Tenant, User

__all__ = ["DEMO_WORKFLOW_NAME", "seed_workflow_if_ready"]

DEMO_WORKFLOW_NAME: str = "Business Loan Pre-Screen"
_DEMO_WORKFLOW_DESCRIPTION: str = (
    "Pre-screen a business loan application: pull and assess the borrower's "
    "financials (Credit), check AML/KYC and sanctions compliance (Compliance), "
    "verify the document checklist is complete (Operations), then return a "
    "consolidated pre-screen decision."
)
_DEMO_WORKFLOW_CONSTRAINTS: list[str] = [
    "must check sanctions and AML/KYC before approving",
    "must confirm the document checklist is complete",
    "escalate to a human on low confidence or conflicting agent findings",
]


def seed_workflow_if_ready(session: Any, tenant: Tenant, owner: User) -> str:
    """Seed the demo Workflow if the `workflows` table exists.

    Returns a short status string for the summary:
      - "deferred"  — table absent (Story 3.1 not landed yet)
      - "exists"    — already seeded (idempotent no-op)
      - "created"   — inserted this run
      - "skipped: <reason>" — table present but insert failed (schema drift)
    """
    if not inspect(session.bind).has_table("workflows"):
        _print_deferral()
        return "deferred"

    try:
        existing = session.execute(
            text(
                "SELECT id FROM workflows "
                "WHERE tenant_id = :tid AND name = :name LIMIT 1"
            ),
            {"tid": str(tenant.id), "name": DEMO_WORKFLOW_NAME},
        ).first()
        if existing is not None:
            print(f"[bootstrap] workflow {DEMO_WORKFLOW_NAME!r} already exists")
            return "exists"

        session.execute(
            text(
                "INSERT INTO workflows "
                "(id, tenant_id, owner_id, name, description, constraints, version) "
                "VALUES (:id, :tid, :oid, :name, :desc, "
                "CAST(:constraints AS jsonb), :version)"
            ),
            {
                "id": str(uuid7()),
                "tid": str(tenant.id),
                "oid": str(owner.id),
                "name": DEMO_WORKFLOW_NAME,
                "desc": _DEMO_WORKFLOW_DESCRIPTION,
                "constraints": json.dumps(_DEMO_WORKFLOW_CONSTRAINTS),
                "version": 1,
            },
        )
        session.flush()
        print(f"[bootstrap] created workflow {DEMO_WORKFLOW_NAME!r}")
        return "created"
    except Exception as exc:  # noqa: BLE001 — degrade, never fail the bootstrap
        reason = str(exc).splitlines()[0]
        print(
            f"[bootstrap] NOTE: workflows table present but seed skipped "
            f"(schema drift?): {reason}"
        )
        return f"skipped: {reason}"


def _print_deferral() -> None:
    """Log that workflow seeding is deferred until Story 3.1 lands."""
    print()
    print(
        "[bootstrap] NOTE: Workflow seeding deferred — the `workflows` table "
        "does not exist yet (Epic 3 Story 3.1 creates it). Re-run this script "
        "after 3.1 lands to seed the demo 'Business Loan Pre-Screen' workflow."
    )
