"""Tenant-scoped Audit V2 explorer, trace, SSE and signed export APIs."""

from __future__ import annotations

import base64
import json
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.core.ids import uuid7
from app.core.jobs import enqueue_job_with_context
from app.core.ports.audit import EventRecord, ExecutionContext
from app.core.settings import get_settings
from app.core.tenant_context import set_tenant_session_var
from app.modules.audit.integrity import verify_session
from app.modules.audit.models import (
    AuditEvaluation,
    AuditEvaluationCriterion,
    AuditEvaluationJob,
    AuditEvent,
    AuditPayload,
    AuditSession,
    AuditSpan,
    TenantAuditKey,
)
from app.modules.audit.signing import sign_document
from app.modules.audit.sink import PostgresAuditSink
from app.modules.tenant.routes import get_tenant_session

router = APIRouter(prefix="/audit", tags=["audit"])
TENANT_SESSION = Depends(get_tenant_session)


class CriterionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)


class CriterionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2000)


class EvaluationCreate(BaseModel):
    criterion_ids: list[uuid.UUID] = Field(min_length=1, max_length=30)


def _ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": jsonable_encoder(data), "error": None, "meta": meta or {}}


def _identity(request: Request) -> tuple[uuid.UUID, uuid.UUID | None, str, uuid.UUID]:
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    if tenant_id is None or user_id is None:
        raise AuthorizationError("Authentication context is required")
    department_id = getattr(request.state, "department_id", None)
    return (
        uuid.UUID(str(user_id)),
        uuid.UUID(str(department_id)) if department_id else None,
        str(getattr(request.state, "role", "")),
        uuid.UUID(str(tenant_id)),
    )


def _visible_session(db: Session, request: Request, session_id: uuid.UUID) -> AuditSession:
    user_id, department_id, role, tenant_id = _identity(request)
    row = db.execute(
        select(AuditSession).where(
            AuditSession.id == session_id,
            AuditSession.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Audit session not found")
    if role == "manager":
        return row
    department_participates = department_id is not None and (
        row.department_id == department_id
        or db.scalar(
            select(
                exists().where(
                    and_(
                        AuditSpan.session_id == row.id,
                        AuditSpan.department_id == department_id,
                    )
                )
            )
        )
    )
    if role == "operator" and department_participates:
        return row
    if role == "builder" and (row.initiator_user_id == user_id or department_participates):
        return row
    raise NotFoundError("Audit session not found")


def _payload_allowed(request: Request, session: AuditSession, payload: AuditPayload) -> bool:
    user_id, department_id, role, _ = _identity(request)
    if role == "manager":
        return True
    if payload.classification == "restricted":
        return False
    if role == "builder" and session.initiator_user_id == user_id:
        return True
    return department_id is not None and payload.department_id == department_id


def _criterion_dict(row: AuditEvaluationCriterion, user_id: uuid.UUID, role: str) -> dict[str, Any]:
    data = jsonable_encoder(row, exclude={"tenant_id"})
    data["can_edit"] = role == "manager" or (
        role == "builder" and row.created_by_user_id == user_id
    )
    return data


@router.get("/evaluation-criteria")
def list_evaluation_criteria(
    request: Request, include_archived: bool = False, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    user_id, _, role, tenant_id = _identity(request)
    query = select(AuditEvaluationCriterion).where(AuditEvaluationCriterion.tenant_id == tenant_id)
    if not include_archived:
        query = query.where(AuditEvaluationCriterion.is_active.is_(True))
    rows = (
        db.execute(query.order_by(AuditEvaluationCriterion.created_at, AuditEvaluationCriterion.id))
        .scalars()
        .all()
    )
    return _ok([_criterion_dict(row, user_id, role) for row in rows])


@router.post("/evaluation-criteria", status_code=status.HTTP_201_CREATED)
def create_evaluation_criterion(
    body: CriterionCreate, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    user_id, _, role, tenant_id = _identity(request)
    if role not in {"manager", "builder"}:
        raise AuthorizationError("Only managers and builders can create evaluation criteria")
    row = AuditEvaluationCriterion(
        id=uuid7(),
        tenant_id=tenant_id,
        name=body.name.strip(),
        description=body.description.strip(),
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("An active criterion with this name already exists") from exc
    db.refresh(row)
    return _ok(_criterion_dict(row, user_id, role))


@router.patch("/evaluation-criteria/{criterion_id}")
def update_evaluation_criterion(
    criterion_id: uuid.UUID, body: CriterionUpdate, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    user_id, _, role, tenant_id = _identity(request)
    row = db.execute(
        select(AuditEvaluationCriterion).where(
            AuditEvaluationCriterion.id == criterion_id,
            AuditEvaluationCriterion.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Evaluation criterion not found")
    if role != "manager" and not (role == "builder" and row.created_by_user_id == user_id):
        raise AuthorizationError("You cannot edit this evaluation criterion")
    if body.name is not None:
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description.strip()
    row.updated_by_user_id = user_id
    row.updated_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("An active criterion with this name already exists") from exc
    return _ok(_criterion_dict(row, user_id, role))


@router.delete("/evaluation-criteria/{criterion_id}")
def archive_evaluation_criterion(
    criterion_id: uuid.UUID, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    user_id, _, role, tenant_id = _identity(request)
    row = db.execute(
        select(AuditEvaluationCriterion).where(
            AuditEvaluationCriterion.id == criterion_id,
            AuditEvaluationCriterion.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Evaluation criterion not found")
    if role != "manager" and not (role == "builder" and row.created_by_user_id == user_id):
        raise AuthorizationError("You cannot archive this evaluation criterion")
    row.is_active = False
    row.updated_by_user_id = user_id
    row.updated_at = datetime.now(UTC)
    db.commit()
    return _ok({"id": row.id, "archived": True})


@router.post("/sessions/{session_id}/evaluations", status_code=status.HTTP_202_ACCEPTED)
async def create_session_evaluation(
    session_id: uuid.UUID, body: EvaluationCreate, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    row = _visible_session(db, request, session_id)
    user_id, department_id, role, tenant_id = _identity(request)
    if role not in {"manager", "builder"}:
        raise AuthorizationError("Only managers and builders can run evaluations")
    if row.status not in {"completed", "failed", "timed_out", "cancelled"}:
        raise ConflictError("Only terminal audit sessions can be evaluated")
    active = db.execute(
        select(AuditEvaluationJob).where(
            AuditEvaluationJob.session_id == session_id,
            AuditEvaluationJob.status.in_(
                ("queued", "collecting_context", "judging", "validating")
            ),
        )
    ).scalar_one_or_none()
    if active is not None:
        return _ok(active)
    unique_ids = list(dict.fromkeys(body.criterion_ids))
    criteria = (
        db.execute(
            select(AuditEvaluationCriterion).where(
                AuditEvaluationCriterion.tenant_id == tenant_id,
                AuditEvaluationCriterion.id.in_(unique_ids),
                AuditEvaluationCriterion.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    by_id = {item.id: item for item in criteria}
    if len(by_id) != len(unique_ids):
        raise ValidationError("One or more evaluation criteria are missing or archived")
    job = AuditEvaluationJob(
        id=uuid7(),
        tenant_id=tenant_id,
        session_id=session_id,
        requested_by_user_id=user_id,
        requester_role=role,
        requester_department_id=department_id,
        criteria_snapshot=[
            {"id": str(item.id), "name": item.name, "description": item.description}
            for item in (by_id[value] for value in unique_ids)
        ],
        boundary_sequence=row.last_sequence,
        boundary_hash=row.last_hash,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        active = db.execute(
            select(AuditEvaluationJob).where(
                AuditEvaluationJob.session_id == session_id,
                AuditEvaluationJob.status.in_(
                    ("queued", "collecting_context", "judging", "validating")
                ),
            )
        ).scalar_one()
        return _ok(active)
    context = ExecutionContext(
        tenant_id=tenant_id,
        session_id=row.id,
        run_id=row.run_id,
        trace_id=row.trace_id,
        correlation_id=row.correlation_id,
        department_id=row.department_id,
    )
    PostgresAuditSink().emit_event(
        EventRecord(
            context=context,
            event_type="evaluation.started",
            phase="start",
            status="running",
            input={"job_id": str(job.id), "criteria": job.criteria_snapshot},
        )
    )
    pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        await enqueue_job_with_context(
            pool, "evaluation_worker", job_id=str(job.id), evaluation_job_id=str(job.id)
        )
    except Exception as exc:
        job.status = job.phase = "failed"
        job.progress = 100
        job.error_code = type(exc).__name__
        job.error_message = "Evaluation worker queue is unavailable"
        job.ended_at = datetime.now(UTC)
        db.commit()
        raise
    finally:
        await pool.aclose()
    db.refresh(job)
    return _ok(job)


@router.get("/evaluation-jobs/{job_id}")
def get_evaluation_job(
    job_id: uuid.UUID, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    row = db.execute(
        select(AuditEvaluationJob).where(AuditEvaluationJob.id == job_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Evaluation job not found")
    _visible_session(db, request, row.session_id)
    return _ok(row)


@router.get("/sessions/{session_id}/evaluations/latest")
def get_latest_evaluation(
    session_id: uuid.UUID, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    _visible_session(db, request, session_id)
    row = (
        db.execute(
            select(AuditEvaluation)
            .where(AuditEvaluation.session_id == session_id)
            .order_by(AuditEvaluation.created_at.desc(), AuditEvaluation.id.desc())
        )
        .scalars()
        .first()
    )
    return _ok(jsonable_encoder(row, exclude={"tenant_id"}) if row else None)


@router.get("/sessions")
def list_sessions(
    request: Request,
    status: str | None = None,
    workflow_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    trigger_type: str | None = None,
    cursor: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = TENANT_SESSION,
) -> dict[str, Any]:
    user_id, user_department, role, tenant_id = _identity(request)
    query = select(AuditSession)
    filters = [AuditSession.tenant_id == tenant_id]
    if status:
        filters.append(AuditSession.status == status)
    if workflow_id:
        filters.append(AuditSession.workflow_id == workflow_id)
    if department_id:
        filters.append(AuditSession.department_id == department_id)
    if trigger_type:
        filters.append(AuditSession.trigger_type == trigger_type)
    if cursor:
        filters.append(AuditSession.id < cursor)
    if agent_id:
        filters.append(
            exists().where(
                and_(AuditSpan.session_id == AuditSession.id, AuditSpan.agent_id == agent_id)
            )
        )
    if role == "operator" and user_department:
        filters.append(
            or_(
                AuditSession.department_id == user_department,
                exists().where(
                    and_(
                        AuditSpan.session_id == AuditSession.id,
                        AuditSpan.department_id == user_department,
                    )
                ),
            )
        )
    elif role == "builder":
        ownership = AuditSession.initiator_user_id == user_id
        if user_department:
            ownership = or_(ownership, AuditSession.department_id == user_department)
        filters.append(ownership)
    elif role != "manager":
        filters.append(AuditSession.id.is_(None))
    rows = (
        db.execute(query.where(*filters).order_by(AuditSession.id.desc()).limit(limit + 1))
        .scalars()
        .all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return _ok(
        [_session_dict(row) for row in rows],
        {
            "next_cursor": str(rows[-1].id) if has_more and rows else None,
            "has_more": has_more,
        },
    )


@router.get("/events")
def explore_events(
    request: Request,
    event_type: str | None = None,
    agent_id: uuid.UUID | None = None,
    model: str | None = None,
    cursor: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = TENANT_SESSION,
) -> dict[str, Any]:
    user_id, department_id, role, tenant_id = _identity(request)
    visible = select(AuditSession.id).where(AuditSession.tenant_id == tenant_id)
    if role == "operator" and department_id:
        visible = visible.where(
            or_(
                AuditSession.department_id == department_id,
                exists().where(
                    and_(
                        AuditSpan.session_id == AuditSession.id,
                        AuditSpan.department_id == department_id,
                    )
                ),
            )
        )
    elif role == "builder":
        visible = visible.where(AuditSession.initiator_user_id == user_id)
    elif role != "manager":
        visible = visible.where(AuditSession.id.is_(None))
    query = select(AuditEvent).where(AuditEvent.session_id.in_(visible))
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
    if agent_id:
        query = query.where(AuditEvent.actor_id == agent_id)
    if cursor:
        query = query.where(AuditEvent.id < cursor)
    if model:
        query = query.where(
            exists().where(and_(AuditSpan.id == AuditEvent.span_id, AuditSpan.model == model))
        )
    rows = db.execute(query.order_by(AuditEvent.id.desc()).limit(limit + 1)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return _ok(
        [_event_dict(row) for row in rows],
        {
            "next_cursor": str(rows[-1].id) if has_more and rows else None,
            "has_more": has_more,
        },
    )


@router.get("/sessions/{session_id}")
def get_session(
    session_id: uuid.UUID, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    row = _visible_session(db, request, session_id)
    evaluations = (
        db.execute(
            select(AuditEvaluation)
            .where(AuditEvaluation.session_id == session_id)
            .order_by(AuditEvaluation.created_at.desc())
        )
        .scalars()
        .all()
    )
    data = _session_dict(row)
    data["integrity"] = verify_session(db, session_id)
    data["evaluations"] = [jsonable_encoder(item, exclude={"tenant_id"}) for item in evaluations]
    data["latest_evaluation"] = data["evaluations"][0] if data["evaluations"] else None
    return _ok(data)


@router.get("/sessions/{session_id}/spans")
def get_spans(
    session_id: uuid.UUID,
    request: Request,
    node_type: str | None = None,
    status: str | None = None,
    db: Session = TENANT_SESSION,
) -> dict[str, Any]:
    _visible_session(db, request, session_id)
    query = select(AuditSpan).where(AuditSpan.session_id == session_id)
    if node_type:
        query = query.where(AuditSpan.node_type == node_type)
    if status:
        query = query.where(AuditSpan.status == status)
    rows = db.execute(query.order_by(AuditSpan.started_at, AuditSpan.id)).scalars().all()
    return _ok([_span_dict(row) for row in rows], {"count": len(rows)})


@router.get("/sessions/{session_id}/events")
def get_events(
    session_id: uuid.UUID,
    request: Request,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    event_type: str | None = None,
    db: Session = TENANT_SESSION,
) -> dict[str, Any]:
    _visible_session(db, request, session_id)
    query = select(AuditEvent).where(
        AuditEvent.session_id == session_id,
        AuditEvent.sequence_no > after,
    )
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
    rows = db.execute(query.order_by(AuditEvent.sequence_no).limit(limit + 1)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return _ok(
        [_event_dict(row) for row in rows],
        {
            "next_after": rows[-1].sequence_no if rows else after,
            "has_more": has_more,
        },
    )


@router.get("/sessions/{session_id}/graph")
def get_graph(
    session_id: uuid.UUID, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    _visible_session(db, request, session_id)
    spans = (
        db.execute(
            select(AuditSpan)
            .where(AuditSpan.session_id == session_id)
            .order_by(AuditSpan.started_at)
        )
        .scalars()
        .all()
    )
    edges: list[dict[str, Any]] = []
    for span in spans:
        if span.parent_span_id:
            edges.append(
                {
                    "id": f"parent:{span.parent_span_id}:{span.id}",
                    "source": str(span.parent_span_id),
                    "target": str(span.id),
                    "type": "parent",
                }
            )
        for dependency in (span.attributes or {}).get("dependency_span_ids", []):
            edges.append(
                {
                    "id": f"dependency:{dependency}:{span.id}",
                    "source": str(dependency),
                    "target": str(span.id),
                    "type": "dependency",
                }
            )
    return _ok({"nodes": [_span_dict(span) for span in spans], "edges": edges})


@router.get("/payloads/{payload_id}")
def get_payload(
    payload_id: uuid.UUID, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    _, _, _, tenant_id = _identity(request)
    payload = db.execute(
        select(AuditPayload).where(
            AuditPayload.id == payload_id,
            AuditPayload.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if payload is None:
        raise NotFoundError("Audit payload not found")
    session = (
        db.execute(
            select(AuditSession).where(
                or_(
                    AuditSession.input_payload_id == payload_id,
                    AuditSession.result_payload_id == payload_id,
                    exists().where(
                        and_(
                            AuditEvent.session_id == AuditSession.id,
                            or_(
                                AuditEvent.input_payload_id == payload_id,
                                AuditEvent.output_payload_id == payload_id,
                            ),
                        )
                    ),
                    exists().where(
                        and_(
                            AuditSpan.session_id == AuditSession.id,
                            or_(
                                AuditSpan.input_payload_id == payload_id,
                                AuditSpan.output_payload_id == payload_id,
                            ),
                        )
                    ),
                )
            )
        )
        .scalars()
        .first()
    )
    if session is None:
        raise NotFoundError("Audit payload not found")
    _visible_session(db, request, session.id)
    if not _payload_allowed(request, session, payload):
        raise AuthorizationError("Raw audit payload is outside your access scope")
    return _ok(
        {
            "id": payload.id,
            "content_type": payload.content_type,
            "classification": payload.classification,
            "data": payload.data,
            "byte_size": payload.byte_size,
            "sha256": payload.sha256,
            "redaction_count": payload.redaction_count,
            "redaction_paths": payload.redaction_paths,
        }
    )


@router.get("/sessions/{session_id}/stream")
def stream_session(
    session_id: uuid.UUID,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    after: int = Query(default=0, ge=0),
    db: Session = TENANT_SESSION,
) -> StreamingResponse:
    row = _visible_session(db, request, session_id)
    start = int(last_event_id) if last_event_id and last_event_id.isdigit() else after
    return StreamingResponse(
        _event_stream(row.tenant_id, session_id, start),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/export")
def export_session(
    session_id: uuid.UUID, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    row = _visible_session(db, request, session_id)
    events = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == session_id)
            .order_by(AuditEvent.sequence_no)
        )
        .scalars()
        .all()
    )
    spans = db.execute(select(AuditSpan).where(AuditSpan.session_id == session_id)).scalars().all()
    evaluations = (
        db.execute(
            select(AuditEvaluation)
            .where(AuditEvaluation.session_id == session_id)
            .order_by(AuditEvaluation.created_at, AuditEvaluation.id)
        )
        .scalars()
        .all()
    )
    payload_ids = {
        value
        for event in events
        for value in (event.input_payload_id, event.output_payload_id)
        if value
    }
    payloads = {
        payload.id: payload
        for payload in db.execute(
            select(AuditPayload).where(AuditPayload.id.in_(payload_ids))
        ).scalars()
    }
    export_events = []
    redactions = []
    for event in events:
        item = _event_dict(event)
        for field, payload_id in (
            ("input", event.input_payload_id),
            ("output", event.output_payload_id),
        ):
            payload = payloads.get(payload_id)
            if payload and _payload_allowed(request, row, payload):
                item[field] = payload.data
            elif payload:
                item[field] = {"redacted": True, "reason": "access_scope", "sha256": payload.sha256}
                redactions.append(
                    {"event_id": str(event.id), "field": field, "reason": "access_scope"}
                )
        export_events.append(item)
    # Sign the exact JSON-compatible representation returned by the API.
    # This avoids datetime/Decimal encoders changing bytes after signing.
    document = jsonable_encoder(
        {
            "schema_version": 2,
            "session": _session_dict(row),
            "exported_at": datetime.now(UTC).isoformat(),
            "entry_count": len(events),
            "spans": [_span_dict(span) for span in spans],
            "events": export_events,
            "evaluations": [jsonable_encoder(item, exclude={"tenant_id"}) for item in evaluations],
            "redaction_manifest": redactions,
            "integrity": verify_session(db, session_id),
        }
    )
    signature = sign_document(db, row.tenant_id, document)
    db.commit()
    actor, _, _, _ = _identity(request)
    PostgresAuditSink().emit_event(
        EventRecord(
            context=ExecutionContext(
                tenant_id=row.tenant_id,
                session_id=row.id,
                run_id=row.run_id,
                trace_id=row.trace_id,
                correlation_id=row.correlation_id,
                department_id=row.department_id,
            ),
            event_type="audit.exported",
            output={
                "entry_count": len(events),
                "key_id": signature["key_id"],
                "exported_by_user_id": str(actor),
            },
        )
    )
    return _ok({"document": document, "signature": signature})


@router.get("/keys/{key_id}/public")
def get_public_key(
    key_id: uuid.UUID, request: Request, db: Session = TENANT_SESSION
) -> dict[str, Any]:
    _, _, _, tenant_id = _identity(request)
    key = db.execute(
        select(TenantAuditKey).where(
            TenantAuditKey.id == key_id,
            TenantAuditKey.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if key is None:
        raise NotFoundError("Audit signing key not found")
    return _ok(
        {
            "key_id": key.id,
            "version": key.version,
            "algorithm": key.algorithm,
            "fingerprint": key.fingerprint,
            "public_key": base64.b64encode(key.public_key).decode(),
        }
    )


def _event_stream(tenant_id: uuid.UUID, session_id: uuid.UUID, after: int) -> Iterator[str]:
    current = after
    heartbeat = time.monotonic()
    redis_client = None
    subscription = None
    try:
        try:
            import redis

            redis_client = redis.Redis.from_url(get_settings().redis_url)
            subscription = redis_client.pubsub(ignore_subscribe_messages=True)
            subscription.subscribe(f"audit:{session_id}")
        except Exception:
            # PostgreSQL remains the source of truth. A missing Redis connection
            # only changes wake-up latency and must never make the stream unusable.
            subscription = None

        while True:
            with SessionLocal() as db:
                set_tenant_session_var(db, tenant_id)
                rows = (
                    db.execute(
                        select(AuditEvent)
                        .where(
                            AuditEvent.tenant_id == tenant_id,
                            AuditEvent.session_id == session_id,
                            AuditEvent.sequence_no > current,
                        )
                        .order_by(AuditEvent.sequence_no)
                        .limit(200)
                    )
                    .scalars()
                    .all()
                )
                for row in rows:
                    current = row.sequence_no
                    data = json.dumps(jsonable_encoder(_event_dict(row)))
                    yield f"id: {current}\nevent: audit\ndata: {data}\n\n"

            if time.monotonic() - heartbeat > 15:
                heartbeat = time.monotonic()
                yield ": heartbeat\n\n"

            if subscription is not None:
                try:
                    subscription.get_message(timeout=2.0)
                    continue
                except Exception:
                    subscription = None
            time.sleep(2)
    finally:
        if subscription is not None:
            subscription.close()
        if redis_client is not None:
            redis_client.close()


def _session_dict(row: AuditSession) -> dict[str, Any]:
    return {
        column.name: getattr(row, column.name)
        for column in AuditSession.__table__.columns
        if column.name != "tenant_id"
    }


def _span_dict(row: AuditSpan) -> dict[str, Any]:
    return {
        column.name: getattr(row, column.name)
        for column in AuditSpan.__table__.columns
        if column.name != "tenant_id"
    }


def _event_dict(row: AuditEvent) -> dict[str, Any]:
    return {
        column.name: getattr(row, column.name)
        for column in AuditEvent.__table__.columns
        if column.name != "tenant_id"
    }
