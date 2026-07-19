"""Story 2.3 T1 — provider/model catalog (AC1, AC2, AC3).

- `configured` reflects `Settings` only (no live API call).
- Anthropic and OpenAI (FPT AI Marketplace / DeepSeek-V4-Flash) have real
  adapters; Google/Ollama remain unconfigured placeholders with no
  selectable models (AC2).
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


def test_google_is_configured_with_selectable_model_when_key_present() -> None:
    catalog = get_provider_catalog(_settings(google_api_key="sk-g-test"))
    google = _entry(catalog, "google")
    assert google.configured is True
    assert google.label == "Google Gemini"
    assert [model.name for model in google.models] == ["gemini-3.5-flash"]


def test_ollama_remains_an_unimplemented_placeholder() -> None:
    ollama = _entry(get_provider_catalog(_settings()), "ollama")
    assert ollama.configured is False
    assert ollama.models == []


def test_openai_configured_when_llm_api_key_present() -> None:
    """`openai` (FPT AI Marketplace / DeepSeek-V4-Flash) is a real adapter;
    `configured` follows `llm_api_key` (sourced from `ANTHROPIC_API_KEY`)."""
    catalog = get_provider_catalog(_settings(llm_api_key="sk-fpt-test"))
    openai_entry = _entry(catalog, "openai")
    assert openai_entry.configured is True
    assert openai_entry.label == "FPT AI Marketplace"
    assert any(m.name == "DeepSeek-V4-Flash" for m in openai_entry.models)


def test_openai_not_configured_when_no_key_present() -> None:
    catalog = get_provider_catalog(_settings())
    openai_entry = _entry(catalog, "openai")
    assert openai_entry.configured is False


def test_get_context_window_known_model() -> None:
    assert get_context_window("anthropic", "claude-sonnet-4-5") == 200_000


def test_get_context_window_unknown_model_returns_none() -> None:
    assert get_context_window("anthropic", "does-not-exist") is None
    assert get_context_window("openai", "gpt-4o") is None
