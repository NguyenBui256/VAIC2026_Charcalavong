"""Story 2.3 T1 — provider/model catalog (AC1, AC2, AC3).

- `configured` reflects `Settings` only (no live API call).
- Anthropic is the only provider with real models; OpenAI/Google/Ollama are
  always unconfigured (placeholders) and yield no selectable models (AC2).
"""

from __future__ import annotations

from app.core.model_catalog import get_context_window, get_provider_catalog
from app.core.settings import Settings


def _settings(**overrides: str) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg,arg-type]


def _entry(catalog: list, provider_id: str):
    return next(p for p in catalog if p.id == provider_id)


def test_anthropic_configured_when_key_present() -> None:
    catalog = get_provider_catalog(_settings(anthropic_api_key="sk-ant-test"))
    anthropic = _entry(catalog, "anthropic")
    assert anthropic.configured is True
    assert anthropic.label == "Anthropic"
    assert len(anthropic.models) >= 1
    assert any(m.name == "claude-sonnet-4-5" for m in anthropic.models)


def test_anthropic_not_configured_when_key_absent() -> None:
    catalog = get_provider_catalog(_settings(anthropic_api_key=""))
    anthropic = _entry(catalog, "anthropic")
    assert anthropic.configured is False


def test_placeholder_providers_always_not_configured_with_no_models() -> None:
    """OpenAI/Google/Ollama render 'Not configured' even with a key set,
    because the adapter is not implemented (AC1). A disabled provider yields
    no selectable models (AC2)."""
    catalog = get_provider_catalog(
        _settings(openai_api_key="sk-oa-test", google_api_key="sk-g-test")
    )
    for provider_id in ("openai", "google", "ollama"):
        entry = _entry(catalog, provider_id)
        assert entry.configured is False
        assert entry.models == []


def test_get_context_window_known_model() -> None:
    assert get_context_window("anthropic", "claude-sonnet-4-5") == 200_000


def test_get_context_window_unknown_model_returns_none() -> None:
    assert get_context_window("anthropic", "does-not-exist") is None
    assert get_context_window("openai", "gpt-4o") is None
