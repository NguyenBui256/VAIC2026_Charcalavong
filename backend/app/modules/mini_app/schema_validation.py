"""Entity-schema + UI-spec validation against the platform meta-schema (4-1).

Pure functions — no I/O. Rejection reasons are human-readable and surfaced
to the caller (audited as `mini_app.schema_rejected`).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.modules.mini_app.schemas import EntitySchema, FieldSpec, UiSpec

_NUMERIC_TYPES = {"integer", "number"}
_STRING_TYPES = {"string", "longtext"}


class SchemaValidationError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_entity_schema(raw: dict[str, Any]) -> EntitySchema:
    try:
        schema = EntitySchema.model_validate(raw)
    except PydanticValidationError as exc:
        raise SchemaValidationError(f"schema shape invalid: {exc.errors()[:3]}") from exc

    seen: set[str] = set()
    for f in schema.fields:
        if f.name in seen:
            raise SchemaValidationError(f"duplicate field name: {f.name}")
        seen.add(f.name)
        _check_field(f)
    if schema.primary_display and schema.primary_display not in seen:
        raise SchemaValidationError(f"primary_display '{schema.primary_display}' is not a field")
    return schema


def _check_field(f: FieldSpec) -> None:
    if f.type == "enum" and not f.options:
        raise SchemaValidationError(f"enum field '{f.name}' requires non-empty options")
    if f.type != "enum" and f.options is not None:
        raise SchemaValidationError(f"field '{f.name}' has options but is not an enum")
    if (f.min is not None or f.max is not None) and f.type not in _NUMERIC_TYPES:
        raise SchemaValidationError(f"min/max only valid on numeric fields ('{f.name}')")
    if (f.minLength is not None or f.maxLength is not None) and f.type not in _STRING_TYPES:
        raise SchemaValidationError(f"minLength/maxLength only valid on string fields ('{f.name}')")
    if f.pattern is not None:
        if f.type not in _STRING_TYPES:
            raise SchemaValidationError(f"pattern only valid on string fields ('{f.name}')")
        try:
            re.compile(f.pattern)
        except re.error as exc:
            raise SchemaValidationError(f"field '{f.name}' pattern invalid: {exc}") from exc
    if f.type == "file" and (
        f.min is not None or f.max is not None
        or f.minLength is not None or f.maxLength is not None
        or f.pattern is not None or f.options is not None
    ):
        raise SchemaValidationError(f"file field '{f.name}' cannot have value constraints")


def validate_ui_spec(raw: dict[str, Any]) -> UiSpec:
    try:
        return UiSpec.model_validate(raw)
    except PydanticValidationError as exc:
        raise SchemaValidationError(f"ui_spec invalid: {exc.errors()[:3]}") from exc


def coerce_row_data(schema: EntitySchema, data: dict[str, Any]) -> dict[str, Any]:
    """Validate + coerce a row payload against the entity schema.

    Returns a dict containing ONLY the schema-defined fields (drops extras).
    Raises SchemaValidationError on any violation.
    """
    out: dict[str, Any] = {}
    for f in schema.fields:
        present = f.name in data
        value = data.get(f.name)
        if not present or value is None:
            if f.required:
                raise SchemaValidationError(f"missing required field: {f.name}")
            continue
        out[f.name] = _coerce_value(f, value)
    return out


def _coerce_value(f: FieldSpec, value: Any) -> Any:  # noqa: ANN401
    if f.type == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"field '{f.name}' must be boolean")
        return value
    if f.type in _NUMERIC_TYPES:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemaValidationError(f"field '{f.name}' must be numeric")
        num = float(value)
        if f.type == "integer" and int(num) != num:
            raise SchemaValidationError(f"field '{f.name}' must be an integer")
        if f.min is not None and num < f.min:
            raise SchemaValidationError(f"field '{f.name}' below min {f.min}")
        if f.max is not None and num > f.max:
            raise SchemaValidationError(f"field '{f.name}' above max {f.max}")
        return int(num) if f.type == "integer" else num
    if f.type == "enum":
        if value not in (f.options or []):
            raise SchemaValidationError(f"field '{f.name}' not in options")
        return value
    if f.type == "date":
        if not isinstance(value, str):
            raise SchemaValidationError(f"field '{f.name}' date must be an ISO string")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise SchemaValidationError(f"field '{f.name}' invalid date: {exc}") from exc
        return value
    if f.type == "file":
        if not isinstance(value, dict):
            raise SchemaValidationError(f"field '{f.name}' file must be an object")
        fid, name, mime, size = (
            value.get("id"), value.get("name"), value.get("mime"), value.get("size"),
        )
        if not isinstance(fid, str) or not isinstance(name, str) or not isinstance(mime, str):
            raise SchemaValidationError(f"field '{f.name}' file needs string id/name/mime")
        if isinstance(size, bool) or not isinstance(size, int):
            raise SchemaValidationError(f"field '{f.name}' file needs integer size")
        return {"id": fid, "name": name, "mime": mime, "size": size}
    # string / longtext
    if not isinstance(value, str):
        raise SchemaValidationError(f"field '{f.name}' must be a string")
    if f.minLength is not None and len(value) < f.minLength:
        raise SchemaValidationError(f"field '{f.name}' shorter than {f.minLength}")
    if f.maxLength is not None and len(value) > f.maxLength:
        raise SchemaValidationError(f"field '{f.name}' longer than {f.maxLength}")
    if f.pattern is not None and not re.fullmatch(f.pattern, value):
        raise SchemaValidationError(f"field '{f.name}' fails pattern")
    return value
