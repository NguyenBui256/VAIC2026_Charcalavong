"""Audit V2 contract, taxonomy and redaction unit tests."""

from __future__ import annotations

import pytest

from app.modules.audit.cost import estimate_cost
from app.modules.audit.redaction import redact_payload
from app.modules.audit.taxonomy import EVENT_TYPES, validate_event_type


def test_taxonomy_contains_all_load_bearing_domains() -> None:
    domains = {value.split(".", 1)[0] for value in EVENT_TYPES}
    assert {
        "session",
        "orchestrator",
        "task",
        "agent",
        "llm",
        "tool",
        "kb",
        "escalation",
        "mini_app",
        "app_event",
        "evaluation",
        "audit",
    } <= domains


def test_unknown_event_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown Audit V2 event"):
        validate_event_type("freeform.log")


def test_nested_secrets_and_banking_identifiers_are_redacted() -> None:
    result = redact_payload(
        {
            "headers": {"Authorization": "Bearer abc.def"},
            "customer": {"citizen_id": "012345678901", "note": "account 123456789012"},
        }
    )
    assert result.value["headers"]["Authorization"] == "[REDACTED]"
    assert result.value["customer"]["citizen_id"] == "[REDACTED]"
    assert "[REDACTED_NUMBER]" in result.value["customer"]["note"]
    assert result.count == 3


def test_cost_uses_immutable_rate_snapshot() -> None:
    cost, snapshot = estimate_cost(
        input_tokens=1_000_000,
        output_tokens=500_000,
        pricing={
            "input_cost_per_million": "3",
            "output_cost_per_million": "15",
            "pricing_version": "2026-07",
        },
    )
    assert str(cost) == "10.50000000"
    assert snapshot["pricing_version"] == "2026-07"
