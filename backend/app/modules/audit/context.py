"""Execution context propagation for HTTP, arq, LLM, tools and RAG."""

from __future__ import annotations

from contextvars import ContextVar, Token

from app.core.ports.audit import ExecutionContext

execution_context: ContextVar[ExecutionContext | None] = ContextVar(
    "audit_execution_context", default=None
)


def get_execution_context(*, required: bool = True) -> ExecutionContext | None:
    value = execution_context.get()
    if required and value is None:
        raise RuntimeError("Audit execution context is required for this operation")
    return value


def set_execution_context(value: ExecutionContext) -> Token[ExecutionContext | None]:
    return execution_context.set(value)


def reset_execution_context(token: Token[ExecutionContext | None]) -> None:
    execution_context.reset(token)
