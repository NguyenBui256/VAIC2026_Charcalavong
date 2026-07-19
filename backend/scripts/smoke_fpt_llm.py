"""Credential-safe live smoke for FPT AI Marketplace."""

from app.core.adapters.openai import OpenAiLlmAdapter
from app.core.ports.llm import Message, ModelRef
from app.core.settings import get_settings


def main() -> None:
    settings = get_settings()
    result = OpenAiLlmAdapter().complete(
        [Message(role="user", content="Reply with exactly: VAIC_FPT_OK")],
        ModelRef(provider="openai", model_name=settings.llm_model),
        {"temperature": 0, "max_tokens": 32},
    )
    print(
        {
            "provider": "openai",
            "model": result.model,
            "latency_ms": result.latency_ms,
            "usage": result.usage,
            "matched": "VAIC_FPT_OK" in result.content,
        }
    )


if __name__ == "__main__":
    main()
