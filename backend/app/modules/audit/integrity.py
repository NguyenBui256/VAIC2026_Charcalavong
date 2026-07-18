"""Audit completeness and hash-chain verification."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent, AuditPayload, AuditSession, AuditSpan


def verify_session(db: Session, session_id: uuid.UUID) -> dict[str, Any]:
    session = db.get(AuditSession, session_id)
    if session is None:
        raise LookupError("audit session not found")
    events = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == session_id)
            .order_by(AuditEvent.sequence_no)
        )
        .scalars()
        .all()
    )
    payloads = {
        p.id: p
        for p in db.execute(
            select(AuditPayload).where(AuditPayload.tenant_id == session.tenant_id)
        ).scalars()
    }
    problems: list[str] = []
    referenced_payload_ids = {
        payload_id
        for event in events
        for payload_id in (event.input_payload_id, event.output_payload_id)
        if payload_id is not None
    }
    for payload_id in referenced_payload_ids:
        payload = payloads.get(payload_id)
        if payload is None:
            problems.append(f"missing payload {payload_id}")
            continue
        payload_digest = hashlib.sha256(_canonical(payload.data)).hexdigest()
        if payload_digest != payload.sha256:
            problems.append(f"payload digest mismatch for {payload_id}")
    previous = ""
    for expected, event in enumerate(events, start=1):
        if event.sequence_no != expected:
            problems.append(f"sequence gap: expected {expected}, found {event.sequence_no}")
        if event.prev_hash != previous:
            problems.append(f"previous hash mismatch at sequence {event.sequence_no}")
        evidence = {
            "event_id": str(event.id),
            "session_id": str(event.session_id),
            "span_id": str(event.span_id or ""),
            "sequence_no": event.sequence_no,
            "occurred_at": event.occurred_at.isoformat(),
            "event_type": event.event_type,
            "status": event.status,
            "input_digest": payloads[event.input_payload_id].sha256
            if event.input_payload_id
            else "",
            "output_digest": payloads[event.output_payload_id].sha256
            if event.output_payload_id
            else "",
            "attributes": event.attributes or {},
            "prev_hash": event.prev_hash,
        }
        actual = hashlib.sha256(_canonical(evidence)).hexdigest()
        if actual != event.event_hash:
            problems.append(f"event hash mismatch at sequence {event.sequence_no}")
        previous = event.event_hash
    if previous != session.last_hash or len(events) != session.last_sequence:
        problems.append("session head does not match event chain")
    running = (
        db.execute(
            select(AuditSpan.id).where(
                AuditSpan.session_id == session_id,
                AuditSpan.status == "running",
            )
        )
        .scalars()
        .all()
    )
    if session.status not in {"running", "awaiting_human"} and running:
        problems.append(f"{len(running)} orphan running span(s)")
    return {
        "valid": not problems,
        "event_count": len(events),
        "last_hash": previous,
        "problems": problems,
        "orphan_span_ids": [str(value) for value in running],
    }


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
