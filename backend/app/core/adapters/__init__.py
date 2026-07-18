"""Hexagonal adapter implementations for the core ports.

Story 1.5:
- ``audit_postgres.PostgresAuditSink`` -- Audit V2 trace/event sink backed by PostgreSQL

Story 1.6:
- ``anthropic.AnthropicLlmAdapter`` -- concrete LlmPort backed by anthropic 0.114.0
- ``openai.OpenAiLlmAdapter``        -- placeholder, raises NotImplementedError
- ``google.GoogleLlmAdapter``         -- placeholder, raises NotImplementedError
- ``ollama.OllamaLlmAdapter``         -- placeholder, raises NotImplementedError

Future stories add: MCP client, tool, doc intake, sandbox adapters.

Domain code (``app/modules/``) MUST NOT import adapters directly; it imports
the relevant Port Protocol from ``app.core.ports.*`` and receives an adapter
instance at runtime via Agent/run config (AD-1, AD-7).
"""
