"""Story 2.3 T3 — run-time model-invocation failure path (AC9, AC10).

Mirrors `test_llm_port_isolation.py::test_fake_agent_works_with_new_custom_adapter`
style: inject a fake `adapter_factory` + fake audit sink so this stays a pure
unit test (no DB, no real Anthropic call).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.core.ports.audit import AuditEntry
from app.core.ports.llm import CompletionResult, Message, ModelRef
from app.modules.agent_builder.models import Agent
from app.modules.agent_builder.service import invoke_agent_model


class FakeAuditSink:
    """Captures audit entries in-memory; never swallows (test double for AD-4)."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


def _make_agent(*, provider: str, model_name: str = "x") -> Agent:
    return Agent(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        name="Test Agent",
        system_prompt="You are helpful.",
        model={"provider": provider, "model_name": model_name, "parameters": {}},
    )


class _RaisingAdapter:
    def complete(
        self, messages: list[Message], model: ModelRef, parameters: dict[str, Any] | None = None
    ) -> CompletionResult:
        raise NotImplementedError("openai adapter is not yet implemented")


class _WorkingAdapter:
    def complete(
        self, messages: list[Message], model: ModelRef, parameters: dict[str, Any] | None = None
    ) -> CompletionResult:
        return CompletionResult(content="ok", model=model.model_name, latency_ms=1)


def test_unconfigured_provider_raises_and_emits_audit_entry() -> None:
    """AC9 — the failure surfaces at run time with a clear audit_trail message."""
    agent = _make_agent(provider="openai")
    audit = FakeAuditSink()

    with pytest.raises(NotImplementedError):
        invoke_agent_model(
            agent,
            "hello",
            audit=audit,
            adapter_factory=lambda _provider: _RaisingAdapter(),
        )

    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry.type == "model_invocation_failed"
    assert entry.agent_id == str(agent.id)
    assert "openai" in entry.output["message"]


def test_one_bad_adapter_does_not_crash_another_agent() -> None:
    """AC10 / FR-26 — provider isolation is per-Agent."""
    bad_agent = _make_agent(provider="openai")
    good_agent = _make_agent(provider="anthropic", model_name="claude-sonnet-4-5")

    bad_audit = FakeAuditSink()
    with pytest.raises(NotImplementedError):
        invoke_agent_model(
            bad_agent,
            "hello",
            audit=bad_audit,
            adapter_factory=lambda _provider: _RaisingAdapter(),
        )

    good_audit = FakeAuditSink()
    result = invoke_agent_model(
        good_agent,
        "hello",
        audit=good_audit,
        adapter_factory=lambda _provider: _WorkingAdapter(),
    )

    assert result.content == "ok"
    assert good_audit.entries == []  # no failure audit for the working Agent


def test_audit_failure_propagates_never_swallowed() -> None:
    """AD-4 — an audit.log() failure itself must propagate, not be hidden."""

    class BoomAuditSink:
        def log(self, entry: AuditEntry) -> None:
            raise RuntimeError("audit sink is down")

    agent = _make_agent(provider="openai")
    with pytest.raises(RuntimeError, match="audit sink is down"):
        invoke_agent_model(
            agent,
            "hello",
            audit=BoomAuditSink(),
            adapter_factory=lambda _provider: _RaisingAdapter(),
        )
