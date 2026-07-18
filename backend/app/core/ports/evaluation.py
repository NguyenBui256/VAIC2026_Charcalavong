"""Contract for evaluator modules to attach results to an audit session."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.core.ports.audit import ExecutionContext


class EvaluationResult(BaseModel):
    context: ExecutionContext
    evaluator_name: str
    evaluator_version: str = ""
    evaluator_type: str = "rule"
    status: str = "completed"
    score: Decimal | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    criteria: list[dict[str, Any]] = Field(default_factory=list)
    evidence_span_ids: list[uuid.UUID] = Field(default_factory=list)
    requested_by_user_id: uuid.UUID | None = None
    provider: str = ""
    model: str = ""
    overall_pass: bool | None = None
    summary: str = ""
    assessment: str = ""
    insights: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    context_manifest: dict[str, Any] = Field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    estimated_cost_usd: Decimal = Decimal("0")


class EvaluationPort(Protocol):
    def record(self, result: EvaluationResult) -> uuid.UUID: ...
