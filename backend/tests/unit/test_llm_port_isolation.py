"""TDD test: adding a new provider requires NO changes to Agent / Orchestrator /
Mini-App code (AD-7, load-bearing AC for Story 1.6).

We construct fake domain modules that depend ONLY on LlmPort. Then we show that
plugging in a new custom adapter (CustomLlmAdapter) requires zero edits to that
domain code — the domain keeps calling llm.complete(), llm.stream(), llm.embed().
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.core.ports.llm import (
    CompletionResult,
    EmbeddingResult,
    LlmPort,
    Message,
    ModelRef,
    StreamChunk,
)

# -- A fake "domain module" that uses ONLY LlmPort ---------------------------
#
# This stands in for Agent / Orchestrator / Mini-App code. It must NOT import
# any concrete adapter (anthropic, openai, etc.) — only the port.


class FakeAgent:
    """A fake Agent that calls its injected LlmPort.

    This represents domain code in app/modules/. It must be agnostic to the
    concrete provider. Adding a new provider MUST NOT require changing this
    class.
    """

    def __init__(self, llm: LlmPort) -> None:
        self._llm = llm  # type: ignore[LlmPort is a Protocol]

    def answer(self, prompt: str, model: ModelRef) -> str:
        messages = [Message(role="user", content=prompt)]
        result = self._llm.complete(messages, model)
        return result.content

    async def stream_answer(self, prompt: str, model: ModelRef) -> list[str]:
        messages = [Message(role="user", content=prompt)]
        chunks: list[str] = []
        async for chunk in self._llm.stream(messages, model):
            chunks.append(chunk.delta)
        return chunks

    def embed(self, text: str, model: ModelRef) -> list[list[float]]:
        result = self._llm.embed([text], model)
        return result.vectors


# -- A fake "existing" adapter (AnthropicLlmAdapter stand-in) ----------------


class FakeAnthropicAdapter:
    """Stand-in for the real AnthropicLlmAdapter."""

    def complete(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> CompletionResult:
        return CompletionResult(
            content=f"[anthropic] {messages[-1].content}",
            model=model.model_name,
            latency_ms=10,
            usage={"input_tokens": 1, "output_tokens": 1},
        )

    async def stream(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(delta=f"[anthropic-stream] {messages[-1].content}")

    def embed(self, texts: list[str], model: ModelRef) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[[0.1] for _ in texts],
            model=model.model_name,
            latency_ms=5,
        )


# -- A NEW provider added AFTER the domain code is written --------------------


class CustomLlmAdapter:
    """A brand-new provider adapter added in a future sprint.

    If AD-7 holds, plugging this in requires NO edits to FakeAgent above.
    """

    def complete(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> CompletionResult:
        return CompletionResult(
            content=f"[custom] {messages[-1].content}",
            model=model.model_name,
            latency_ms=7,
            usage={"input_tokens": 2, "output_tokens": 2},
        )

    async def stream(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(delta=f"[custom-stream] {messages[-1].content}")

    def embed(self, texts: list[str], model: ModelRef) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[[0.9] for _ in texts],
            model=model.model_name,
            latency_ms=3,
        )


# -- Tests -------------------------------------------------------------------


def test_fake_agent_works_with_anthropic_adapter() -> None:
    """Domain code (FakeAgent) works with the original Anthropic adapter."""
    agent = FakeAgent(FakeAnthropicAdapter())
    model = ModelRef(provider="anthropic", model_name="claude-sonnet-4-5")
    result = agent.answer("hello", model)
    assert result == "[anthropic] hello"


def test_fake_agent_works_with_new_custom_adapter_unchanged() -> None:
    """LOAD-BEARING AD-7 TEST: same FakeAgent code works with a new provider.

    We reuse FakeAgent AS-IS (no source edits) and inject the new
    CustomLlmAdapter. If this passes, adding a provider required zero changes
    to the domain layer.
    """
    agent = FakeAgent(CustomLlmAdapter())
    model = ModelRef(provider="custom", model_name="custom-1")
    result = agent.answer("hello", model)
    assert result == "[custom] hello"


@pytest.mark.asyncio
async def test_fake_agent_streaming_works_with_new_adapter() -> None:
    """Streaming path also works with the new adapter unchanged."""
    agent = FakeAgent(CustomLlmAdapter())
    model = ModelRef(provider="custom", model_name="custom-1")
    chunks = await agent.stream_answer("hello", model)
    assert chunks == ["[custom-stream] hello"]


def test_fake_agent_embedding_works_with_new_adapter() -> None:
    """Embedding path also works with the new adapter unchanged."""
    agent = FakeAgent(CustomLlmAdapter())
    model = ModelRef(provider="custom", model_name="custom-embed")
    vectors = agent.embed("hello", model)
    assert vectors == [[0.9]]


def test_domain_code_does_not_import_concrete_adapters() -> None:
    """FakeAgent source does not reference any concrete adapter by name.

    This is a structural check: the source of FakeAgent must not mention
    "Anthropic", "OpenAi", "Google", or "Ollama".
    """
    src = inspect.getsource(FakeAgent)
    forbidden = ["Anthropic", "OpenAi", "Google", "Ollama", "anthropic", "openai"]
    for word in forbidden:
        assert word not in src, (
            f"FakeAgent source references '{word}' — domain code must be "
            "provider-agnostic (AD-7)."
        )


def test_llm_port_is_a_protocol() -> None:
    """Sanity: LlmPort is a typing.Protocol, enabling structural substitution."""
    import typing

    assert typing.get_origin(LlmPort) is None
    assert getattr(LlmPort, "_is_protocol", False) is True


def test_both_adapters_satisfy_llm_port() -> None:
    """Both the original and the new adapter are structurally LlmPort."""
    assert isinstance(FakeAnthropicAdapter(), LlmPort)
    assert isinstance(CustomLlmAdapter(), LlmPort)
