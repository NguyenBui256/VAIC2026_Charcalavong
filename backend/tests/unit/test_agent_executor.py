"""Unit tests for `TaskExecutionResult`/`AgentProviderPort.execute_task` (Story 3.3/3.4 Task 1)
and the concrete `AgentExecutor` (Task 2)."""

from __future__ import annotations

import uuid

import pytest

from app.core.ports.agent_provider import AgentProviderPort, TaskExecutionResult
from app.core.ports.llm import CompletionResult


def test_task_execution_result_defaults() -> None:
    r = TaskExecutionResult(output={"verdict": "pass"})
    assert r.success is True
    assert r.confidence == 1.0
    assert r.tool_calls == []
    assert r.kb_citations == []


def test_execute_task_in_protocol() -> None:
    assert hasattr(AgentProviderPort, "execute_task")


@pytest.mark.asyncio
async def test_execute_task_composes_model_and_kb(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.agent_builder import agent_executor as mod

    fake_agent = type(
        "A",
        (),
        {
            "id": uuid.uuid4(),
            "system_prompt": "You are Credit Analyst",
            "department_id": uuid.uuid4(),
            "model": {"provider": "anthropic", "model_name": "x"},
        },
    )()
    monkeypatch.setattr(mod, "get_agent", lambda s, aid: fake_agent)
    monkeypatch.setattr(
        mod,
        "invoke_agent_model",
        lambda agent, prompt, **k: CompletionResult(
            content='{"verdict":"pass","confidence":0.9}', model="x", latency_ms=5
        ),
    )

    class FakeKb:
        def __init__(self, s) -> None: ...

        async def retrieve(self, aid, q, *, tenant_id, department_id, top_k=5):
            from app.core.ports.agent_provider import RetrievalPassage

            return [
                RetrievalPassage(
                    passage="policy clause",
                    document_name="lending.pdf",
                    chunk_reference="c1",
                    score=0.8,
                )
            ]

    monkeypatch.setattr(mod, "AgentKbProvider", FakeKb)

    ex = mod.AgentExecutor(session=None)
    res = await ex.execute_task(
        fake_agent.id,
        {
            "task": {"summary": "screen loan"},
            "input": {"revenue": 1},
            "expected": [],
            "criteria": {},
        },
        tenant_id=uuid.uuid4(),
        department_id=fake_agent.department_id,
    )
    assert isinstance(res, TaskExecutionResult)
    assert res.success is True
    assert res.output.get("verdict") == "pass"
    assert res.confidence == 0.9
    assert "lending.pdf" in res.kb_citations[0]


@pytest.mark.asyncio
async def test_execute_task_reports_failure_on_required_tool_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M-4: a required tool (`criteria.must_use_tool`) that fails must flip
    `TaskExecutionResult.success` to False with a non-empty `error` -- the
    model's own JSON reply may still look fine, but a hard tool failure
    means the Task did not actually succeed."""
    from app.core.ports.tool import ToolOutput
    from app.modules.agent_builder import agent_executor as mod

    fake_agent = type(
        "A",
        (),
        {
            "id": uuid.uuid4(),
            "system_prompt": "You are Credit Analyst",
            "department_id": uuid.uuid4(),
            "model": {"provider": "anthropic", "model_name": "x"},
        },
    )()
    monkeypatch.setattr(mod, "get_agent", lambda s, aid: fake_agent)
    monkeypatch.setattr(
        mod,
        "invoke_agent_model",
        lambda agent, prompt, **k: CompletionResult(
            content='{"verdict":"pass","confidence":0.9}', model="x", latency_ms=5
        ),
    )

    class FakeKb:
        def __init__(self, s) -> None: ...

        async def retrieve(self, aid, q, *, tenant_id, department_id, top_k=5):
            return []

    monkeypatch.setattr(mod, "AgentKbProvider", FakeKb)
    monkeypatch.setattr(mod, "get_tool_by_name", lambda s, *, agent_id, display_name: object())
    monkeypatch.setattr(
        mod,
        "invoke_tool",
        lambda s, tool, args, *, tenant_id, department_id, audit=None: ToolOutput(
            tool_name="credit_check", output={}, success=False, error="sandbox timeout"
        ),
    )

    ex = mod.AgentExecutor(session=None)
    res = await ex.execute_task(
        fake_agent.id,
        {
            "task": {"summary": "screen loan"},
            "input": {"revenue": 1},
            "expected": [],
            "criteria": {"must_use_tool": "credit_check"},
        },
        tenant_id=uuid.uuid4(),
        department_id=fake_agent.department_id,
    )
    assert res.success is False
    assert res.error == "sandbox timeout"
