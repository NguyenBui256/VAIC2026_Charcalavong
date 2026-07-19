"""Provider-neutral immutable cost snapshot calculation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def estimate_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    pricing: dict[str, Any] | None = None,
) -> tuple[Decimal, dict[str, str]]:
    """Return USD estimate plus the exact rates stored with the span.

    Pricing is supplied by provider/model configuration so historical audit
    data never changes when a vendor updates its public prices.
    """
    values = pricing or {}
    input_rate = Decimal(str(values.get("input_cost_per_million", 0)))
    output_rate = Decimal(str(values.get("output_cost_per_million", 0)))
    cached_rate = Decimal(str(values.get("cached_cost_per_million", 0)))
    million = Decimal(1_000_000)
    cost = (
        Decimal(input_tokens) * input_rate
        + Decimal(output_tokens) * output_rate
        + Decimal(cached_tokens) * cached_rate
    ) / million
    snapshot = {
        "currency": "USD",
        "input_cost_per_million": str(input_rate),
        "output_cost_per_million": str(output_rate),
        "cached_cost_per_million": str(cached_rate),
        "pricing_version": str(values.get("pricing_version", "unconfigured")),
    }
    return cost.quantize(Decimal("0.00000001")), snapshot
