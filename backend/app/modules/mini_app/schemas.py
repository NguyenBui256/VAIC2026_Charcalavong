"""Pydantic DTOs for Mini-App entity schema + UI spec (Epic 4).

`EntitySchema`/`FieldSpec` are the *validated* shape a Mini-App's schema
takes once it passes `schema_validation.validate_entity_schema`. Kept
separate from the ORM `entity_schema` JSONB (stored as a plain dict).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FIELD_TYPES = ("string", "longtext", "integer", "number", "boolean", "date", "enum", "file")


class FieldSpec(BaseModel):
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{0,63}$")
    type: Literal["string", "longtext", "integer", "number", "boolean", "date", "enum", "file"]
    label: str | None = None
    required: bool = False
    min: float | None = None
    max: float | None = None
    minLength: int | None = None
    maxLength: int | None = None
    pattern: str | None = None
    options: list[str] | None = None


class EntitySchema(BaseModel):
    fields: list[FieldSpec] = Field(..., min_length=1)
    primary_display: str | None = None


class UiSpec(BaseModel):
    layout: Literal["table", "cards"] = "table"
    # Render mode of the generated app:
    #   full — create form + list table (default, backward-compatible)
    #   form — create form only (customer intake; no list)
    #   crm  — list table with edit/delete; the form shows only while editing
    mode: Literal["full", "form", "crm"] = "full"
    components: list[dict[str, Any]] = Field(default_factory=list)
    primary_actions: list[Literal["create", "edit", "delete"]] = Field(
        default_factory=lambda: ["create", "edit", "delete"]
    )
