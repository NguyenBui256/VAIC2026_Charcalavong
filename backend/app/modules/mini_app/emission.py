"""LLM emission of a Mini-App {entity_schema, ui_spec} from a description (FR-12).

Reuses the env-driven model port (VAIC_LLM_PROVIDER / VAIC_LLM_MODEL) exactly
as orchestrator.service does. The model is instructed to return STRICT JSON;
output is parsed then run through the meta-schema validator (invalid -> reject).
"""

from __future__ import annotations

import json
from typing import Any

from app.core.adapters.registry import select_llm_adapter
from app.core.ports.llm import Message, ModelRef
from app.core.settings import get_settings
from app.modules.mini_app.schema_validation import (
    SchemaValidationError,
    validate_entity_schema,
    validate_ui_spec,
)
from app.modules.mini_app.schemas import EntitySchema, UiSpec

_ALLOWED_TYPES = "string, longtext, integer, number, boolean, date, enum"

_SYSTEM = (
    "You design data-entry mini-apps for a bank. Given a description and the "
    "expected output, return STRICT JSON only (no prose, no markdown fences) "
    'of the form: {"entity_schema": {"fields": [{"name","type","label","required",'
    '"min","max","minLength","maxLength","pattern","options"}], "primary_display"}, '
    '"ui_spec": {"layout":"table","primary_actions":["create","edit","delete"]}}. '
    f"Allowed field types: {_ALLOWED_TYPES}. Field names must match ^[a-z][a-z0-9_]*$. "
    "enum fields MUST include a non-empty options array. Include only fields the app needs."
)


def _model() -> ModelRef:
    s = get_settings()
    return ModelRef(provider=s.llm_provider, model_name=s.llm_model)


def emit_schema(
    description: str, expected_output: str, *, llm: Any | None = None
) -> tuple[EntitySchema, UiSpec, str]:
    """Ask the LLM for {entity_schema, ui_spec}, parse, and meta-validate.

    Returns (schema, ui_spec, prompt) on success. Raises SchemaValidationError
    if the model output isn't valid JSON or fails the meta-schema (unknown
    field type, duplicate name, enum without options, etc).
    """
    prompt = f"Description:\n{description}\n\nExpected output:\n{expected_output}"
    adapter = llm or select_llm_adapter(_model().provider)
    messages = [Message(role="system", content=_SYSTEM), Message(role="user", content=prompt)]
    completion = adapter.complete(messages, _model(), {"temperature": 0.2})
    text = completion.content
    try:
        parsed = json.loads(_strip_fences(text))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"model did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SchemaValidationError("model output must be a JSON object")
    schema = validate_entity_schema(parsed.get("entity_schema", {}))
    ui_spec = validate_ui_spec(parsed.get("ui_spec", {}))
    return schema, ui_spec, prompt


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.endswith("```"):
            t = t.rsplit("```", 1)[0]
    return t.strip()


_REVISE_SYSTEM = (
    "You revise a data-entry mini-app for a bank. You are given the CURRENT "
    "app as JSON (entity_schema + ui_spec) and a user instruction describing a "
    "change. Return STRICT JSON only (no prose, no markdown fences) of the form: "
    '{"entity_schema": {"fields": [{"name","type","label","required","min","max",'
    '"minLength","maxLength","pattern","options"}], "primary_display"}, '
    '"ui_spec": {"layout":"table|cards","primary_actions":["create","edit","delete"]}, '
    '"message": "one short sentence describing what changed"}. '
    "Return the FULL updated entity_schema and ui_spec (not a diff), preserving "
    "fields the instruction does not change. "
    f"Allowed field types: {_ALLOWED_TYPES}. Field names must match ^[a-z][a-z0-9_]*$. "
    "enum fields MUST include a non-empty options array. Keep the app minimal and coherent."
)


def revise_schema(
    current_schema: dict[str, Any],
    current_ui_spec: dict[str, Any],
    instruction: str,
    *,
    llm: Any | None = None,
) -> tuple[EntitySchema, UiSpec, str, str]:
    """Ask the LLM to revise {entity_schema, ui_spec} per an instruction.

    Returns (schema, ui_spec, message, prompt). Raises SchemaValidationError if
    the model output isn't valid JSON or fails the meta-schema.
    """
    prompt = (
        "CURRENT APP JSON:\n"
        + json.dumps({"entity_schema": current_schema, "ui_spec": current_ui_spec})
        + f"\n\nINSTRUCTION:\n{instruction}"
    )
    adapter = llm or select_llm_adapter(_model().provider)
    messages = [Message(role="system", content=_REVISE_SYSTEM), Message(role="user", content=prompt)]
    completion = adapter.complete(messages, _model(), {"temperature": 0.2})
    try:
        parsed = json.loads(_strip_fences(completion.content))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"model did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SchemaValidationError("model output must be a JSON object")
    schema = validate_entity_schema(parsed.get("entity_schema", {}))
    ui_spec = validate_ui_spec(parsed.get("ui_spec", {}))
    message = str(parsed.get("message") or "Updated the app.")
    return schema, ui_spec, message, prompt
