"""Shared adapter for OpenAI-compatible chat and embedding endpoints."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from app.core.ports.llm import (
    CompletionResult,
    EmbeddingResult,
    Message,
    ModelRef,
    StreamChunk,
)

if TYPE_CHECKING:
    from openai import OpenAI


class OpenAiCompatibleLlmAdapter:
    """Implement ``LlmPort`` using an OpenAI-compatible SDK endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float,
        provider_label: str,
        key_env_hint: str,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._provider_label = provider_label
        self._key_env_hint = key_env_hint
        self._client_instance: OpenAI | None = None

    @property
    def _client(self) -> OpenAI:
        if self._client_instance is not None:
            return self._client_instance
        if not self._api_key:
            raise RuntimeError(
                f"{self._provider_label} API key is not configured. Set "
                f"{self._key_env_hint} for endpoint ({self._base_url})."
            )
        from openai import OpenAI as _OpenAI

        self._client_instance = _OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        return self._client_instance

    def complete(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> CompletionResult:
        payload = self._build_payload(messages, model, parameters)
        start = time.perf_counter()
        response = self._client.chat.completions.create(**payload)
        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = response.choices[0]
        usage = response.usage
        return CompletionResult(
            content=choice.message.content or "",
            model=getattr(response, "model", model.model_name),
            latency_ms=latency_ms,
            usage={
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            },
            finish_reason=choice.finish_reason or "",
        )

    async def stream(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        payload = self._build_payload(messages, model, parameters)
        payload["stream"] = True
        for chunk in self._client.chat.completions.create(**payload):
            delta = chunk.choices[0].delta.content if chunk.choices else None
            finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
            if delta:
                yield StreamChunk(delta=delta, finish_reason=finish_reason or "")

    def embed(self, texts: list[str], model: ModelRef) -> EmbeddingResult:
        start = time.perf_counter()
        response = self._client.embeddings.create(model=model.model_name, input=texts)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return EmbeddingResult(
            vectors=[item.embedding for item in response.data],
            model=getattr(response, "model", model.model_name),
            latency_ms=latency_ms,
        )

    @staticmethod
    def _build_payload(
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = dict(model.parameters or {})
        if parameters:
            merged.update(parameters)
        return {
            "model": model.model_name,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            **merged,
        }
