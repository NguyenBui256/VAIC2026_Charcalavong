"""Hexagonal adapter implementations for the core ports.

Story 1.6:
- ``anthropic.AnthropicLlmAdapter`` -- concrete LlmPort backed by anthropic 0.114.0
- ``openai.OpenAiLlmAdapter``     -- placeholder, raises NotImplementedError
- ``google.GoogleLlmAdapter``      -- placeholder, raises NotImplementedError
- ``ollama.OllamaLlmAdapter``      -- placeholder, raises NotImplementedError

Domain code (``app/modules/``) MUST NOT import adapters directly; it imports
the ``LlmPort`` Protocol from ``app.core.ports.llm`` and receives an adapter
instance at runtime via Agent config ``{provider, model_name, parameters}``
(AD-7).
"""
