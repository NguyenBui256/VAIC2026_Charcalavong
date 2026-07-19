"""Google Gemini adapter through the official OpenAI-compatible endpoint."""

from __future__ import annotations

from typing import Any

from app.core.adapters.openai_compatible import OpenAiCompatibleLlmAdapter
from app.core.settings import get_settings

__all__ = ["GoogleLlmAdapter"]


class GoogleLlmAdapter(OpenAiCompatibleLlmAdapter):
    """``LlmPort`` implementation for Google Gemini."""

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
            api_key=api_key or settings.google_api_key,
            base_url=base_url or settings.gemini_base_url,
            timeout=timeout if timeout is not None else settings.llm_timeout_seconds,
            provider_label="Google Gemini",
            key_env_hint="VAIC_GOOGLE_API_KEY or GEMINI_API_KEY",
        )
