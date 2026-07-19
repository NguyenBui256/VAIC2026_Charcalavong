"""Unit tests for `app.core.deps.crud_audit_ids` — pins OQ-1 convention."""

from __future__ import annotations

import uuid

from app.core.deps import crud_audit_ids


def test_crud_audit_ids_run_id_matches_entity_id() -> None:
    """`run_id` is the CRUD entity's own id, stringified."""
    entity_id = str(uuid.uuid4())
    run_id, _step_id = crud_audit_ids(entity_id)
    assert run_id == entity_id


def test_crud_audit_ids_step_id_is_valid_uuid() -> None:
    """`step_id` is a valid UUID string (uuid7)."""
    entity_id = str(uuid.uuid4())
    _run_id, step_id = crud_audit_ids(entity_id)
    assert isinstance(uuid.UUID(step_id), uuid.UUID)


def test_crud_audit_ids_step_id_distinct_each_call() -> None:
    """Calling twice with the same entity_id yields two different step_ids."""
    entity_id = str(uuid.uuid4())
    _run_id_1, step_id_1 = crud_audit_ids(entity_id)
    _run_id_2, step_id_2 = crud_audit_ids(entity_id)
    assert step_id_1 != step_id_2
