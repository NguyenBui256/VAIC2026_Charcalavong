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
from typing import TYPE_CHECKING, Any

from app.core.ports.audit import AuditPort, EventRecord, ExecutionContext, SpanEnd, SpanStart
from app.core.ports.llm import (
    CompletionResult,
    EmbeddingResult,
    Message,
    ModelRef,
    StreamChunk,
)
from app.modules.audit.context import get_execution_context
from app.modules.audit.cost import estimate_cost

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
        return os.environ.get(_ANTHROPIC_API_KEY_ENV) or os.environ.get(_FALLBACK_ENV)

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

        self._client_instance = _Anthropic(api_key=self._api_key, **self._extra_client_kwargs)
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
        audit_ctx = self._begin_audit(messages, model, parameters, "completion")
        start = time.perf_counter()
        try:
            resp = self._client.messages.create(**payload)
        except Exception as exc:
            self._fail_audit(audit_ctx, exc)
            raise
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

        self._complete_audit(
            audit_ctx,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            response_content=content,
            finish_reason=result.finish_reason,
            pricing=model.parameters,
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
        audit_ctx = self._begin_audit(messages, model, parameters, "stream")
        start = time.perf_counter()
        try:
            stream_cm = self._client.messages.stream(**payload)
        except Exception as exc:
            self._fail_audit(audit_ctx, exc)
            raise
        # Enter the context manager synchronously (SDK pattern); iterate
        # text_stream asynchronously.
        active = stream_cm.__enter__()
        chunks: list[str] = []
        first_token_ms: int | None = None
        try:
            async for delta in active.text_stream:  # type: ignore[attr-defined]
                if first_token_ms is None:
                    first_token_ms = int((time.perf_counter() - start) * 1000)
                    if self._audit_port is not None and audit_ctx is not None:
                        self._audit_port.emit_event(
                            EventRecord(
                                context=audit_ctx,
                                event_type="llm.first_token",
                                phase="progress",
                                status="running",
                                attributes={"ttft_ms": first_token_ms},
                            )
                        )
                chunks.append(delta)
                yield StreamChunk(delta=delta)
            final = active.get_final_message()  # type: ignore[attr-defined]
            latency_ms = int((time.perf_counter() - start) * 1000)
            input_tokens = getattr(final.usage, "input_tokens", 0)
            output_tokens = getattr(final.usage, "output_tokens", 0)
            self._complete_audit(
                audit_ctx,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                response_content="".join(chunks),
                finish_reason=getattr(final, "stop_reason", "") or "",
                ttft_ms=first_token_ms,
                pricing=model.parameters,
            )
        except Exception as exc:
            self._fail_audit(audit_ctx, exc)
            raise
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
        audit_ctx = self._begin_audit([], model, {"text_count": len(texts)}, "embedding")
        start = time.perf_counter()
        try:
            resp = self._client.embeddings.create(model=model.model_name, input=texts)
        except Exception as exc:
            self._fail_audit(audit_ctx, exc)
            raise
        latency_ms = int((time.perf_counter() - start) * 1000)

        vectors = list(getattr(resp, "embeddings", []) or [])
        result = EmbeddingResult(
            vectors=vectors,
            model=getattr(resp, "model", model.model_name),
            latency_ms=latency_ms,
        )

        self._complete_audit(
            audit_ctx,
            input_tokens=len(texts),
            output_tokens=0,
            latency_ms=latency_ms,
            response_content={"vector_count": len(vectors)},
            finish_reason="completed",
            pricing=model.parameters,
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

    def _begin_audit(
        self,
        messages: list[Message],
        model: ModelRef,
        parameters: dict[str, Any] | None,
        operation: str,
    ) -> ExecutionContext | None:
        if self._audit_port is None:
            return None
        parent = get_execution_context(required=True)
        assert parent is not None
        return self._audit_port.start_span(
            SpanStart(
                context=parent,
                node_type="llm",
                name=f"Anthropic {operation}",
                actor_type="agent" if parent.agent_id else "orchestrator",
                provider=_PROVIDER_NAME,
                model=model.model_name,
                input={
                    "messages": [m.model_dump() for m in messages],
                    "parameters": {**model.parameters, **(parameters or {})},
                },
                attributes={
                    "operation": operation,
                    "provider": _PROVIDER_NAME,
                    "model": model.model_name,
                },
            )
        )

    def _complete_audit(
        self,
        context: ExecutionContext | None,
        *,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        response_content: Any,
        finish_reason: str,
        ttft_ms: int | None = None,
        pricing: dict[str, Any] | None = None,
    ) -> None:
        if self._audit_port is None or context is None:
            return
        cost, snapshot = estimate_cost(
            input_tokens=input_tokens, output_tokens=output_tokens, pricing=pricing
        )
        self._audit_port.end_span(
            SpanEnd(
                context=context,
                output={"content": response_content, "finish_reason": finish_reason},
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost,
                ttft_ms=ttft_ms,
                attributes={
                    "latency_ms": latency_ms,
                    "finish_reason": finish_reason,
                    "provider": _PROVIDER_NAME,
                    "pricing_snapshot": snapshot,
                },
            )
        )

    def _fail_audit(self, context: ExecutionContext | None, exc: Exception) -> None:
        if self._audit_port is None or context is None:
            return
        self._audit_port.end_span(
            SpanEnd(
                context=context,
                status="failed",
                error_code=type(exc).__name__,
                error_message=str(exc),
                attributes={"provider": _PROVIDER_NAME},
            )
        )
