"""JSON Schema draft 2020-12 validation helper (Story 2.6 T2).

Thin wrapper over ``jsonschema``. Two responsibilities:

1. ``validate_schema_document`` — assert a submitted ``input_schema`` /
   ``output_schema`` is itself a *valid* draft-2020-12 schema document
   (AC1: schema-of-schemas check, run at Tool registration time).
2. ``validate_instance`` — validate a payload (Tool invocation input or
   output) against a schema, returning human-readable error strings
   (AC2 input validation, AC3 output validation).

Never silently accept an invalid schema/instance — callers translate a
non-empty error list / raised ``ValidationError`` into a structured
rejection (`tool.rejected` audit entry per AC2/AC3).
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from app.core.errors import ValidationError

__all__ = ["validate_schema_document", "validate_instance"]


def validate_schema_document(schema: dict[str, Any]) -> None:
    """Assert `schema` is itself a valid JSON Schema draft 2020-12 document.

    Raises ValidationError (structured, 400) if the schema is malformed —
    NOT just that instances fail to validate against it (AC1).
    """
    if not isinstance(schema, dict):
        raise ValidationError(
            "Schema must be a JSON object", code="invalid_schema"
        )
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValidationError(
            f"Schema is not a valid draft 2020-12 document: {exc.message}",
            code="invalid_schema",
            details={"path": list(exc.path)},
        ) from exc


def validate_instance(schema: dict[str, Any], instance: dict[str, Any]) -> list[str]:
    """Validate `instance` against `schema`. Returns error strings (empty = valid).

    Used for both input (AC2) and output (AC3) validation at invocation time.
    """
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
