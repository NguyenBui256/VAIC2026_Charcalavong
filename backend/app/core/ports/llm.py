"""LlmPort -- hexagonal port for LLM providers (AD-7).

Agents and the orchestrator import ONLY this abstraction. Adapters
(``anthropic``, ``openai``, ``google``, ``ollama``) live in ``core/adapters/``
and are Stories 1.6+.

The Agent record stores ``{provider, model_name, parameters}`` as data -- never
as code. The platform never fixes the model; it always reads from Agent config.

Per AD-7:
- ``complete`` -- single-shot completion
- ``stream``  -- async generator yielding token chunks
- ``embed``   -- text embeddings for RAG indexing
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

__all__ = [
    "LlmPort",
    "Message",
    "ModelRef",
    "CompletionResult",
    "StreamChunk",
    "EmbeddingResult",
]


# -- Pydantic models ---------------------------------------------------------


class Message(BaseModel):
    """A single chat message."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str


class ModelRef(BaseModel):
    """Provider + model identifier -- stored per-Agent as data, not code."""

    provider: str  # "anthropic" | "openai" | "google" | "ollama"
    model_name: str  # e.g. "claude-sonnet-4-5", "gpt-4o"
    parameters: dict[str, Any] = Field(default_factory=dict)


class CompletionResult(BaseModel):
    """Result of a non-streaming LLM completion."""

    content: str
    model: str
    latency_ms: int
    usage: dict[str, int] = Field(default_factory=dict)
    finish_reason: str = ""


class StreamChunk(BaseModel):
    """A single chunk from a streaming completion."""

    delta: str
    finish_reason: str = ""


class EmbeddingResult(BaseModel):
    """Result of an embedding call."""

    vectors: list[list[float]]
    model: str
    latency_ms: int


# -- Protocol ----------------------------------------------------------------


@runtime_checkable
class LlmPort(Protocol):
    """Hexagonal port for LLM providers.

    Implementations: ``core/adapters/anthropic.py``, ``openai.py``, etc.
    The Agent config ``{provider, model_name, parameters}`` selects the
    adapter at run time.
    """

    def complete(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> CompletionResult:
        """Single-shot completion. Returns the full result."""
        ...

    async def stream(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming completion. Yields chunks as they arrive."""
        ...

    def embed(
        self,
        texts: list[str],
        model: ModelRef,
    ) -> EmbeddingResult:
        """Text embeddings for RAG indexing and retrieval."""
        ...
