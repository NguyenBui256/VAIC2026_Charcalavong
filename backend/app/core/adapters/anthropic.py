"""Anthropic LLM adapter -- wraps the ``anthropic`` 0.114.0 SDK (AD-7).

Per AD-7, this is the ONLY place in the codebase that imports the ``anthropic``
SDK. Domain code (Agent / Orchestrator / Mini-App) imports ``LlmPort`` only.

Design:
- The adapter is constructed with an optional ``api_key`` and an optional
  ``audit_port``. The ``anthropic.Anthropic`` client is NOT created at
  construction time when the key is missing -- this defers the failure to
  runtime (per FR-5 consequence: "missing provider surfaces at run time, not
  config time").
- Every ``complete`` / ``stream`` / ``embed`` call:
  1. Resolves the client lazily; if the API key is missing, raises a
     ``RuntimeError`` naming the missing env var.
  2. Translates the LlmPort ``Message`` / ``ModelRef`` shapes into the
     anthropic SDK's param shape.
  3. Measures wall-clock latency and builds a ``CompletionResult`` /
     ``StreamChunk`` / ``EmbeddingResult``.
  4. If ``audit_port`` is set, calls ``audit_port.log(entry)`` with the
     ``{provider, model, prompt_token_count, completion_token_count,
     latency_ms}`` payload (NFR-5).
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.core.ports.audit import AuditEntry, AuditPort
from app.core.ports.llm import (
    CompletionResult,
    EmbeddingResult,
    Message,
    ModelRef,
    StreamChunk,
)
from app.core.settings import get_settings

if TYPE_CHECKING:
    from anthropic import Anthropic

__all__ = ["AnthropicLlmAdapter"]


_PROVIDER_NAME = "anthropic"
_ANTHROPIC_API_KEY_ENV = "VAIC_ANTHROPIC_API_KEY"
_FALLBACK_ENV = "ANTHROPIC_API_KEY"


class AnthropicLlmAdapter:
    """Concrete ``LlmPort`` implementation backed by the Anthropic SDK.

    Construction never raises -- the API key may be unset and the failure is
    deferred to call time (FR-5 consequence).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        audit_port: AuditPort | None = None,
        extra_client_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._api_key = api_key or self._resolve_api_key()
        self._audit_port = audit_port
        self._extra_client_kwargs = extra_client_kwargs or {}
        # Lazily constructed; ``None`` means "not yet built / unbuildable".
        self._client_instance: Anthropic | None = None

    # -- Client resolution ---------------------------------------------------

    @staticmethod
    def _resolve_api_key() -> str | None:
        """Resolve the API key from env vars, preferring the VAIC-prefixed one."""
        return os.environ.get(_ANTHROPIC_API_KEY_ENV) or os.environ.get(
            _FALLBACK_ENV
        )

    @property
    def _client(self) -> Anthropic:
        """Lazily build the anthropic.Anthropic client.

        Raises ``RuntimeError`` at call time if the API key is missing (FR-5
        consequence: missing provider surfaces at run time).
        """
        if self._client_instance is not None:
            return self._client_instance
        if not self._api_key:
            raise RuntimeError(
                "Anthropic API key is not configured. Set the "
                f"{_ANTHROPIC_API_KEY_ENV} (or {_FALLBACK_ENV}) environment "
                "variable to a valid Anthropic API key."
            )
        # Import is here (not at module top) so that the SDK is only loaded
        # when an actual call is made -- keeps test import cheap and lets
        # the missing-key path raise our error rather than the SDK's.
        from anthropic import Anthropic as _Anthropic

        # Enforce the backend-configured hard timeout on the client so a hung
        # request aborts at `llm_timeout_seconds` and raises (retried upstream
        # by `execute_task_row`). An explicit `timeout` in `extra_client_kwargs`
        # (e.g. from a test) still wins.
        client_kwargs = dict(self._extra_client_kwargs)
        client_kwargs.setdefault("timeout", get_settings().llm_timeout_seconds)
        self._client_instance = _Anthropic(api_key=self._api_key, **client_kwargs)
        return self._client_instance

    # -- LlmPort.complete ----------------------------------------------------

    def complete(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> CompletionResult:
        """Single-shot completion via ``messages.create``."""
        payload = self._build_payload(messages, model, parameters)
        client = self._client  # may raise RuntimeError
        start = time.perf_counter()
        resp = client.messages.create(**payload)
        latency_ms = int((time.perf_counter() - start) * 1000)

        content = self._extract_text(resp)
        input_tokens = getattr(resp.usage, "input_tokens", 0)
        output_tokens = getattr(resp.usage, "output_tokens", 0)
        result = CompletionResult(
            content=content,
            model=getattr(resp, "model", model.model_name),
            latency_ms=latency_ms,
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
            finish_reason=getattr(resp, "stop_reason", "") or "",
        )

        self._audit(
            model=model.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            prompt_messages=messages,
            response_content=content,
        )
        return result

    # -- LlmPort.stream ------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming completion via ``messages.stream``.

        Yields ``StreamChunk`` objects as text arrives. Token usage and
        latency are audited at stream end (best-effort).
        """
        payload = self._build_payload(messages, model, parameters)
        client = self._client  # may raise RuntimeError
        start = time.perf_counter()
        stream_cm = client.messages.stream(**payload)
        # Enter the context manager synchronously (SDK pattern); iterate
        # text_stream asynchronously.
        active = stream_cm.__enter__()
        try:
            async for delta in active.text_stream:  # type: ignore[attr-defined]
                yield StreamChunk(delta=delta)
            try:
                final = active.get_final_message()  # type: ignore[attr-defined]
                latency_ms = int((time.perf_counter() - start) * 1000)
                input_tokens = getattr(final.usage, "input_tokens", 0)
                output_tokens = getattr(final.usage, "output_tokens", 0)
                self._audit(
                    model=model.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    prompt_messages=messages,
                    response_content="<stream>",
                )
            except Exception:
                # Best-effort audit; streaming may not expose final usage.
                pass
        finally:
            stream_cm.__exit__(None, None, None)

    # -- LlmPort.embed -------------------------------------------------------

    def embed(
        self,
        texts: list[str],
        model: ModelRef,
    ) -> EmbeddingResult:
        """Text embeddings via ``embeddings.create``.

        NOTE: Anthropic does not currently ship a first-class embeddings
        endpoint for Claude. This method is structured to call the SDK's
        ``embeddings.create`` if/when it becomes available; until then a
        provider-specific error will surface from the SDK at runtime.
        """
        client = self._client  # may raise RuntimeError
        start = time.perf_counter()
        resp = client.embeddings.create(
            model=model.model_name,
            input=texts,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        vectors = list(getattr(resp, "embeddings", []) or [])
        result = EmbeddingResult(
            vectors=vectors,
            model=getattr(resp, "model", model.model_name),
            latency_ms=latency_ms,
        )

        self._audit(
            model=model.model_name,
            input_tokens=len(texts),
            output_tokens=0,
            latency_ms=latency_ms,
            prompt_messages=[],
            response_content="<embeddings>",
        )
        return result

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _split_system(
        messages: list[Message],
    ) -> tuple[str | None, list[dict[str, str]]]:
        """Pull out system messages; Anthropic takes ``system`` as a kwarg."""
        system_parts: list[str] = []
        rest: list[dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                rest.append({"role": m.role, "content": m.content})
        system = "\n\n".join(system_parts) if system_parts else None
        return system, rest

    def _build_payload(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Translate LlmPort shapes into ``anthropic.messages.create`` kwargs."""
        merged: dict[str, Any] = dict(model.parameters or {})
        if parameters:
            merged.update(parameters)
        system, rest = self._split_system(messages)
        payload: dict[str, Any] = {
            "model": model.model_name,
            "messages": rest,
            "max_tokens": int(merged.pop("max_tokens", 1024)),
        }
        if system is not None:
            payload["system"] = system
        # Pass through known optional kwargs if present.
        for key in ("temperature", "top_p", "top_k", "stop_sequences"):
            if key in merged:
                payload[key] = merged.pop(key)
        # Any remaining unknown parameters are passed through verbatim. This
        # keeps the adapter forward-compatible as Anthropic adds new knobs.
        payload.update(merged)
        return payload

    @staticmethod
    def _extract_text(resp: Any) -> str:
        """Extract the concatenated text content from an Anthropic Message."""
        parts: list[str] = []
        for block in getattr(resp, "content", []) or []:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
        return "".join(parts)

    def _audit(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        prompt_messages: list[Message],
        response_content: str,
    ) -> None:
        """Emit a ``model_invocation`` AuditEntry (NFR-5). Best-effort."""
        if self._audit_port is None:
            return
        entry = AuditEntry(
            run_id="",
            step_id="",
            agent_id="",
            ts=datetime.now(UTC).isoformat(timespec="milliseconds"),
            type="model_invocation",
            input={
                "provider": _PROVIDER_NAME,
                "model": model,
                "messages": [m.model_dump() for m in prompt_messages],
            },
            output={
                "provider": _PROVIDER_NAME,
                "model": model,
                "prompt_token_count": input_tokens,
                "completion_token_count": output_tokens,
                "latency_ms": latency_ms,
                "content_preview": response_content[:200],
            },
            latency_ms=latency_ms,
            model=model,
        )
        # Per AD-4, an audit.log() failure MUST crash the calling Run.
        # We call it directly and let any exception propagate.
        self._audit_port.log(entry)
