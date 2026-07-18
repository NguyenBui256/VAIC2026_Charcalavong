"""OpenAI-compatible LLM adapter, including custom base URLs."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, OpenAI

from app.core.ports.llm import CompletionResult, EmbeddingResult, Message, ModelRef, StreamChunk

__all__ = ["OpenAiLlmAdapter"]


class OpenAiLlmAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 180.0,
        **_: Any,
    ) -> None:
        # Legacy fallback keeps the current deployment working while the generic
        # VAIC_LLM_API_KEY name is rolled out.
        key = (
            api_key
            or os.getenv("VAIC_LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
        )
        if not key:
            raise RuntimeError("OpenAI-compatible API key is not configured")
        self._sync = OpenAI(
            api_key=key,
            base_url=base_url or os.getenv("VAIC_LLM_BASE_URL") or None,
            timeout=timeout,
            max_retries=1,
        )
        self._async = AsyncOpenAI(
            api_key=key,
            base_url=base_url or os.getenv("VAIC_LLM_BASE_URL") or None,
            timeout=timeout,
            max_retries=1,
        )

    @staticmethod
    def _payload(
        messages: list[Message], model: ModelRef, parameters: dict[str, Any] | None
    ) -> dict[str, Any]:
        merged = {**model.parameters, **(parameters or {})}
        return {
            "model": model.model_name,
            "messages": [message.model_dump() for message in messages],
            **merged,
        }

    def complete(
        self, messages: list[Message], model: ModelRef, parameters: dict[str, Any] | None = None
    ) -> CompletionResult:
        started = time.perf_counter()
        response = self._sync.chat.completions.create(**self._payload(messages, model, parameters))
        choice = response.choices[0]
        usage = response.usage
        return CompletionResult(
            content=choice.message.content or "",
            model=response.model or model.model_name,
            latency_ms=int((time.perf_counter() - started) * 1000),
            usage={
                "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                "cached_tokens": int(
                    getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
                ),
            },
            finish_reason=choice.finish_reason or "",
        )

    async def stream(
        self, messages: list[Message], model: ModelRef, parameters: dict[str, Any] | None = None
    ) -> AsyncIterator[StreamChunk]:
        stream = await self._async.chat.completions.create(
            **self._payload(messages, model, parameters), stream=True
        )
        async for chunk in stream:
            choice = chunk.choices[0]
            yield StreamChunk(
                delta=choice.delta.content or "", finish_reason=choice.finish_reason or ""
            )

    def embed(self, texts: list[str], model: ModelRef) -> EmbeddingResult:
        started = time.perf_counter()
        response = self._sync.embeddings.create(model=model.model_name, input=texts)
        return EmbeddingResult(
            vectors=[item.embedding for item in response.data],
            model=response.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
