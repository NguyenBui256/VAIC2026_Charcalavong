"""Adapter registry -- maps ``ModelRef.provider`` -> concrete ``LlmPort`` (AD-7).

This is the ONLY place, besides the adapters themselves, allowed to import
concrete adapter classes. ``app/modules/`` code MUST depend on
``select_llm_adapter`` here, never on a concrete adapter directly (Story 2.3
Dev Notes anti-pattern #2). Provider selection happens at run time from the
Agent's stored ``{provider, model_name, parameters}`` data.
"""

from __future__ import annotations

from app.core.adapters.anthropic import AnthropicLlmAdapter
from app.core.adapters.google import GoogleLlmAdapter
from app.core.adapters.ollama import OllamaLlmAdapter
from app.core.adapters.openai import OpenAiLlmAdapter
from app.core.errors import ValidationError
from app.core.ports.llm import LlmPort

__all__ = ["ADAPTER_REGISTRY", "select_llm_adapter"]

# Maps provider id (as stored on the Agent record) -> adapter class. Adding a
# new provider means adding one entry here -- never a branch in domain code.
ADAPTER_REGISTRY: dict[str, type] = {
    "anthropic": AnthropicLlmAdapter,
    "openai": OpenAiLlmAdapter,
    "google": GoogleLlmAdapter,
    "ollama": OllamaLlmAdapter,
}


def select_llm_adapter(provider: str) -> LlmPort:
    """Construct the adapter for ``provider``. Construction never raises for
    a known-but-unconfigured provider (FR-5 consequence) -- only an unknown
    provider id raises here, at run time.
    """
    adapter_cls = ADAPTER_REGISTRY.get(provider)
    if adapter_cls is None:
        raise ValidationError(
            f"Unknown provider '{provider}'", code="unknown_provider"
        )
    return adapter_cls()  # type: ignore[no-any-return]
