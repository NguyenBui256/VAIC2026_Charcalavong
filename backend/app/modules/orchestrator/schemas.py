"""Pydantic validators for the Orchestrator's LLM-decomposition output (Story 3.3).

`TaskSchemaModel` is the schema a single decomposed Task item must satisfy
before it is persisted as a `Task` row. Field names are exact -- the
decomposition prompt in `orchestrator/service.py` instructs the LLM to
reply with this exact shape.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

__all__ = ["TaskSchemaModel"]


class TaskSchemaModel(BaseModel):
    task: dict[str, Any]
    target_agent_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    expected: list[Any] = Field(default_factory=list)
    criteria: dict[str, Any] = Field(default_factory=dict)
