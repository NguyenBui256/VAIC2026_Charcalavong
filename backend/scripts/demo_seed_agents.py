"""Demo Agent / Knowledge-Base / Tool seeding (Epic 7-thin, roadmap §2).

Companion to `bootstrap_demo_tenant.py`. Extends the Story 1.12 "Bootstrap
Lite" (Tenant + Departments + Users) with the three Specialist Agents the
demo "Business Loan Pre-Screen" workflow dispatches to, plus one Knowledge
Base document and one Tool per Agent.

Why a separate module: keeps `bootstrap_demo_tenant.py` lean and each file
focused (CLAUDE.md modularization rule). All helpers are idempotent
find-or-create by natural key, mirroring the parent script's convention.

Scope caveats (surfaced honestly, not silently):
- KB documents are seeded as METADATA rows only (`status="indexed"` with a
  placeholder `external_document_id`). The vector store is NOT populated —
  actual RAG retrieval returns `[]` until documents are ingested through the
  real DocIntake pipeline. This is enough for the collaboration demo (Agents
  execute on system prompt + model even when retrieval is empty, AD-11).
- Tools are seeded as MCP-routed registrations (`embedded_python=None`) with
  valid input/output JSON schemas. Whether a Tool actually executes depends
  on Epic 3.4 dispatch wiring + a reachable MCP server — out of seed scope.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.modules.agent_builder.kb_models import KbDocument
from app.modules.agent_builder.models import Agent, Tool
from app.modules.tenant.models import Department, Tenant, User

__all__ = [
    "AGENT_SPECS",
    "DEMO_MODEL_REF",
    "seed_agents_kb_tools",
]

# A configured-but-not-necessarily-keyed model ref. The frontend renders this
# on the Model tab; execution requires the Anthropic key in Settings.
DEMO_MODEL_REF: dict[str, Any] = {
    "provider": "anthropic",
    "model_name": "claude-sonnet-4-5",
    "parameters": {},
}

# Single source of truth for the demo Agent dataset. `department` MUST match a
# Department name seeded by bootstrap_demo_tenant.DEPARTMENTS.
AGENT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "Credit Analyst",
        "department": "Credit",
        "system_prompt": (
            "You are a credit analyst at SHB. Assess a business borrower's "
            "creditworthiness from their financials. Compute key ratios, flag "
            "risks, and return a structured recommendation with a confidence."
        ),
        "kb": {
            "filename": "credit-policy-2026.pdf",
            "chunk_count": 14,
        },
        "tool": {
            "display_name": "financial_ratio_calculator",
            "input_schema": {
                "type": "object",
                "properties": {
                    "annual_revenue": {"type": "number"},
                    "total_liabilities": {"type": "number"},
                },
                "required": ["annual_revenue", "total_liabilities"],
            },
            "output_schema": {
                "type": "object",
                "properties": {"debt_to_income": {"type": "number"}},
            },
        },
    },
    {
        "name": "Compliance Officer",
        "department": "Compliance",
        "system_prompt": (
            "You are a compliance officer at SHB. Screen the applicant against "
            "AML/KYC and sanctions policy. Return any flags with citations to "
            "the relevant guideline and a pass/fail with confidence."
        ),
        "kb": {
            "filename": "aml-kyc-guidelines.pdf",
            "chunk_count": 22,
        },
        "tool": {
            "display_name": "sanctions_screening",
            "input_schema": {
                "type": "object",
                "properties": {"entity_name": {"type": "string"}},
                "required": ["entity_name"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "is_flagged": {"type": "boolean"},
                    "matches": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
    {
        "name": "Operations Verifier",
        "department": "Operations",
        "system_prompt": (
            "You are an operations verifier at SHB. Check the loan application "
            "document checklist for completeness. Return the missing documents "
            "and a ready/not-ready verdict with confidence."
        ),
        "kb": {
            "filename": "document-checklist-sop.pdf",
            "chunk_count": 9,
        },
        "tool": {
            "display_name": "document_checklist",
            "input_schema": {
                "type": "object",
                "properties": {"application_id": {"type": "string"}},
                "required": ["application_id"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "complete": {"type": "boolean"},
                    "missing": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
)


def seed_agents_kb_tools(
    session: Any,
    tenant: Tenant,
    departments: list[Department],
    owner: User,
) -> dict[str, int]:
    """Idempotently seed demo Agents + one KB doc + one Tool each.

    Returns a count summary: ``{"agents": n, "kb": n, "tools": n}`` (new rows
    only). `owner` is the Agent record owner (the builder user).
    """
    dept_by_name = {d.name: d for d in departments}
    created = {"agents": 0, "tools": 0, "kb": 0}

    for spec in AGENT_SPECS:
        department = dept_by_name.get(spec["department"])
        if department is None:
            raise RuntimeError(
                f"Department {spec['department']!r} not found for agent "
                f"{spec['name']!r} — seed departments first."
            )
        agent, agent_created = _upsert_agent(session, tenant, department, owner, spec)
        if agent_created:
            created["agents"] += 1
        if _upsert_kb_document(session, tenant, agent, department, spec["kb"]):
            created["kb"] += 1
        if _upsert_tool(session, tenant, agent, department, spec["tool"]):
            created["tools"] += 1

    return created


def _upsert_agent(
    session: Any,
    tenant: Tenant,
    department: Department,
    owner: User,
    spec: dict[str, Any],
) -> tuple[Agent, bool]:
    """Find-or-create one Agent by (tenant, name)."""
    existing = session.execute(
        select(Agent).where(
            Agent.tenant_id == tenant.id,
            Agent.name == spec["name"],
        )
    ).scalars().first()
    if existing is not None:
        return existing, False

    agent = Agent(
        tenant_id=tenant.id,
        department_id=department.id,
        owner_id=owner.id,
        name=spec["name"],
        system_prompt=spec["system_prompt"],
        model=DEMO_MODEL_REF,
        status="active",
    )
    session.add(agent)
    session.flush()
    print(f"[bootstrap] created agent name={spec['name']!r} id={agent.id}")
    return agent, True


def _upsert_kb_document(
    session: Any,
    tenant: Tenant,
    agent: Agent,
    department: Department,
    kb: dict[str, Any],
) -> bool:
    """Find-or-create one KB document metadata row by (agent, filename)."""
    existing = session.execute(
        select(KbDocument).where(
            KbDocument.agent_id == agent.id,
            KbDocument.filename == kb["filename"],
        )
    ).scalars().first()
    if existing is not None:
        return False

    doc = KbDocument(
        tenant_id=tenant.id,
        agent_id=agent.id,
        department_id=department.id,
        filename=kb["filename"],
        content_type="application/pdf",
        size_bytes=kb.get("size_bytes", 262_144),
        status="indexed",
        external_document_id=f"seed-{agent.id}",
        chunk_count=kb["chunk_count"],
    )
    session.add(doc)
    session.flush()
    print(f"[bootstrap]   + kb doc {kb['filename']!r} for agent {agent.name!r}")
    return True


def _upsert_tool(
    session: Any,
    tenant: Tenant,
    agent: Agent,
    department: Department,
    tool: dict[str, Any],
) -> bool:
    """Find-or-create one Tool by (agent, display_name)."""
    existing = session.execute(
        select(Tool).where(
            Tool.agent_id == agent.id,
            Tool.display_name == tool["display_name"],
        )
    ).scalars().first()
    if existing is not None:
        return False

    row = Tool(
        agent_id=agent.id,
        tenant_id=tenant.id,
        department_id=department.id,
        display_name=tool["display_name"],
        header={},
        input_schema=tool["input_schema"],
        output_schema=tool["output_schema"],
        embedded_python=None,
    )
    session.add(row)
    session.flush()
    print(f"[bootstrap]   + tool {tool['display_name']!r} for agent {agent.name!r}")
    return True
