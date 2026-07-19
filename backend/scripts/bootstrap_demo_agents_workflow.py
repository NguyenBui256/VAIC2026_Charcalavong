"""Seeds the Epic 7 demo Specialist Agents, Tools, KB docs, and Workflow.

Called by `bootstrap_demo_tenant.bootstrap_demo_tenant()` after Story 1.12's
tenant/department/user seeding. Reuses the SAME agent_builder / orchestrator
SERVICE functions the API routes use (`create_agent`/`update_agent`/
`seed_default_tools`/`create_workflow`) — never hand-writes INSERTs that
bypass validation/audit (dev-rules "DO NOT create new enhanced files" /
consistency-conventions), except for the demo KB documents themselves, which
are seeded directly via ORM (no file bytes to upload) and marked `indexed`.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.ids import uuid7  # noqa: E402
from app.core.tenant_context import tenant_context  # noqa: E402
from app.modules.agent_builder.kb_models import AgentKbDocument, KbDocument  # noqa: E402
from app.modules.agent_builder.models import Agent, AgentTool  # noqa: E402
from app.modules.agent_builder.service import Principal, create_agent, update_agent  # noqa: E402
from app.modules.agent_builder.tool_catalog_service import seed_default_tools  # noqa: E402
from app.modules.orchestrator.models import Workflow  # noqa: E402
from app.modules.orchestrator.service import create_workflow  # noqa: E402
from app.modules.tenant.models import Department, User  # noqa: E402
from scripts.demo_agent_specs import (  # noqa: E402
    AGENT_SPECS,
    DEMO_KB_DOCS,
    DEMO_WORKFLOW_DESCRIPTION,
    DEMO_WORKFLOW_NAME,
    AgentSpec,
    get_agent_model_ref,
)

__all__ = ["seed_agents_tools_workflow"]


def _find_agent(session: Session, tenant_id: uuid.UUID, name: str) -> Agent | None:
    return session.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id, Agent.name == name, Agent.is_deleted.is_(False)
        )
    ).scalars().first()


def _find_workflow(session: Session, tenant_id: uuid.UUID, name: str) -> Workflow | None:
    return session.execute(
        select(Workflow).where(Workflow.tenant_id == tenant_id, Workflow.name == name)
    ).scalars().first()


def _upsert_agent(
    session: Session, tenant_id: uuid.UUID, dept: Department, owner: User, spec: AgentSpec
) -> tuple[Agent, bool]:
    """Find-or-create the Agent, then ensure its Model is set (idempotent)."""
    existing = _find_agent(session, tenant_id, spec["name"])
    if existing is not None:
        return existing, False

    tenant_context.set(tenant_id)
    agent = create_agent(
        session,
        owner_id=owner.id,
        role="builder",
        name=spec["name"],
        department_id=dept.id,
        system_prompt=spec["system_prompt"],
    )
    principal = Principal(
        user_id=owner.id, tenant_id=tenant_id, department_id=dept.id, role="builder"
    )
    agent = update_agent(session, agent.id, principal, model=get_agent_model_ref())
    return agent, True


def _seed_kb_docs(session: Session, tenant_id: uuid.UUID, owner: User) -> dict[str, KbDocument]:
    """Seed demo KB docs directly (no file bytes); mark indexed. Idempotent."""
    tenant_context.set(tenant_id)
    by_name: dict[str, KbDocument] = {}
    for spec in DEMO_KB_DOCS:
        existing = session.execute(
            select(KbDocument).where(
                KbDocument.tenant_id == tenant_id, KbDocument.filename == spec["filename"]
            )
        ).scalars().first()
        if existing is not None:
            by_name[spec["filename"]] = existing
            continue
        doc = KbDocument(
            id=uuid7(), tenant_id=tenant_id, owner_id=owner.id, department_id=None,
            filename=spec["filename"], content_type=spec["content_type"],
            size_bytes=0, status="indexed",
            external_document_id=f"demo-{spec['filename']}", chunk_count=0,
        )
        session.add(doc)
        by_name[spec["filename"]] = doc
    session.commit()
    for doc in by_name.values():
        session.refresh(doc)
    return by_name


def _ref_tool(session: Session, agent: Agent, tool: Any, tenant_id: uuid.UUID) -> None:
    if session.get(AgentTool, {"agent_id": agent.id, "tool_id": tool.id}) is None:
        session.add(AgentTool(agent_id=agent.id, tool_id=tool.id, tenant_id=tenant_id))
        session.commit()


def _grant_doc(session: Session, agent: Agent, doc: KbDocument, tenant_id: uuid.UUID) -> None:
    if session.get(AgentKbDocument, {"agent_id": agent.id, "document_id": doc.id}) is None:
        session.add(AgentKbDocument(agent_id=agent.id, document_id=doc.id, tenant_id=tenant_id))
        session.commit()


def _upsert_workflow(session: Session, tenant_id: uuid.UUID, owner: User) -> tuple[Workflow, bool]:
    existing = _find_workflow(session, tenant_id, DEMO_WORKFLOW_NAME)
    if existing is not None:
        return existing, False

    tenant_context.set(tenant_id)
    workflow = create_workflow(
        session,
        owner_id=owner.id,
        role="builder",
        name=DEMO_WORKFLOW_NAME,
        description=DEMO_WORKFLOW_DESCRIPTION,
    )
    return workflow, True


def seed_agents_tools_workflow(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    departments: list[Department],
    builder_user: User,
) -> dict[str, Any]:
    """Idempotently seed the 3 demo Agents (+catalog Tool refs +KB grants) + 1 Workflow.

    `builder_user` owns every Agent/Workflow row and the demo KB documents —
    `create_agent`/`create_workflow` only require `role=='builder'`, and
    `_authorize_mutation`'s owner-or-same-department check passes on
    ownership alone, so a single builder owning all 3 Agents (even across
    3 different Departments) is a valid, AC10-safe seed.
    """
    dept_by_name = {d.name: d for d in departments}
    agents_created = 0
    agents: list[Agent] = []

    tools_by_type = seed_default_tools(session, tenant_id=tenant_id, owner_id=builder_user.id)
    docs_by_name = _seed_kb_docs(session, tenant_id, builder_user)

    for spec in AGENT_SPECS:
        dept = dept_by_name.get(spec["department"])
        if dept is None:
            raise RuntimeError(f"Department {spec['department']!r} not seeded")
        agent, agent_created = _upsert_agent(session, tenant_id, dept, builder_user, spec)
        agents_created += int(agent_created)
        for ttype in spec["tool_types"]:
            _ref_tool(session, agent, tools_by_type[ttype], tenant_id)
        for fname in spec["kb_doc_filenames"]:
            _grant_doc(session, agent, docs_by_name[fname], tenant_id)
        agents.append(agent)
        print(f"[bootstrap] agent={agent.name!r} tools={spec['tool_types']} docs={spec['kb_doc_filenames']}")

    workflow, workflow_created = _upsert_workflow(session, tenant_id, builder_user)
    print(
        f"[bootstrap] workflow={workflow.name!r} id={workflow.id} "
        f"({'created' if workflow_created else 'exists'})"
    )

    return {
        "agents": agents,
        "workflow": workflow,
        "created": {
            "agents": agents_created,
            "tools": len(tools_by_type),
            "workflow": int(workflow_created),
        },
    }
