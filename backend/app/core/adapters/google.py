"""Placeholder Google (Gemini) LLM adapter (AD-7).

Raises ``NotImplementedError`` on every call. Real implementation lands in a
later sprint; this file exists so that the provider-selector code can route
to it without ``ImportError``.

Domain code MUST NOT import this module directly; it works against
``LlmPort`` and the adapter is selected at runtime from Agent config.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.core.ports.llm import (
    CompletionResult,
    EmbeddingResult,
    Message,
    ModelRef,
    StreamChunk,
)

__all__ = ["GoogleLlmAdapter"]

_PROVIDER_NAME = "google"


class GoogleLlmAdapter:
    """Placeholder adapter for Google Gemini. Not yet implemented."""

    def __init__(
        self,
        api_key: str | None = None,
        **_kwargs: Any,
    ) -> None:
        self._api_key = api_key

    def complete(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> CompletionResult:
        raise NotImplementedError(
            f"{_PROVIDER_NAME} adapter is not yet implemented (Story 1.6 only "
            "delivers the Anthropic adapter). Provider selection for this "
            f"Agent was '{_PROVIDER_NAME}'; either reconfigure the Agent to use "
            "'anthropic' or wait for the Google stream."
        )

    async def stream(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        raise NotImplementedError(
            f"{_PROVIDER_NAME} adapter is not yet implemented."
        )
        yield StreamChunk(delta="")  # pragma: no cover

    def embed(
        self,
        texts: list[str],
        model: ModelRef,
    ) -> EmbeddingResult:
        raise NotImplementedError(
            f"{_PROVIDER_NAME} adapter is not yet implemented."
        )
