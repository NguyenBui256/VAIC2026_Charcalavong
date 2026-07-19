"""FPT AI Marketplace adapter through its OpenAI-compatible endpoint."""

from __future__ import annotations

from typing import Any

from app.core.adapters.openai_compatible import OpenAiCompatibleLlmAdapter
from app.core.settings import get_settings

__all__ = ["OpenAiLlmAdapter"]


class OpenAiLlmAdapter(OpenAiCompatibleLlmAdapter):
    """Backward-compatible ``openai`` provider id for FPT AI Marketplace."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        timeout: float | None = None,
        **_kwargs: Any,
    ) -> None:
        settings = get_settings()
        super().__init__(
            api_key=api_key or settings.llm_api_key or settings.openai_api_key,
            base_url=base_url or settings.llm_base_url,
            timeout=timeout if timeout is not None else settings.llm_timeout_seconds,
            provider_label="OpenAI-compatible",
            key_env_hint="VAIC_LLM_API_KEY",
        )
