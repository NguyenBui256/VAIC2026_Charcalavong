"""Credential-safe live smoke for Google Gemini."""

from app.core.adapters.google import GoogleLlmAdapter
from app.core.ports.llm import Message, ModelRef
from app.core.settings import get_settings


def main() -> None:
    settings = get_settings()
    result = GoogleLlmAdapter().complete(
        [Message(role="user", content="Reply with exactly: VAIC_GEMINI_OK")],
        ModelRef(provider="google", model_name=settings.gemini_model),
        {"temperature": 0, "max_tokens": 32},
    )
    print(
        {
            "provider": "google",
            "model": result.model,
            "latency_ms": result.latency_ms,
            "usage": result.usage,
            "matched": "VAIC_GEMINI_OK" in result.content,
        }
    )


if __name__ == "__main__":
    main()
