"""Validated, versioned AI mutations for Workflow Graph and Mini-App Chat."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from arq.connections import ArqRedis
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ValidationError
from app.core.ports.llm import CompletionResult, Message, ModelRef
from app.modules.agent_builder.models import Agent
from app.modules.chat.models import ChatMessage, ChatMutation, ChatSession
from app.modules.chat.worker import _attachment_context, _complete_with_retry
from app.modules.mini_app.lifecycle import enqueue_build
from app.modules.mini_app.models import MiniApp
from app.modules.mini_app.schema_validation import validate_entity_schema, validate_ui_spec
from app.modules.orchestrator.graph_authoring import (
    replace_workflow_graph,
    serialize_workflow_graph,
)
from app.modules.orchestrator.models import Workflow
from app.modules.tenant.models import User


class GraphProposal(BaseModel):
    action: Literal["apply", "clarify", "reject"]
    summary: str = Field(min_length=1)
    expected_version: int
    graph: dict[str, Any] | None = None


class MiniAppProposal(BaseModel):
    action: Literal["apply", "clarify", "reject"]
    summary: str = Field(min_length=1)
    expected_updated_at: str
    entity_schema: dict[str, Any] | None = None
    ui_spec: dict[str, Any] | None = None


def _strip_fences(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        if value.endswith("```"):
            value = value.rsplit("```", 1)[0]
    return value.strip()


async def _structured_completion(
    *,
    system: str,
    prompt: str,
    model: ModelRef,
    schema: type[GraphProposal] | type[MiniAppProposal],
) -> tuple[GraphProposal | MiniAppProposal, CompletionResult]:
    messages = [Message(role="system", content=system), Message(role="user", content=prompt)]
    completion = await _complete_with_retry(messages, model)
    for repair in range(2):
        try:
            raw = json.loads(_strip_fences(completion.content))
            return schema.model_validate(raw), completion
        except (json.JSONDecodeError, PydanticValidationError) as exc:
            if repair:
                raise ValidationError(
                    f"model returned invalid structured output: {exc}",
                    code="invalid_model_output",
                ) from exc
            repair_prompt = (
                "The previous JSON failed server validation. Return corrected JSON only.\n"
                f"VALIDATION ERROR:\n{exc}\n\nPREVIOUS OUTPUT:\n{completion.content}"
            )
            completion = await _complete_with_retry(
                [
                    *messages,
                    Message(role="assistant", content=completion.content),
                    Message(role="user", content=repair_prompt),
                ],
                model,
            )
    raise RuntimeError("unreachable")


def _model(chat_session: ChatSession) -> ModelRef:
    if not chat_session.provider_id or not chat_session.model_name:
        raise ValidationError("chat session has no model", code="model_not_selected")
    return ModelRef(provider=chat_session.provider_id, model_name=chat_session.model_name)


def _merge_graph_defaults(
    current: dict[str, Any], proposed: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    old_by_key = {node["node_key"]: node for node in current.get("nodes", [])}
    nodes = list(proposed.get("nodes") or [])
    for index, node in enumerate(nodes):
        old = old_by_key.get(node.get("node_key"), {})
        if not node.get("position"):
            node["position"] = old.get(
                "position", {"x": float((index % 4) * 280), "y": float((index // 4) * 180)}
            )
        if "approver_user_ids" not in node:
            node["approver_user_ids"] = old.get("approver_user_ids", [])
        node.setdefault("config", old.get("config", {}))
    return nodes, list(proposed.get("edges") or [])


def _validate_graph_references(db: Session, nodes: list[dict[str, Any]]) -> None:
    try:
        agent_ids = {uuid.UUID(str(node.get("agent_id"))) for node in nodes}
        approver_ids = {
            uuid.UUID(str(user_id))
            for node in nodes
            for user_id in node.get("approver_user_ids", [])
        }
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "graph contains an invalid UUID", code="invalid_graph_reference"
        ) from exc
    valid_agents = set(
        db.scalars(
            select(Agent.id).where(Agent.id.in_(agent_ids), Agent.is_deleted.is_(False))
        ).all()
    )
    if valid_agents != agent_ids:
        raise ValidationError("graph references an unknown Agent", code="unknown_agent")
    if approver_ids:
        valid_users = set(db.scalars(select(User.id).where(User.id.in_(approver_ids))).all())
        if valid_users != approver_ids:
            raise ValidationError("graph references an unknown approver", code="unknown_approver")


async def _process_graph(
    db: Session, chat_session: ChatSession, user_message: ChatMessage
) -> tuple[str, dict[str, Any], CompletionResult]:
    workflow = db.get(Workflow, chat_session.target_id)
    if workflow is None:
        raise ValidationError("workflow not found", code="workflow_not_found")
    current = serialize_workflow_graph(db, workflow.id)
    agents = db.execute(
        select(Agent.id, Agent.name).where(Agent.is_deleted.is_(False)).order_by(Agent.name)
    ).all()
    prompt = json.dumps(
        {
            "instruction": user_message.content,
            "attachment_context": _attachment_context(db, user_message),
            "expected_workflow_version": workflow.version,
            "current_graph": current,
            "available_agents": [{"id": str(item.id), "name": item.name} for item in agents],
        },
        ensure_ascii=False,
    )
    system = (
        "You edit a bank workflow DAG. Return strict JSON only with action "
        "apply|clarify|reject, summary, expected_version, and full graph when action=apply. "
        "Use only available Agent IDs. Preserve unchanged positions and approvers. "
        "Do not create cycles, duplicate node keys, unknown endpoints, or self edges."
    )
    proposal_raw, completion = await _structured_completion(
        system=system, prompt=prompt, model=_model(chat_session), schema=GraphProposal
    )
    proposal = GraphProposal.model_validate(proposal_raw)
    if proposal.action != "apply":
        return proposal.summary, {"action": proposal.action}, completion
    if proposal.expected_version != workflow.version:
        raise ConflictError(
            "workflow changed while the model was responding", code="workflow_version_conflict"
        )
    if proposal.graph is None:
        raise ValidationError("apply response requires a full graph", code="invalid_model_output")
    nodes, edges = _merge_graph_defaults(current, proposal.graph)
    _validate_graph_references(db, nodes)
    before_version = workflow.version
    after = replace_workflow_graph(db, workflow.id, role="builder", nodes=nodes, edges=edges)
    workflow = db.get(Workflow, workflow.id)
    mutation = ChatMutation(
        tenant_id=chat_session.tenant_id,
        session_id=chat_session.id,
        message_id=user_message.id,
        target_type="workflow",
        target_id=workflow.id,
        before_snapshot=current,
        after_snapshot=after,
        before_version=str(before_version),
        after_version=str(workflow.version),
        status="applied",
    )
    db.add(mutation)
    db.commit()
    return (
        proposal.summary,
        {
            "action": "apply",
            "mutation_id": str(mutation.id),
            "workflow_version": workflow.version,
            "graph": after,
        },
        completion,
    )


def _mini_snapshot(app: MiniApp) -> dict[str, Any]:
    return {
        "entity_schema": app.entity_schema,
        "ui_spec": app.ui_spec,
        "build_status": app.build_status,
        "build_error": app.build_error,
    }


async def _process_mini_app(
    ctx: dict[str, Any], db: Session, chat_session: ChatSession, user_message: ChatMessage
) -> tuple[str, dict[str, Any], CompletionResult]:
    app = db.get(MiniApp, chat_session.target_id)
    if app is None:
        raise ValidationError("mini-app not found", code="mini_app_not_found")
    expected = app.updated_at.isoformat()
    prompt = json.dumps(
        {
            "instruction": user_message.content,
            "attachment_context": _attachment_context(db, user_message),
            "expected_updated_at": expected,
            "current_entity_schema": app.entity_schema,
            "current_ui_spec": app.ui_spec,
        },
        ensure_ascii=False,
    )
    system = (
        "You revise a bank data-entry mini-app. Return strict JSON only with action "
        "apply|clarify|reject, summary, expected_updated_at, full entity_schema and full "
        "ui_spec for apply. Preserve unspecified fields. Allowed field types are string, "
        "longtext, integer, number, boolean, date, enum. Never return a partial diff."
    )
    proposal_raw, completion = await _structured_completion(
        system=system, prompt=prompt, model=_model(chat_session), schema=MiniAppProposal
    )
    proposal = MiniAppProposal.model_validate(proposal_raw)
    if proposal.action != "apply":
        return proposal.summary, {"action": proposal.action}, completion
    if proposal.expected_updated_at != expected:
        raise ConflictError(
            "mini-app changed while the model was responding", code="mini_app_version_conflict"
        )
    if proposal.entity_schema is None or proposal.ui_spec is None:
        raise ValidationError(
            "apply response requires full schema and UI", code="invalid_model_output"
        )
    schema = validate_entity_schema(proposal.entity_schema).model_dump()
    ui_spec = validate_ui_spec(proposal.ui_spec).model_dump()
    before = _mini_snapshot(app)
    before_version = expected
    app.entity_schema, app.ui_spec = schema, ui_spec
    app.build_status, app.build_error, app.updated_at = "pending", None, datetime.now(UTC)
    after = _mini_snapshot(app)
    mutation = ChatMutation(
        tenant_id=chat_session.tenant_id,
        session_id=chat_session.id,
        message_id=user_message.id,
        target_type="mini_app",
        target_id=app.id,
        before_snapshot=before,
        after_snapshot=after,
        before_version=before_version,
        after_version=app.updated_at.isoformat(),
        status="applied",
    )
    db.add(mutation)
    db.commit()
    pool: ArqRedis | None = ctx.get("redis") or ctx.get("arq_redis")
    if pool is None:
        _restore_mini_app(db, app, before)
        mutation.status, mutation.undone_at = "undone", datetime.now(UTC)
        db.commit()
        raise RuntimeError("ARQ worker Redis context is unavailable; mini-app change restored")
    try:
        await enqueue_build(pool, str(app.id))
    except Exception:
        _restore_mini_app(db, app, before)
        mutation.status, mutation.undone_at = "undone", datetime.now(UTC)
        db.commit()
        raise
    return (
        proposal.summary,
        {
            "action": "apply",
            "mutation_id": str(mutation.id),
            "build_status": app.build_status,
            "app_updated_at": app.updated_at.isoformat(),
        },
        completion,
    )


async def process_mutation_message(
    ctx: dict[str, Any], db: Session, chat_session: ChatSession, user_message: ChatMessage
) -> tuple[str, dict[str, Any], CompletionResult]:
    if chat_session.scope == "graph_authoring" and chat_session.target_type == "workflow":
        return await _process_graph(db, chat_session, user_message)
    if chat_session.scope == "mini_app_edit" and chat_session.target_type == "mini_app":
        return await _process_mini_app(ctx, db, chat_session, user_message)
    raise ValidationError("unsupported chat scope/target", code="unsupported_chat_scope")


def _restore_mini_app(db: Session, app: MiniApp, snapshot: dict[str, Any]) -> None:
    app.entity_schema = snapshot["entity_schema"]
    app.ui_spec = snapshot["ui_spec"]
    app.build_status = snapshot.get("build_status", "pending")
    app.build_error = snapshot.get("build_error")
    app.updated_at = datetime.now(UTC)
    db.commit()


async def undo_mutation(db: Session, mutation: ChatMutation, pool: ArqRedis) -> dict[str, Any]:
    if mutation.target_type == "workflow":
        workflow = db.get(Workflow, mutation.target_id)
        if workflow is None or str(workflow.version) != mutation.after_version:
            raise ConflictError(
                "workflow changed after this mutation", code="undo_version_conflict"
            )
        graph = mutation.before_snapshot
        restored = replace_workflow_graph(
            db,
            workflow.id,
            role="builder",
            nodes=graph.get("nodes", []),
            edges=graph.get("edges", []),
        )
        mutation.status, mutation.undone_at = "undone", datetime.now(UTC)
        db.commit()
        return {"mutation_id": str(mutation.id), "status": "undone", "graph": restored}
    app = db.get(MiniApp, mutation.target_id)
    if app is None or app.updated_at.isoformat() != mutation.after_version:
        raise ConflictError("mini-app changed after this mutation", code="undo_version_conflict")
    current = _mini_snapshot(app)
    _restore_mini_app(db, app, mutation.before_snapshot)
    mutation.status, mutation.undone_at = "undone", datetime.now(UTC)
    try:
        await enqueue_build(pool, str(app.id))
    except Exception:
        _restore_mini_app(db, app, current)
        mutation.status, mutation.undone_at = "applied", None
        db.commit()
        raise
    db.commit()
    return {
        "mutation_id": str(mutation.id),
        "status": "undone",
        "build_status": app.build_status,
        "app_updated_at": app.updated_at.isoformat(),
    }
