"""Agent Builder service layer — CRUD + identity/department scoping.

Story 2.1. Domain functions read `tenant_context.get()` (via RLS on the
session) — NEVER accept `tenant_id` as an argument (consistency-conventions
"Tenant context"). The `department_id` filter in `list_agents` is a domain
filter, not a tenant filter (AD-2: RLS owns tenant isolation).

Every CRUD write emits exactly one audit entry through `AuditPort` (AD-4) —
never direct SQL/ORM to `audit_trail` (AC8).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.adapters.registry import select_llm_adapter
from app.core.deps import crud_audit_ids
from app.core.errors import AuthorizationError, NotFoundError, ValidationError
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.model_catalog import KNOWN_PROVIDER_IDS
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.ports.llm import CompletionResult, LlmPort, Message, ModelRef
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.models import Agent

__all__ = [
    "Principal",
    "create_agent",
    "get_agent",
    "list_agents",
    "list_routable_agents",
    "update_agent",
    "soft_delete_agent",
    "serialize_agent",
    "invoke_agent_model",
]


@dataclass(frozen=True)
class Principal:
    """The caller's identity, as extracted from `request.state` by routes."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    department_id: uuid.UUID | None
    role: str


def _emit_audit(
    audit: AuditPort, agent: Agent, entry_type: str, payload: dict
) -> None:
    """Emit one audit entry for a CRUD write (AC8). Never swallows (AD-4)."""
    run_id, step_id = crud_audit_ids(str(agent.id))
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(agent.id),
            ts=utcnow_iso_ms(),
            type=entry_type,
            input=payload,
            output={"agent_id": str(agent.id), "version": agent.version},
            latency_ms=0,
            model="",
        )
    )


def create_agent(
    session: Session,
    *,
    owner_id: uuid.UUID,
    role: str,
    name: str,
    department_id: uuid.UUID,
    system_prompt: str,
    audit: AuditPort | None = None,
) -> Agent:
    """Create a scoped Agent (AC1, AC10). Requires builder role."""
    if role != "builder":
        raise AuthorizationError("builder role required to create an Agent", code="FORBIDDEN")

    tenant_id = tenant_context.get()
    agent = Agent(
        id=uuid7(),
        tenant_id=tenant_id,
        department_id=department_id,
        owner_id=owner_id,
        name=name,
        system_prompt=system_prompt,
        status="draft",
        version=1,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)

    _emit_audit(
        audit or PostgresAuditSink(),
        agent,
        "agent.created",
        {"name": name, "department_id": str(department_id)},
    )
    return agent


def get_agent(session: Session, agent_id: uuid.UUID) -> Agent:
    """Fetch a single non-deleted Agent. RLS hides cross-tenant rows (AC3)."""
    agent = session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.is_deleted.is_(False))
    ).scalar_one_or_none()
    if agent is None:
        raise NotFoundError("Agent not found")
    return agent


def list_agents(
    session: Session, *, department_id: uuid.UUID | None = None
) -> list[Agent]:
    """List non-deleted Agents. Tenant scoping is RLS-only (AC4, AC5)."""
    stmt = select(Agent).where(Agent.is_deleted.is_(False))
    if department_id is not None:
        stmt = stmt.where(Agent.department_id == department_id)
    return list(session.execute(stmt).scalars().all())


def list_routable_agents(session: Session) -> list[dict]:
    """Public routing candidates for the Orchestrator (AD-1: service, not model access)."""
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "department_id": str(a.department_id),
            "system_prompt": a.system_prompt,
        }
        for a in list_agents(session)
    ]


def _authorize_mutation(agent: Agent, principal: Principal) -> None:
    """Guard for PATCH/DELETE (AC6, AC10).

    Allowed if the caller has builder role AND (owns the Agent OR is in the
    Agent's Department). Else 403 FORBIDDEN.
    """
    is_owner = agent.owner_id == principal.user_id
    same_department = agent.department_id == principal.department_id
    if principal.role == "builder" and (is_owner or same_department):
        return
    raise AuthorizationError(
        "Not authorized to mutate this Agent", code="FORBIDDEN"
    )


def _validate_model_ref(value: dict[str, Any]) -> dict[str, Any]:
    """Validate a `model` PATCH payload shape (T2.2, AC4).

    `provider` must be a KNOWN provider id, but is NOT required to be
    *configured* -- an unconfigured/placeholder provider is accepted at
    config time (AC9); the failure surfaces at run time instead.
    """
    provider = value.get("provider")
    if not isinstance(provider, str) or provider not in KNOWN_PROVIDER_IDS:
        raise ValidationError(
            f"Unknown provider '{provider}'", code="unknown_provider"
        )
    model_name = value.get("model_name")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValidationError("model_name is required", code="validation_error")
    parameters = value.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValidationError("parameters must be an object", code="validation_error")
    return {"provider": provider, "model_name": model_name, "parameters": parameters}


def update_agent(
    session: Session,
    agent_id: uuid.UUID,
    principal: Principal,
    *,
    audit: AuditPort | None = None,
    **changes: object,
) -> Agent:
    """Update mutable fields on an Agent, bumping `version` (AC6, AC8)."""
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)

    allowed_fields = {"name", "system_prompt", "status", "department_id", "model"}
    applied: dict[str, object] = {}
    for key, value in changes.items():
        if key not in allowed_fields or value is None:
            continue
        if key == "model":
            value = _validate_model_ref(value)  # type: ignore[arg-type]
        setattr(agent, key, value)
        applied[key] = value

    agent.version += 1
    agent.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(agent)

    _emit_audit(audit or PostgresAuditSink(), agent, "agent.updated", applied)
    return agent


def soft_delete_agent(
    session: Session,
    agent_id: uuid.UUID,
    principal: Principal,
    *,
    audit: AuditPort | None = None,
) -> None:
    """Soft-delete an Agent — never hard-deletes (AC7, AC8)."""
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)

    agent.is_deleted = True
    agent.deleted_at = datetime.now(UTC)
    session.commit()
    session.refresh(agent)

    _emit_audit(
        audit or PostgresAuditSink(), agent, "agent.deleted", {"id": str(agent.id)}
    )


def serialize_agent(agent: Agent) -> dict:
    """Response payload shape (AR-14: ISO 8601 ms timestamps)."""
    return {
        "id": str(agent.id),
        "tenant_id": str(agent.tenant_id),
        "department_id": str(agent.department_id),
        "owner_id": str(agent.owner_id),
        "name": agent.name,
        "system_prompt": agent.system_prompt,
        "model": agent.model or {},
        "status": agent.status,
        "version": agent.version,
        "created_at": agent.created_at.isoformat(timespec="milliseconds"),
        "updated_at": agent.updated_at.isoformat(timespec="milliseconds"),
    }


# ---------------------------------------------------------------------------
# Run-time model invocation (Story 2.3 T3) — observable + isolated failures.
#
# Full Orchestrator run wiring is Epic 3; this only needs the run-time
# failure path to be observable (audited) and isolated (AC9, AC10). Provider
# selection goes through `select_llm_adapter` (core/adapters/registry.py) --
# this module never imports a concrete adapter (Dev Notes anti-pattern #2).
# ---------------------------------------------------------------------------


def invoke_agent_model(
    agent: Agent,
    prompt: str,
    *,
    audit: AuditPort | None = None,
    adapter_factory: Callable[[str], LlmPort] | None = None,
) -> CompletionResult:
    """Run the Agent's configured model on `prompt`.

    On provider failure (missing key, NotImplementedError, etc.) this emits
    one `model_invocation_failed` audit entry with a clear remediation
    message (AC9) and RE-RAISES (AD-4: never swallow). Each call is
    independently scoped -- one Agent's bad provider cannot affect another
    Agent's invocation (AC10, FR-26).
    """
    factory = adapter_factory or select_llm_adapter
    model_data = agent.model or {}
    model_ref = ModelRef(
        provider=model_data.get("provider", ""),
        model_name=model_data.get("model_name", ""),
        parameters=model_data.get("parameters", {}),
    )
    audit_port = audit or PostgresAuditSink()

    try:
        adapter = factory(model_ref.provider)
        messages = [
            Message(role="system", content=agent.system_prompt),
            Message(role="user", content=prompt),
        ]
        return adapter.complete(messages, model_ref)
    except Exception as exc:
        run_id, step_id = crud_audit_ids(str(agent.id))
        audit_port.log(
            AuditEntry(
                run_id=run_id,
                step_id=step_id,
                agent_id=str(agent.id),
                ts=utcnow_iso_ms(),
                type="model_invocation_failed",
                input={"provider": model_ref.provider, "model": model_ref.model_name},
                output={
                    "error": str(exc),
                    "message": (
                        f"Provider '{model_ref.provider}' is unavailable: {exc} "
                        f"Configure the '{model_ref.provider}' provider (API key "
                        "/ adapter) or switch this Agent to a configured "
                        "provider."
                    ),
                },
                latency_ms=0,
                model=model_ref.model_name,
            )
        )
        raise
