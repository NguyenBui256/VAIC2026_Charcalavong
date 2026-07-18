"""OpenAI-compatible LLM adapter (AD-7).

Wraps the ``openai`` SDK's Chat Completions API against any OpenAI-compatible
endpoint -- defaults to the FPT AI Marketplace "OpenAI Wrapper"
(``VAIC_LLM_BASE_URL``, default ``https://mkp-api.fptcloud.com/v1``). Per
AD-7, this is the ONLY place in the codebase that imports the ``openai`` SDK.
Domain code (Agent / Orchestrator / Mini-App) imports ``LlmPort`` only.

Mirrors ``adapters/anthropic.py``'s construction contract:
- Construction never raises (FR-5): the API key/base_url may be unset and the
  failure is deferred to call time.
- Every ``complete``/``stream``/``embed`` call resolves the client lazily,
  raising ``RuntimeError`` at call time if the API key is missing.
"""

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
from app.core.settings import get_settings

if TYPE_CHECKING:
    from openai import OpenAI

__all__ = ["OpenAiLlmAdapter"]

_PROVIDER_NAME = "openai"


class OpenAiLlmAdapter:
    """``LlmPort`` implementation backed by any OpenAI Chat-Completions
    -compatible endpoint.

    Construction never raises -- the API key/base_url may be unset and the
    failure is deferred to call time (FR-5 consequence).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        timeout: float | None = None,
        **_kwargs: Any,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.llm_api_key or settings.openai_api_key
        self._base_url = base_url or settings.llm_base_url
        # Backend-configured hard timeout enforced on the client so a hung
        # request aborts at this mark and raises (retried upstream by
        # `execute_task_row`). An explicit `timeout=` arg still wins.
        self._timeout = timeout if timeout is not None else settings.llm_timeout_seconds
        # Lazily constructed; ``None`` means "not yet built / unbuildable".
        self._client_instance: OpenAI | None = None

    # -- Client resolution ---------------------------------------------------

    @property
    def _client(self) -> OpenAI:
        """Lazily build the ``openai.OpenAI`` client.

        Raises ``RuntimeError`` at call time if the API key is missing (FR-5
        consequence: missing provider surfaces at run time).
        """
        if self._client_instance is not None:
            return self._client_instance
        if not self._api_key:
            raise RuntimeError(
                "OpenAI-compatible API key is not configured. Set the "
                "ANTHROPIC_API_KEY (or VAIC_OPENAI_API_KEY) environment "
                "variable to a valid API key for the configured endpoint "
                f"({self._base_url})."
            )
        # Import is here (not at module top) so the SDK is only loaded when
        # an actual call is made -- keeps test import cheap.
        from openai import OpenAI as _OpenAI

        self._client_instance = _OpenAI(
            api_key=self._api_key, base_url=self._base_url, timeout=self._timeout
        )
        return self._client_instance

    # -- LlmPort.complete ----------------------------------------------------

    def complete(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> CompletionResult:
        """Single-shot completion via ``chat.completions.create``."""
        payload = self._build_payload(messages, model, parameters)
        client = self._client  # may raise RuntimeError
        start = time.perf_counter()
        resp = client.chat.completions.create(**payload)
        latency_ms = int((time.perf_counter() - start) * 1000)

        choice = resp.choices[0]
        content = choice.message.content or ""
        usage = resp.usage
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        return CompletionResult(
            content=content,
            model=getattr(resp, "model", model.model_name),
            latency_ms=latency_ms,
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
            finish_reason=choice.finish_reason or "",
        )

    # -- LlmPort.stream ------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming completion via ``chat.completions.create(stream=True)``."""
        payload = self._build_payload(messages, model, parameters)
        payload["stream"] = True
        client = self._client  # may raise RuntimeError
        for chunk in client.chat.completions.create(**payload):
            delta = chunk.choices[0].delta.content if chunk.choices else None
            finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
            if delta:
                yield StreamChunk(delta=delta, finish_reason=finish_reason or "")

    # -- LlmPort.embed -------------------------------------------------------

    def embed(
        self,
        texts: list[str],
        model: ModelRef,
    ) -> EmbeddingResult:
        """Text embeddings via ``embeddings.create``."""
        client = self._client  # may raise RuntimeError
        start = time.perf_counter()
        resp = client.embeddings.create(model=model.model_name, input=texts)
        latency_ms = int((time.perf_counter() - start) * 1000)

        vectors = [item.embedding for item in resp.data]
        return EmbeddingResult(
            vectors=vectors,
            model=getattr(resp, "model", model.model_name),
            latency_ms=latency_ms,
        )

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _build_payload(
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Translate LlmPort shapes into ``chat.completions.create`` kwargs."""
        merged: dict[str, Any] = dict(model.parameters or {})
        if parameters:
            merged.update(parameters)
        payload: dict[str, Any] = {
            "model": model.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        # Any remaining parameters (temperature, max_tokens, top_p, ...) pass
        # through verbatim -- keeps the adapter forward-compatible.
        payload.update(merged)
        return payload
