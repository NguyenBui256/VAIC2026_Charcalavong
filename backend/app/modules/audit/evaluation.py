"""Persistence adapter for external evaluator results."""

from __future__ import annotations

import uuid

from app.core.db import SessionLocal
from app.core.ids import uuid7
from app.core.ports.audit import EventRecord
from app.core.ports.evaluation import EvaluationPort, EvaluationResult
from app.core.tenant_context import set_tenant_session_var
from app.modules.audit.models import AuditEvaluation
from app.modules.audit.sink import PostgresAuditSink


class PostgresEvaluationSink(EvaluationPort):
    def record(self, result: EvaluationResult) -> uuid.UUID:
        evaluation_id = uuid7()
        with SessionLocal() as db:
            set_tenant_session_var(db, result.context.tenant_id)
            db.add(
                AuditEvaluation(
                    id=evaluation_id,
                    tenant_id=result.context.tenant_id,
                    session_id=result.context.session_id,
                    evaluator_name=result.evaluator_name,
                    evaluator_version=result.evaluator_version,
                    evaluator_type=result.evaluator_type,
                    status=result.status,
                    score=result.score,
                    metrics=result.metrics,
                    criteria=result.criteria,
                    evidence_span_ids=[str(value) for value in result.evidence_span_ids],
                    requested_by_user_id=result.requested_by_user_id,
                    provider=result.provider,
                    model=result.model,
                    overall_pass=result.overall_pass,
                    summary=result.summary,
                    assessment=result.assessment,
                    insights=result.insights,
                    issues=result.issues,
                    strengths=result.strengths,
                    context_manifest=result.context_manifest,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    latency_ms=result.latency_ms,
                    estimated_cost_usd=result.estimated_cost_usd,
                )
            )
            db.commit()
        PostgresAuditSink().emit_event(
            EventRecord(
                context=result.context,
                event_type="evaluation.completed"
                if result.status == "completed"
                else "evaluation.failed",
                phase="end",
                status="completed" if result.status == "completed" else "failed",
                output={
                    "evaluation_id": str(evaluation_id),
                    "score": result.score,
                    "metrics": result.metrics,
                    "criteria": result.criteria,
                    "overall_pass": result.overall_pass,
                    "provider": result.provider,
                    "model": result.model,
                },
            )
        )
        return evaluation_id
