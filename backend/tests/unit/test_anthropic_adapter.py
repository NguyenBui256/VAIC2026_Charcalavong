"""Unit tests for the Anthropic LLM adapter (Story 1.6).

All tests mock the Anthropic SDK; no real API calls are made.

Covers ACs:
- AnthropicLlmAdapter exposes complete, stream, embed matching LlmPort
- Wraps the anthropic 0.114.0 SDK; domain code never imports the SDK (AD-7)
- Domain code calls llm.complete(...) and gets {content, usage, latency_ms}
- Adapter logs audit entry via audit_port.log() (NFR-5)
- Missing API key surfaces at RUNTIME (not config time)
- Missing provider in one Agent does not crash other Agents (FR-26)
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.adapters.anthropic import AnthropicLlmAdapter
from app.core.ports.audit import AuditEntry
from app.core.ports.llm import (
    CompletionResult,
    EmbeddingResult,
    LlmPort,
    Message,
    ModelRef,
    StreamChunk,
)

# -- helpers -----------------------------------------------------------------


class FakeAuditSink:
    """Captures AuditEntry instances for assertions."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


def _make_messages() -> list[Message]:
    return [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Hello"),
    ]


def _make_model() -> ModelRef:
    return ModelRef(
        provider="anthropic",
        model_name="claude-sonnet-4-5",
        parameters={"max_tokens": 256, "temperature": 0.7},
    )


def _fake_message_response(
    content: str = "Hi there",
    input_tokens: int = 10,
    output_tokens: int = 3,
) -> MagicMock:
    """Build a MagicMock that mimics anthropic.types.Message."""
    resp = MagicMock()
    text_block = MagicMock()
    text_block.text = content
    text_block.type = "text"
    resp.content = [text_block]
    resp.model = "claude-sonnet-4-5"
    resp.stop_reason = "end_turn"
    resp.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    return resp


def _fake_embedding_response(vectors: list[list[float]] | None = None) -> MagicMock:
    resp = MagicMock()
    resp.embeddings = vectors or [[0.1, 0.2, 0.3]]
    resp.model = "claude-embed-v1"
    return resp


def _bypass_client_resolution(adapter: AnthropicLlmAdapter) -> MagicMock:
    """Patch the lazy client instance so no real SDK is built.

    ``AnthropicLlmAdapter._client`` is a property that returns
    ``self._client_instance``; assigning a MagicMock to that attribute bypasses
    both SDK construction and the missing-API-key path.
    """
    mock_client = MagicMock()
    adapter._client_instance = mock_client  # noqa: SLF001
    return mock_client


# -- AC: Adapter implements LlmPort -----------------------------------------


def test_anthropic_adapter_satisfies_llm_port_protocol() -> None:
    """The adapter is structurally compatible with LlmPort (AD-7)."""
    adapter = AnthropicLlmAdapter(api_key="sk-test")
    assert isinstance(adapter, LlmPort)


def test_anthropic_adapter_has_complete_stream_embed() -> None:
    """Adapter exposes complete, stream, embed with correct callable signatures."""
    adapter = AnthropicLlmAdapter(api_key="sk-test")
    assert callable(adapter.complete)
    assert callable(adapter.stream)
    assert callable(adapter.embed)


# -- AC: complete() returns CompletionResult with content/usage/latency_ms ---


def test_complete_returns_completion_result() -> None:
    """complete() returns a CompletionResult with content, usage, latency_ms."""
    adapter = AnthropicLlmAdapter(api_key="sk-test")
    fake_resp = _fake_message_response(content="Hello back", input_tokens=12, output_tokens=5)

    mock_client = _bypass_client_resolution(adapter)
    mock_client.messages.create.return_value = fake_resp
    result = adapter.complete(_make_messages(), _make_model())

    assert isinstance(result, CompletionResult)
    assert result.content == "Hello back"
    assert result.usage["input_tokens"] == 12
    assert result.usage["output_tokens"] == 5
    assert isinstance(result.latency_ms, int)
    assert result.latency_ms >= 0
    assert result.model == "claude-sonnet-4-5"


def test_complete_merges_parameters_from_model_and_call() -> None:
    """Parameters from ModelRef.parameters and the parameters arg are merged."""
    adapter = AnthropicLlmAdapter(api_key="sk-test")
    fake_resp = _fake_message_response()

    mock_client = _bypass_client_resolution(adapter)
    mock_client.messages.create.return_value = fake_resp
    adapter.complete(
        _make_messages(),
        _make_model(),
        parameters={"temperature": 0.1},
    )

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-5"
    assert call_kwargs["max_tokens"] == 256
    # call-site parameters override model parameters
    assert call_kwargs["temperature"] == 0.1


def test_complete_passes_system_message_separately() -> None:
    """Anthropic API takes system as a top-level kwarg, not in messages."""
    adapter = AnthropicLlmAdapter(api_key="sk-test")
    fake_resp = _fake_message_response()

    mock_client = _bypass_client_resolution(adapter)
    mock_client.messages.create.return_value = fake_resp
    adapter.complete(_make_messages(), _make_model())

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "You are a helpful assistant."
    # The remaining user/assistant messages do NOT contain the system role
    roles = [m["role"] for m in call_kwargs["messages"]]
    assert "system" not in roles


# -- AC: stream() yields StreamChunk ---------------------------------------


@pytest.mark.asyncio
async def test_stream_yields_stream_chunks() -> None:
    """stream() is an async iterator yielding StreamChunk objects."""
    adapter = AnthropicLlmAdapter(api_key="sk-test")

    # The anthropic SDK's messages.stream() returns a context manager whose
    # __enter__ yields a MessageStream with text_stream async iterator.
    fake_stream = MagicMock()
    fake_text_stream = _fake_text_stream(["Hello", " world"])
    fake_stream.text_stream = fake_text_stream
    fake_stream.get_final_message.return_value = _fake_message_response(
        content="Hello world", input_tokens=8, output_tokens=2,
    )

    fake_cm = MagicMock()
    fake_cm.__enter__ = MagicMock(return_value=fake_stream)
    fake_cm.__exit__ = MagicMock(return_value=False)

    mock_client = _bypass_client_resolution(adapter)
    mock_client.messages.stream.return_value = fake_cm
    chunks: list[StreamChunk] = []
    async for chunk in adapter.stream(_make_messages(), _make_model()):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert all(isinstance(c, StreamChunk) for c in chunks)
    assert chunks[0].delta == "Hello"
    assert chunks[1].delta == " world"


def _fake_text_stream(deltas: list[str]) -> Any:
    """Build a fake async iterator over text deltas."""
    class _AsyncIter:
        def __init__(self, items: list[str]) -> None:
            self._items = list(items)
            self._idx = 0

        def __aiter__(self) -> _AsyncIter:
            return self

        async def __anext__(self) -> str:
            if self._idx >= len(self._items):
                raise StopAsyncIteration
            item = self._items[self._idx]
            self._idx += 1
            return item

    return _AsyncIter(deltas)


# -- AC: embed() returns EmbeddingResult ------------------------------------


def test_embed_returns_embedding_result() -> None:
    """embed() returns EmbeddingResult with vectors."""
    adapter = AnthropicLlmAdapter(api_key="sk-test")
    fake_resp = _fake_embedding_response(vectors=[[0.1, 0.2], [0.3, 0.4]])

    mock_client = _bypass_client_resolution(adapter)
    # The Anthropic SDK may not have a first-class embeddings endpoint for
    # Claude; we use a hypothetical method name and mock it.
    mock_client.embeddings.create.return_value = fake_resp
    result = adapter.embed(
        ["hello", "world"],
        ModelRef(provider="anthropic", model_name="claude-embed-v1"),
    )

    assert isinstance(result, EmbeddingResult)
    assert len(result.vectors) == 2
    assert result.vectors[0] == [0.1, 0.2]
    assert result.model == "claude-embed-v1"


# -- AC: audit logging via audit_port (NFR-5) -------------------------------


def test_complete_logs_audit_entry() -> None:
    """complete() logs an AuditEntry via audit_port.log() (NFR-5)."""
    audit = FakeAuditSink()
    adapter = AnthropicLlmAdapter(api_key="sk-test", audit_port=audit)
    fake_resp = _fake_message_response(input_tokens=11, output_tokens=4)

    mock_client = _bypass_client_resolution(adapter)
    mock_client.messages.create.return_value = fake_resp
    adapter.complete(_make_messages(), _make_model())

    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert isinstance(entry, AuditEntry)
    assert entry.type == "model_invocation"
    assert entry.model == "claude-sonnet-4-5"
    assert entry.output["prompt_token_count"] == 11
    assert entry.output["completion_token_count"] == 4
    assert "latency_ms" in entry.output
    assert entry.input["provider"] == "anthropic"


def test_audit_port_is_optional() -> None:
    """If audit_port is None (the default), complete() still works."""
    adapter = AnthropicLlmAdapter(api_key="sk-test")  # no audit_port
    assert adapter._audit_port is None  # noqa: SLF001
    fake_resp = _fake_message_response()

    mock_client = _bypass_client_resolution(adapter)
    mock_client.messages.create.return_value = fake_resp
    result = adapter.complete(_make_messages(), _make_model())

    assert result.content == "Hi there"


# -- AC: Missing API key surfaces at RUNTIME (not config time) ---------------


def test_missing_api_key_does_not_raise_at_construction() -> None:
    """Adapter construction without an API key MUST NOT raise (FR-5 consequence)."""
    # Construction with no key and no env var should be safe.
    adapter = AnthropicLlmAdapter(api_key=None)
    assert adapter is not None


def test_missing_api_key_raises_on_complete_call() -> None:
    """Calling complete() without an API key raises with a clear message."""
    adapter = AnthropicLlmAdapter(api_key=None)

    with pytest.raises(RuntimeError) as exc_info:
        adapter.complete(_make_messages(), _make_model())

    msg = str(exc_info.value)
    # Clear message that names the missing env var
    assert "ANTHROPIC_API_KEY" in msg or "anthropic_api_key" in msg.lower()


def test_missing_api_key_raises_on_embed_call() -> None:
    """embed() also raises at runtime without an API key."""
    adapter = AnthropicLlmAdapter(api_key=None)

    with pytest.raises(RuntimeError):
        adapter.embed(["hello"], ModelRef(provider="anthropic", model_name="x"))


@pytest.mark.asyncio
async def test_missing_api_key_raises_on_stream_call() -> None:
    """stream() also raises at runtime without an API key."""
    adapter = AnthropicLlmAdapter(api_key=None)

    with pytest.raises(RuntimeError):
        async for _ in adapter.stream(_make_messages(), _make_model()):
            pass


# -- AC: Missing provider in one Agent does not crash others (FR-26) --------


def test_one_bad_adapter_does_not_crash_another() -> None:
    """Two adapter instances: bad config raises on call; good one works fine."""
    bad = AnthropicLlmAdapter(api_key=None)
    good = AnthropicLlmAdapter(api_key="sk-good")
    fake_resp = _fake_message_response(content="ok")

    # bad one raises
    with pytest.raises(RuntimeError):
        bad.complete(_make_messages(), _make_model())

    # good one still works
    mock_client = _bypass_client_resolution(good)
    mock_client.messages.create.return_value = fake_resp
    result = good.complete(_make_messages(), _make_model())

    assert result.content == "ok"


# -- AC: Adapter wraps anthropic SDK; domain never imports it (AD-7) --------


def test_adapter_imports_anthropic_sdk_only_in_adapters_module() -> None:
    """AD-7: the anthropic SDK is imported only under core/adapters/.

    This test scans app/modules/ for `import anthropic` lines. Domain code
    MUST NOT import the SDK directly.
    """
    import pathlib

    repo_root = pathlib.Path(__file__).resolve()
    # Walk up to find "backend/"
    while repo_root.name != "backend":
        repo_root = repo_root.parent
        if repo_root == repo_root.parent:
            raise AssertionError("Could not find backend/ root")

    modules_dir = repo_root / "app" / "modules"
    if not modules_dir.exists():
        # modules/ doesn't exist yet in this story; nothing to scan.
        return

    violations: list[str] = []
    for path in modules_dir.rglob("*.py"):
        rel = str(path.relative_to(repo_root))
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("import anthropic") or "import anthropic" in stripped:
                violations.append(f"{rel}:{lineno}: {stripped}")
    assert not violations, (
        "AD-7 violation: domain code imports anthropic SDK directly:\n"
        + "\n".join(violations)
    )


# -- AC: Adapter accepts settings-injected config ---------------------------


def test_adapter_accepts_api_key_from_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """If no api_key arg, the adapter reads VAIC_ANTHROPIC_API_KEY from env."""
    monkeypatch.setenv("VAIC_ANTHROPIC_API_KEY", "sk-from-env")
    adapter = AnthropicLlmAdapter()  # no explicit api_key
    assert adapter._api_key == "sk-from-env"  # noqa: SLF001


def test_adapter_latency_is_measured() -> None:
    """latency_ms reflects actual wall-clock time of the call."""
    adapter = AnthropicLlmAdapter(api_key="sk-test")
    fake_resp = _fake_message_response()

    def _slow_create(*_args: Any, **_kwargs: Any) -> Any:
        time.sleep(0.05)
        return fake_resp

    mock_client = _bypass_client_resolution(adapter)
    mock_client.messages.create.side_effect = _slow_create
    result = adapter.complete(_make_messages(), _make_model())

    # At least 40ms (allowing for timer granularity)
    assert result.latency_ms >= 40


# -- AC: Placeholder adapters raise NotImplementedError ----------------------


def test_openai_adapter_raises_not_implemented() -> None:
    """OpenAiLlmAdapter is a placeholder; calls raise NotImplementedError."""
    from app.core.adapters.openai import OpenAiLlmAdapter

    adapter = OpenAiLlmAdapter()
    with pytest.raises(NotImplementedError):
        adapter.complete(_make_messages(), _make_model())


@pytest.mark.asyncio
async def test_openai_adapter_stream_raises_not_implemented() -> None:
    """OpenAi stream() also raises NotImplementedError."""
    from app.core.adapters.openai import OpenAiLlmAdapter

    adapter = OpenAiLlmAdapter()
    with pytest.raises(NotImplementedError):
        async for _ in adapter.stream(_make_messages(), _make_model()):
            pass


def test_openai_adapter_embed_raises_not_implemented() -> None:
    from app.core.adapters.openai import OpenAiLlmAdapter

    adapter = OpenAiLlmAdapter()
    with pytest.raises(NotImplementedError):
        adapter.embed(["hi"], ModelRef(provider="openai", model_name="x"))


def test_google_adapter_raises_not_implemented() -> None:
    """GoogleLlmAdapter is a placeholder; calls raise NotImplementedError."""
    from app.core.adapters.google import GoogleLlmAdapter

    adapter = GoogleLlmAdapter()
    with pytest.raises(NotImplementedError):
        adapter.complete(_make_messages(), _make_model())


def test_google_adapter_embed_raises_not_implemented() -> None:
    from app.core.adapters.google import GoogleLlmAdapter

    adapter = GoogleLlmAdapter()
    with pytest.raises(NotImplementedError):
        adapter.embed(["hi"], ModelRef(provider="google", model_name="x"))


def test_ollama_adapter_raises_not_implemented() -> None:
    """OllamaLlmAdapter is a placeholder; calls raise NotImplementedError."""
    from app.core.adapters.ollama import OllamaLlmAdapter

    adapter = OllamaLlmAdapter()
    with pytest.raises(NotImplementedError):
        adapter.complete(_make_messages(), _make_model())


def test_ollama_adapter_embed_raises_not_implemented() -> None:
    from app.core.adapters.ollama import OllamaLlmAdapter

    adapter = OllamaLlmAdapter()
    with pytest.raises(NotImplementedError):
        adapter.embed(["hi"], ModelRef(provider="ollama", model_name="x"))


def test_placeholder_adapter_construction_does_not_raise() -> None:
    """Placeholder adapters must be cheap to construct (FR-5 consequence)."""
    from app.core.adapters.google import GoogleLlmAdapter
    from app.core.adapters.ollama import OllamaLlmAdapter
    from app.core.adapters.openai import OpenAiLlmAdapter

    assert OpenAiLlmAdapter() is not None
    assert GoogleLlmAdapter() is not None
    assert OllamaLlmAdapter() is not None


def test_all_placeholder_adapters_satisfy_llm_port() -> None:
    """Placeholder adapters structurally satisfy LlmPort so the selector can
    instantiate them before the NotImplementedError surfaces."""
    from app.core.adapters.google import GoogleLlmAdapter
    from app.core.adapters.ollama import OllamaLlmAdapter
    from app.core.adapters.openai import OpenAiLlmAdapter

    assert isinstance(OpenAiLlmAdapter(), LlmPort)
    assert isinstance(GoogleLlmAdapter(), LlmPort)
    assert isinstance(OllamaLlmAdapter(), LlmPort)
