"""Seeds the Epic 7 demo Specialist Agents, Tools, and Workflow.

Called by `bootstrap_demo_tenant.bootstrap_demo_tenant()` after Story 1.12's
tenant/department/user seeding. Reuses the SAME agent_builder / orchestrator
SERVICE functions the API routes use (`create_agent`/`update_agent`/
`create_tool`/`create_workflow`) — never hand-writes INSERTs that bypass
validation/audit (dev-rules "DO NOT create new enhanced files" /
consistency-conventions).

KB seeding is intentionally SKIPPED — no real embedding/RAG server exists
yet; `McpClientStub.call_tool("rag.search", ...)` always returns an empty
passage list regardless of what was ingested (see
`app/modules/agent_builder/kb_retrieval.py`), so seeding KB documents would
be theater with zero effect on runtime retrieval. Agents still run fine —
`AgentKbProvider.retrieve` returns `[]`, which `AgentExecutor` treats as
"(none)" KB context, not a failure.
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

from app.core.tenant_context import tenant_context  # noqa: E402
from app.modules.agent_builder.models import Agent, Tool  # noqa: E402
from app.modules.agent_builder.service import Principal, create_agent, update_agent  # noqa: E402
from app.modules.agent_builder.tool_crud import create_tool  # noqa: E402
from app.modules.orchestrator.models import Workflow  # noqa: E402
from app.modules.orchestrator.service import create_workflow  # noqa: E402
from app.modules.tenant.models import Department, User  # noqa: E402
from scripts.demo_agent_specs import (  # noqa: E402
    AGENT_MODEL_REF,
    AGENT_SPECS,
    DEMO_WORKFLOW_DESCRIPTION,
    DEMO_WORKFLOW_NAME,
    AgentSpec,
    ToolSpec,
)

__all__ = ["seed_agents_tools_workflow"]


def _find_agent(session: Session, tenant_id: uuid.UUID, name: str) -> Agent | None:
    return session.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id, Agent.name == name, Agent.is_deleted.is_(False)
        )
    ).scalars().first()


def _find_tool(session: Session, agent_id: uuid.UUID, display_name: str) -> Tool | None:
    return session.execute(
        select(Tool).where(
            Tool.agent_id == agent_id,
            Tool.display_name == display_name,
            Tool.is_deleted.is_(False),
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
    agent = update_agent(session, agent.id, principal, model=dict(AGENT_MODEL_REF))
    return agent, True


def _upsert_tool(
    session: Session, agent: Agent, owner: User, tenant_id: uuid.UUID, tool_spec: ToolSpec
) -> tuple[Tool, bool]:
    existing = _find_tool(session, agent.id, tool_spec["display_name"])
    if existing is not None:
        return existing, False

    tenant_context.set(tenant_id)
    principal = Principal(
        user_id=owner.id, tenant_id=tenant_id, department_id=agent.department_id, role="builder"
    )
    tool = create_tool(
        session,
        agent_id=agent.id,
        principal=principal,
        display_name=tool_spec["display_name"],
        header={},
        input_schema=tool_spec["input_schema"],
        output_schema=tool_spec["output_schema"],
        embedded_python=tool_spec["embedded_python"],
    )
    return tool, True


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
    """Idempotently seed the 3 demo Agents (+1 Tool each) + 1 Workflow.

    `builder_user` owns every Agent/Tool/Workflow row — `create_agent`/
    `create_workflow` only require `role=='builder'`, and
    `_authorize_mutation`'s owner-or-same-department check passes on
    ownership alone, so a single builder owning all 3 Agents (even across
    3 different Departments) is a valid, AC10-safe seed.
    """
    dept_by_name = {d.name: d for d in departments}
    agents_created = 0
    tools_created = 0
    agents: list[Agent] = []

    for spec in AGENT_SPECS:
        dept = dept_by_name.get(spec["department"])
        if dept is None:
            raise RuntimeError(f"Department {spec['department']!r} not seeded")
        agent, agent_created = _upsert_agent(session, tenant_id, dept, builder_user, spec)
        agents_created += int(agent_created)
        _tool, tool_created = _upsert_tool(session, agent, builder_user, tenant_id, spec["tool"])
        tools_created += int(tool_created)
        agents.append(agent)
        print(
            f"[bootstrap] agent={agent.name!r} id={agent.id} "
            f"tool={spec['tool']['display_name']!r} "
            f"({'created' if agent_created else 'exists'})"
        )

    workflow, workflow_created = _upsert_workflow(session, tenant_id, builder_user)
    print(
        f"[bootstrap] workflow={workflow.name!r} id={workflow.id} "
        f"({'created' if workflow_created else 'exists'})"
    )
    print(
        "[bootstrap] NOTE: KB seeding skipped — no real RAG/embedding "
        "server is wired yet (McpClientStub.rag.search always returns an "
        "empty passage list); Agents still run, retrieval just yields no "
        "citations."
    )

    return {
        "agents": agents,
        "workflow": workflow,
        "created": {
            "agents": agents_created,
            "tools": tools_created,
            "workflow": int(workflow_created),
        },
    }
