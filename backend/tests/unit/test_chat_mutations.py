from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.ports.llm import CompletionResult, ModelRef
from app.modules.chat import mutations


def _completion(content: str) -> CompletionResult:
    return CompletionResult(
        content=content,
        model="gemini-3.5-flash",
        latency_ms=12,
        usage={"input_tokens": 5, "output_tokens": 8},
    )


@pytest.mark.asyncio
async def test_structured_graph_output_is_domain_validated(monkeypatch) -> None:
    async def fake_complete(messages, model):
        _ = messages, model
        return _completion(
            '{"action":"clarify","summary":"Cần Agent xử lý","expected_version":3,"graph":null}'
        )

    monkeypatch.setattr(mutations, "_complete_with_retry", fake_complete)
    proposal, completion = await mutations._structured_completion(
        system="system",
        prompt="prompt",
        model=ModelRef(provider="google", model_name="gemini-3.5-flash"),
        schema=mutations.GraphProposal,
    )
    assert proposal.action == "clarify"
    assert proposal.expected_version == 3
    assert completion.usage["output_tokens"] == 8


@pytest.mark.asyncio
async def test_structured_output_repairs_at_most_once(monkeypatch) -> None:
    outputs = iter(
        [
            _completion("not json"),
            _completion(
                '{"action":"reject","summary":"Không an toàn",'
                '"expected_updated_at":"2026-01-01T00:00:00+00:00"}'
            ),
        ]
    )

    async def fake_complete(messages, model):
        _ = messages, model
        return next(outputs)

    monkeypatch.setattr(mutations, "_complete_with_retry", fake_complete)
    proposal, _ = await mutations._structured_completion(
        system="system",
        prompt="prompt",
        model=ModelRef(provider="openai", model_name="DeepSeek-V4-Flash"),
        schema=mutations.MiniAppProposal,
    )
    assert proposal.action == "reject"


@pytest.mark.asyncio
async def test_structured_output_rejects_after_one_failed_repair(monkeypatch) -> None:
    async def fake_complete(messages, model):
        _ = messages, model
        return _completion("still invalid")

    monkeypatch.setattr(mutations, "_complete_with_retry", fake_complete)
    with pytest.raises(ValidationError, match="invalid structured output"):
        await mutations._structured_completion(
            system="system",
            prompt="prompt",
            model=ModelRef(provider="openai", model_name="DeepSeek-V4-Flash"),
            schema=mutations.GraphProposal,
        )
