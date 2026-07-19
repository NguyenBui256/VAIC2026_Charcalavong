"""Unit tests for `schema_validation` (Story 2.6 T7.1, AC1/AC2/AC3)."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.modules.agent_builder.schema_validation import (
    validate_instance,
    validate_schema_document,
)


def test_valid_draft_2020_12_schema_accepted() -> None:
    """A well-formed draft-2020-12 schema passes without raising (AC1)."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    validate_schema_document(schema)  # no raise


def test_malformed_schema_rejected() -> None:
    """A structurally invalid schema (bad `type` value) raises ValidationError (AC1)."""
    bad_schema = {"type": "not-a-real-json-type"}
    with pytest.raises(ValidationError) as exc_info:
        validate_schema_document(bad_schema)
    assert exc_info.value.code == "invalid_schema"


def test_non_dict_schema_rejected() -> None:
    """A non-object schema payload is rejected before reaching jsonschema."""
    with pytest.raises(ValidationError):
        validate_schema_document("not a schema")  # type: ignore[arg-type]


def test_instance_validation_returns_errors_for_mismatch() -> None:
    """A payload missing a required field returns a non-empty error list (AC2)."""
    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    errors = validate_instance(schema, {})
    assert errors
    assert any("query" in e for e in errors)


def test_instance_validation_empty_for_valid_payload() -> None:
    """A conforming payload returns an empty error list (AC2/AC3)."""
    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    errors = validate_instance(schema, {"query": "hello"})
    assert errors == []
