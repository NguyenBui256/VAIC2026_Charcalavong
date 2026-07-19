"""Generate a realistic, fully-linked Audit V2 Trace Session fixture."""

from __future__ import annotations

import argparse
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.core.db import AdminSessionLocal
from app.core.ids import uuid7
from app.core.ports.audit import (
    EventRecord,
    ExecutionContext,
    SessionEnd,
    SessionStart,
    SpanEnd,
    SpanStart,
)
from app.core.ports.evaluation import EvaluationResult
from app.core.tenant_context import set_tenant_context
from app.modules.audit.evaluation import PostgresEvaluationSink
from app.modules.audit.sink import PostgresAuditSink
from app.modules.tenant.models import Department, Tenant, User


def seed_audit_demo(event_target: int = 20) -> uuid.UUID:
    with AdminSessionLocal() as db:
        tenant = db.execute(select(Tenant).where(Tenant.name == "SHB Demo")).scalar_one()
        departments = (
            db.execute(select(Department).where(Department.tenant_id == tenant.id)).scalars().all()
        )
        users = db.execute(select(User).where(User.tenant_id == tenant.id)).scalars().all()
    set_tenant_context(tenant.id)
    credit = next((item for item in departments if item.name == "Credit"), departments[0])
    # The default UI login is the demo builder. Seed the run under that actor
    # so builder-scoped RBAC can display its own trace without weakening the
    # production authorization rules. Managers/operators retain their normal
    # tenant/department visibility.
    initiator = next((item for item in users if item.role == "builder"), users[0])
    run_id = uuid7()
    base = ExecutionContext(
        tenant_id=tenant.id,
        session_id=run_id,
        run_id=run_id,
        trace_id=uuid7(),
        correlation_id=uuid7(),
        department_id=credit.id,
    )
    sink = PostgresAuditSink()
    sink.start_session(
        SessionStart(
            context=base,
            name="Business Loan Pre-Screen · Acme Trading",
            workflow_version="2.1.0",
            trigger_type="manual",
            initiator_user_id=initiator.id,
            input={
                "request": "Pre-screen loan application LOAN-2026-0143",
                "account_number": "1234567890123456",
                "authorization": "Bearer demo-secret-must-never-be-stored",
            },
            attributes={"case_id": "LOAN-2026-0143", "environment": "demo"},
        )
    )
    root = sink.start_span(
        SpanStart(
            context=base,
            node_type="orchestrator",
            name="Dynamic task decomposition",
            actor_type="orchestrator",
            model="claude-sonnet",
            provider="anthropic",
            input={"workflow": "Cross-department business loan pre-screen"},
        )
    )
    sink.emit_event(
        EventRecord(
            context=root,
            event_type="orchestrator.decomposed",
            output={
                "task_count": 3,
                "routing_rationale": "Credit, Compliance and Operations skills",
            },
        )
    )

    evidence: list[uuid.UUID] = []
    agent_names = ("Credit Analyst", "Compliance Analyst", "Operations Analyst")
    for index, name in enumerate(agent_names):
        agent_id = uuid7()
        agent = sink.start_span(
            SpanStart(
                context=root.model_copy(
                    update={
                        "agent_id": agent_id,
                        "task_id": uuid7(),
                        "department_id": departments[index % len(departments)].id,
                    }
                ),
                node_type="agent",
                name=name,
                actor_type="agent",
                logical_node_id=f"specialist-{index}",
                input={
                    "task": f"Perform {name.lower()} assessment",
                    "criteria": {"confidence_floor": 0.8},
                },
            )
        )
        evidence.append(agent.span_id)  # type: ignore[arg-type]
        if index == 0:
            rag = sink.start_span(
                SpanStart(
                    context=agent,
                    node_type="kb",
                    name="Retrieve lending policy",
                    actor_type="agent",
                    kb_id=uuid7(),
                    kb_version="2026.07",
                    input={"query": "business loan debt service thresholds", "top_k": 5},
                )
            )
            sink.emit_event(
                EventRecord(
                    context=rag,
                    event_type="kb.retrieved",
                    output={
                        "chunks": [
                            {"document": "Credit Policy 2026", "chunk_id": "cp-42", "score": 0.94}
                        ]
                    },
                )
            )
            sink.end_span(SpanEnd(context=rag, output={"passage_count": 5, "cited": ["cp-42"]}))
        tool = sink.start_span(
            SpanStart(
                context=agent,
                node_type="tool",
                name=f"{name} validation tool",
                actor_type="tool",
                tool_name=(
                    "financial-ratio-calculator",
                    "sanctions-check",
                    "doc-checklist-verifier",
                )[index],
                tool_version="1.2",
                input={"case_id": "LOAN-2026-0143", "api_key": "must-redact"},
            )
        )
        if index == 1:
            sink.emit_event(
                EventRecord(
                    context=tool,
                    event_type="tool.validated",
                    output={"input_schema": "valid"},
                )
            )
        sink.end_span(SpanEnd(context=tool, output={"success": True, "flags": []}))
        llm = sink.start_span(
            SpanStart(
                context=agent,
                node_type="llm",
                name=f"Synthesize {name} result",
                actor_type="agent",
                provider="anthropic",
                model="claude-sonnet-4-5",
                input={
                    "messages": [
                        {"role": "user", "content": "Return a grounded structured verdict"}
                    ]
                },
            )
        )
        sink.emit_event(
            EventRecord(
                context=llm,
                event_type="llm.first_token",
                phase="progress",
                status="running",
                attributes={"ttft_ms": 184 + index * 20},
            )
        )
        sink.end_span(
            SpanEnd(
                context=llm,
                output={
                    "verdict": "pass",
                    "confidence": 0.91 - index * 0.03,
                    "citations": ["cp-42"] if index == 0 else [],
                },
                input_tokens=900 + index * 120,
                output_tokens=240 + index * 30,
                cached_tokens=100,
                estimated_cost_usd=Decimal("0.0084"),
                ttft_ms=184 + index * 20,
                attributes={"finish_reason": "end_turn"},
            )
        )
        sink.emit_event(
            EventRecord(
                context=agent,
                event_type="agent.feedback_emitted",
                output={
                    "confidence": 0.91 - index * 0.03,
                    "flags": [],
                    "rationale": "Criteria satisfied",
                },
            )
        )
        sink.end_span(SpanEnd(context=agent, output={"status": "ready_for_aggregation"}))

    # Scale fixture deterministically for virtualization/performance checks.
    with AdminSessionLocal() as db:
        from app.modules.audit.models import AuditSession

        current = db.get(AuditSession, run_id).last_sequence
    while current < max(1, event_target - 3):
        sink.emit_event(
            EventRecord(
                context=root,
                event_type="orchestrator.decision_recorded",
                output={"decision": "retain evidence", "ordinal": current},
            )
        )
        current += 1

    sink.emit_event(
        EventRecord(
            context=root,
            event_type="orchestrator.aggregated",
            output={"used_agent_results": [str(value) for value in evidence], "dropped": []},
        )
    )
    mini_app = sink.start_span(
        SpanStart(
            context=root,
            node_type="mini_app",
            name="Provision Loan Case Mini-App",
            actor_type="system",
            input={"visibility": "Need-Auth", "entity": "LoanCase"},
        )
    )
    sink.emit_event(
        EventRecord(
            context=mini_app,
            event_type="mini_app.validated",
            output={"schema_valid": True},
        )
    )
    sink.end_span(
        SpanEnd(context=mini_app, output={"app_id": str(uuid7()), "path": "/apps/loan-case"})
    )
    sink.end_span(
        SpanEnd(context=root, output={"decision": "approve_for_human_review", "confidence": 0.88})
    )
    PostgresEvaluationSink().record(
        EvaluationResult(
            context=base,
            evaluator_name="Loan policy rubric",
            evaluator_version="1.0",
            score=Decimal("0.94"),
            metrics={"groundedness": 0.96, "tool_compliance": 1.0},
            criteria=[
                {"name": "all departments responded", "passed": True},
                {"name": "policy cited", "passed": True},
            ],
            evidence_span_ids=evidence,
        )
    )
    sink.end_session(
        SessionEnd(
            context=base,
            status="completed",
            output={"decision": "approve_for_human_review", "mini_app": "/apps/loan-case"},
        )
    )
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=20)
    args = parser.parse_args()
    print(seed_audit_demo(args.events))


if __name__ == "__main__":
    main()
