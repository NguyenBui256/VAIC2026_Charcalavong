"""Asynchronous, evidence-grounded LLM evaluation for audit sessions."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from app.core.adapters.openai import OpenAiLlmAdapter
from app.core.jobs import tenant_aware_job
from app.core.ports.audit import EventRecord, ExecutionContext, SpanEnd, SpanStart
from app.core.ports.evaluation import EvaluationResult
from app.core.ports.llm import Message, ModelRef
from app.core.settings import get_settings
from app.modules.audit.evaluation import PostgresEvaluationSink
from app.modules.audit.models import (
    AuditEvaluationJob,
    AuditEvent,
    AuditPayload,
    AuditSession,
    AuditSpan,
)
from app.modules.audit.redaction import redact_payload
from app.modules.audit.sink import PostgresAuditSink
from app.modules.tenant.models import User


class CriterionResult(BaseModel):
    criterion_id: uuid.UUID
    name: str
    description: str = ""
    passed: bool
    confidence: float = Field(ge=0, le=1)
    rationale: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class JudgeOutput(BaseModel):
    criteria: list[CriterionResult]
    summary: str
    assessment: str
    insights: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_criteria(self) -> JudgeOutput:
        ids = [item.criterion_id for item in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion_id must be unique")
        return self


def _context(session: AuditSession) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=session.tenant_id,
        session_id=session.id,
        run_id=session.run_id,
        trace_id=session.trace_id,
        correlation_id=session.correlation_id,
        department_id=session.department_id,
    )


def _set_phase(db: Session, job: AuditEvaluationJob, status: str, progress: int) -> None:
    job.status = status
    job.phase = status
    job.progress = progress
    if status == "collecting_context" and job.started_at is None:
        job.started_at = datetime.now(UTC)
    db.commit()


def _payload_allowed(job: AuditEvaluationJob, session: AuditSession, payload: AuditPayload) -> bool:
    if job.requester_role == "manager":
        return True
    if payload.classification == "restricted":
        return False
    if job.requester_role == "builder" and session.initiator_user_id == job.requested_by_user_id:
        return True
    return (
        job.requester_department_id is not None
        and payload.department_id == job.requester_department_id
    )


def _authorize(db: Session, job: AuditEvaluationJob, session: AuditSession) -> User:
    user = db.execute(
        select(User).where(
            User.id == job.requested_by_user_id,
            User.tenant_id == job.tenant_id,
            User.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if user is None or user.role not in {"manager", "builder"}:
        raise PermissionError("Requester no longer has evaluation permission")
    if user.role == "builder":
        participates = db.scalar(
            select(
                exists().where(
                    and_(
                        AuditSpan.session_id == session.id,
                        AuditSpan.department_id == user.department_id,
                    )
                )
            )
        )
        if (
            session.initiator_user_id != user.id
            and session.department_id != user.department_id
            and not participates
        ):
            raise PermissionError("Requester no longer has access to this audit session")
    job.requester_role = user.role
    job.requester_department_id = user.department_id
    return user


def _build_context(
    db: Session, job: AuditEvaluationJob, session: AuditSession
) -> tuple[str, dict[str, Any]]:
    spans = (
        db.execute(
            select(AuditSpan)
            .where(AuditSpan.session_id == session.id)
            .order_by(AuditSpan.started_at, AuditSpan.id)
        )
        .scalars()
        .all()
    )
    events = (
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == session.id,
                AuditEvent.sequence_no <= job.boundary_sequence,
                ~AuditEvent.event_type.like("evaluation.%"),
            )
            .order_by(AuditEvent.sequence_no)
        )
        .scalars()
        .all()
    )
    payload_ids = {
        value
        for value in (session.input_payload_id, session.result_payload_id)
        if value is not None
    }
    for span in spans:
        payload_ids.update(
            value for value in (span.input_payload_id, span.output_payload_id) if value
        )
    for event in events:
        payload_ids.update(
            value for value in (event.input_payload_id, event.output_payload_id) if value
        )
    payloads = (
        db.execute(select(AuditPayload).where(AuditPayload.id.in_(payload_ids))).scalars().all()
        if payload_ids
        else []
    )
    allowed = [payload for payload in payloads if _payload_allowed(job, session, payload)]
    context = {
        "session": {
            "id": str(session.id),
            "name": session.name,
            "status": session.status,
            "trigger_type": session.trigger_type,
            "workflow_version": session.workflow_version,
            "failure_summary": session.failure_summary,
            "last_sequence": job.boundary_sequence,
            "last_hash": job.boundary_hash,
        },
        "spans": [
            {
                "id": str(span.id),
                "parent_span_id": str(span.parent_span_id) if span.parent_span_id else None,
                "node_type": span.node_type,
                "name": span.name,
                "status": span.status,
                "duration_ms": span.duration_ms,
                "provider": span.provider,
                "model": span.model,
                "tool_name": span.tool_name,
                "error_code": span.error_code,
                "error_message": span.error_message,
                "attributes": span.attributes,
            }
            for span in spans
        ],
        "events": [
            {
                "sequence": event.sequence_no,
                "span_id": str(event.span_id) if event.span_id else None,
                "type": event.event_type,
                "phase": event.phase,
                "status": event.status,
                "severity": event.severity,
                "attributes": event.attributes,
            }
            for event in events
        ],
        "payloads": [
            {
                "id": str(payload.id),
                "sha256": payload.sha256,
                "classification": payload.classification,
                "data": payload.data,
            }
            for payload in allowed
        ],
    }
    manifest = {
        "boundary_sequence": job.boundary_sequence,
        "boundary_hash": job.boundary_hash,
        "span_ids": [str(span.id) for span in spans],
        "event_sequences": [event.sequence_no for event in events],
        "payload_ids": [str(payload.id) for payload in allowed],
        "excluded_payload_count": len(payloads) - len(allowed),
    }
    return json.dumps(context, ensure_ascii=False, default=str, separators=(",", ":")), manifest


_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _parse_output(content: str, expected_ids: set[uuid.UUID]) -> JudgeOutput:
    clean = _JSON_FENCE.sub("", content.strip())
    result = JudgeOutput.model_validate(json.loads(clean))
    if {item.criterion_id for item in result.criteria} != expected_ids:
        raise ValueError("LLM result must contain exactly one result for every selected criterion")
    return result


def _system_prompt() -> str:
    return (
        "You are an audit evaluator. Judge only from supplied redacted evidence. "
        "Never invent evidence and never reveal chain-of-thought. Return JSON only with keys: "
        "criteria (criterion_id,name,description,passed,confidence,rationale,evidence[]), "
        "summary, assessment, insights[], issues[], strengths[], limitations[]. "
        "Evidence entries should reference span_id, event_sequence or payload_sha256."
    )


def process_evaluation_job(db: Session, job_id: uuid.UUID) -> uuid.UUID:
    job = db.execute(select(AuditEvaluationJob).where(AuditEvaluationJob.id == job_id)).scalar_one()
    session = db.execute(select(AuditSession).where(AuditSession.id == job.session_id)).scalar_one()
    base_context = _context(session)
    sink = PostgresAuditSink()
    evaluation_span: ExecutionContext | None = None
    try:
        _authorize(db, job, session)
        _set_phase(db, job, "collecting_context", 20)
        context_json, manifest = _build_context(db, job, session)
        settings = get_settings()
        adapter = OpenAiLlmAdapter(
            api_key=settings.llm_api_key or settings.openai_api_key or settings.anthropic_api_key,
            base_url=settings.llm_base_url or None,
            timeout=settings.llm_timeout_seconds,
        )
        model = ModelRef(provider=settings.llm_provider, model_name=settings.llm_model)
        evaluation_span = sink.start_span(
            SpanStart(
                context=base_context,
                node_type="evaluation",
                name="LLM session evaluation",
                actor_type="system",
                input={"criteria": job.criteria_snapshot},
                attributes={"job_id": str(job.id)},
            )
        )
        _set_phase(db, job, "judging", 55)
        max_chars = settings.evaluation_max_context_tokens * 4
        chunk_chars = settings.evaluation_chunk_tokens * 4
        evidence_digest = context_json
        total_input = total_output = total_latency = 0
        if len(context_json) > max_chars:
            summaries: list[str] = []
            for index in range(0, len(context_json), chunk_chars):
                chunk = context_json[index : index + chunk_chars]
                response = adapter.complete(
                    [
                        Message(
                            role="system",
                            content=(
                                "Extract concise audit evidence with exact span IDs, "
                                "event sequences and payload digests. Do not judge."
                            ),
                        ),
                        Message(role="user", content=chunk),
                    ],
                    model,
                    {"temperature": 0, "max_tokens": 1800},
                )
                summaries.append(response.content)
                total_input += response.usage.get("input_tokens", 0)
                total_output += response.usage.get("output_tokens", 0)
                total_latency += response.latency_ms
            evidence_digest = "\n\n--- CHUNK EVIDENCE ---\n".join(summaries)
            manifest["chunked"] = True
            manifest["chunk_count"] = len(summaries)
        else:
            manifest["chunked"] = False
            manifest["chunk_count"] = 1
        prompt = json.dumps(
            {"criteria": job.criteria_snapshot, "audit_evidence": evidence_digest},
            ensure_ascii=False,
        )
        response = adapter.complete(
            [
                Message(role="system", content=_system_prompt()),
                Message(role="user", content=prompt),
            ],
            model,
            {"temperature": 0, "max_tokens": 5000},
        )
        total_input += response.usage.get("input_tokens", 0)
        total_output += response.usage.get("output_tokens", 0)
        total_latency += response.latency_ms
        _set_phase(db, job, "validating", 85)
        expected_ids = {uuid.UUID(item["id"]) for item in job.criteria_snapshot}
        try:
            judged = _parse_output(response.content, expected_ids)
        except Exception as first_error:
            repair = adapter.complete(
                [
                    Message(role="system", content=_system_prompt()),
                    Message(
                        role="user",
                        content=(
                            f"Repair this invalid result. Validation error: {first_error}. "
                            f"Expected criterion IDs: {[str(value) for value in expected_ids]}"
                            f"\n\n{response.content}"
                        ),
                    ),
                ],
                model,
                {"temperature": 0, "max_tokens": 5000},
            )
            total_input += repair.usage.get("input_tokens", 0)
            total_output += repair.usage.get("output_tokens", 0)
            total_latency += repair.latency_ms
            judged = _parse_output(repair.content, expected_ids)
        safe = redact_payload(judged.model_dump(mode="json")).value
        criteria = safe["criteria"]
        passed = sum(1 for item in criteria if item["passed"])
        score = Decimal(passed) / Decimal(len(criteria))
        overall_pass = passed == len(criteria)
        evidence_spans = {
            uuid.UUID(str(evidence["span_id"]))
            for item in criteria
            for evidence in item.get("evidence", [])
            if evidence.get("span_id")
        }
        result = EvaluationResult(
            context=evaluation_span,
            evaluator_name="LLM Audit Judge",
            evaluator_version="1.0",
            evaluator_type="llm_judge",
            score=score,
            criteria=criteria,
            evidence_span_ids=list(evidence_spans),
            requested_by_user_id=job.requested_by_user_id,
            provider=settings.llm_provider,
            model=response.model,
            overall_pass=overall_pass,
            summary=safe["summary"],
            assessment=safe["assessment"],
            insights=safe["insights"],
            issues=safe["issues"],
            strengths=safe["strengths"],
            context_manifest={**manifest, "limitations": safe["limitations"]},
            input_tokens=total_input,
            output_tokens=total_output,
            latency_ms=total_latency,
        )
        evaluation_id = PostgresEvaluationSink().record(result)
        sink.end_span(
            SpanEnd(
                context=evaluation_span,
                output={"evaluation_id": str(evaluation_id), "overall_pass": overall_pass},
                input_tokens=total_input,
                output_tokens=total_output,
            )
        )
        job.evaluation_id = evaluation_id
        job.status = job.phase = "completed"
        job.progress = 100
        job.ended_at = datetime.now(UTC)
        db.commit()
        return evaluation_id
    except Exception as exc:
        db.rollback()
        job = db.execute(
            select(AuditEvaluationJob).where(AuditEvaluationJob.id == job_id)
        ).scalar_one()
        job.status = job.phase = "failed"
        job.progress = 100
        job.error_code = type(exc).__name__
        job.error_message = str(exc)[:2000]
        job.ended_at = datetime.now(UTC)
        db.commit()
        if evaluation_span is not None:
            sink.end_span(
                SpanEnd(
                    context=evaluation_span,
                    status="failed",
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
            )
        else:
            sink.emit_event(
                EventRecord(
                    context=base_context,
                    event_type="evaluation.failed",
                    phase="end",
                    status="failed",
                    severity="error",
                    output={"job_id": str(job_id), "error_code": type(exc).__name__},
                )
            )
        raise


@tenant_aware_job
async def evaluation_worker(ctx: dict[str, Any], evaluation_job_id: str) -> str:
    db: Session = ctx["session"]
    return str(process_evaluation_job(db, uuid.UUID(evaluation_job_id)))
