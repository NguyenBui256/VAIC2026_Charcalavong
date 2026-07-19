"""Provider/model catalog -- single source of truth for the Model tab (Story
2.3 T1). The frontend renders whatever this reports; it never hard-codes a
provider or model list (AD-7, FR-5).

``configured`` = adapter implemented AND the runtime key/config is present in
``Settings``. This never makes a live network call -- availability is
inferred from settings only, so config-time UI never surfaces a false
run-time failure (AC1, AC3, anti-pattern #4).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.core.settings import Settings

__all__ = [
    "ModelCatalogEntry",
    "ProviderCatalogEntry",
    "KNOWN_PROVIDER_IDS",
    "get_provider_catalog",
    "get_context_window",
]


class ModelCatalogEntry(BaseModel):
    """A single selectable model under a provider."""

    name: str
    context_window: int


class ProviderCatalogEntry(BaseModel):
    """A single provider row for the Model tab's Provider dropdown."""

    id: str
    label: str
    configured: bool
    models: list[ModelCatalogEntry]


# Static registry: provider id -> {label, implemented, models}.
_STATIC_PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {
        "label": "Anthropic",
        "implemented": True,
        "models": [
            {"name": "claude-sonnet-4-5", "context_window": 200_000},
            {"name": "claude-opus-4-1", "context_window": 200_000},
        ],
    },
    "openai": {
        "label": "FPT AI Marketplace",
        "implemented": True,
        # Fallback for `get_context_window` (no live ``settings`` there);
        # `get_provider_catalog` overrides this with the deployment's
        # configured `VAIC_LLM_MODEL` at call time (AC1, AC3).
        "models": [{"name": "DeepSeek-V4-Flash", "context_window": 128_000}],
    },
    "google": {
        "label": "Google Gemini",
        "implemented": True,
        "models": [{"name": "gemini-3.5-flash", "context_window": 1_000_000}],
    },
    "ollama": {"label": "Ollama", "implemented": False, "models": []},
}

KNOWN_PROVIDER_IDS: frozenset[str] = frozenset(_STATIC_PROVIDERS.keys())


def _settings_key_for(provider_id: str, settings: Settings) -> str:
    """Return the runtime config value that gates ``configured`` for a provider."""
    return {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.llm_api_key or settings.openai_api_key,
        "google": settings.google_api_key,
        "ollama": settings.ollama_base_url,
    }.get(provider_id, "")


def get_provider_catalog(settings: Settings) -> list[ProviderCatalogEntry]:
    """Build the provider catalog from static metadata + runtime ``settings``."""
    entries: list[ProviderCatalogEntry] = []
    for provider_id, meta in _STATIC_PROVIDERS.items():
        implemented: bool = meta["implemented"]
        configured = implemented and bool(_settings_key_for(provider_id, settings))
        models = meta["models"]
        if provider_id == "openai":
            # `openai` advertises the deployment's configured model
            # (`VAIC_LLM_MODEL`) rather than a static list -- keeps the
            # catalog truthful to whatever model is actually wired at
            # runtime for the passed-in ``settings`` (AD-7).
            models = [{"name": settings.llm_model, "context_window": 128_000}]
        elif provider_id == "google":
            models = [{"name": settings.gemini_model, "context_window": 1_000_000}]
        entries.append(
            ProviderCatalogEntry(
                id=provider_id,
                label=meta["label"],
                configured=configured,
                models=[ModelCatalogEntry(**m) for m in models],
            )
        )
    return entries


def get_context_window(provider: str, model_name: str) -> int | None:
    """Look up the context-window estimate for ``provider``/``model_name``."""
    meta = _STATIC_PROVIDERS.get(provider)
    if meta is None:
        return None
    for m in meta["models"]:
        if m["name"] == model_name:
            return int(m["context_window"])
    return None
