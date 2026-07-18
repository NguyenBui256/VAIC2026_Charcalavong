"""Validation tests for the evidence-grounded audit judge contract."""

from __future__ import annotations

import json

import pytest

from app.core.ids import uuid7
from app.modules.audit.judge import _parse_output


def _result(criterion_id: str) -> str:
    return json.dumps(
        {
            "criteria": [
                {
                    "criterion_id": criterion_id,
                    "name": "Complete output",
                    "description": "Output is complete.",
                    "passed": True,
                    "confidence": 0.9,
                    "rationale": "The terminal output is present.",
                    "evidence": [{"event_sequence": 12}],
                }
            ],
            "summary": "Passed",
            "assessment": "The workflow met the selected criterion.",
            "insights": [],
            "issues": [],
            "strengths": ["Clear output"],
            "limitations": [],
        }
    )


def test_parse_output_accepts_json_fence_and_exact_criteria() -> None:
    criterion_id = uuid7()

    parsed = _parse_output(f"```json\n{_result(str(criterion_id))}\n```", {criterion_id})

    assert parsed.criteria[0].passed is True


def test_parse_output_rejects_missing_selected_criterion() -> None:
    with pytest.raises(ValueError, match="exactly one result"):
        _parse_output(_result(str(uuid7())), {uuid7()})
