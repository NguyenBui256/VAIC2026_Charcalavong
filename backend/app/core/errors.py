"""Error envelope, DomainError hierarchy, and FastAPI exception handlers.

Target shape (AR-14 / consistency-conventions.md):
    {error: {code: str, message: str, details: object, trace_id: uuid}}

Every API error -- domain or unhandled -- is translated into this envelope by
the FastAPI exception handlers registered via `register_error_handlers()`.
No stack trace is ever leaked to the client.

Per consistency-conventions.md: errors propagate via exceptions in domain code;
the API boundary translates to the envelope. Never swallow. Never return None
to mean error.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.ids import uuid7

logger = logging.getLogger(__name__)

__all__ = [
    "DomainError",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "RateLimitError",
    "UpstreamError",
    "MissingTenantContextError",
    "ErrorEnvelope",
    "TraceIdContext",
    "new_trace_id",
    "get_trace_id",
    "register_error_handlers",
]

# -- TraceId context ---------------------------------------------------------

TraceIdContext: ContextVar[uuid.UUID | None] = ContextVar(
    "trace_id_context", default=None,
)


def new_trace_id() -> uuid.UUID:
    """Generate a fresh UUID v7 for request tracing."""
    return uuid7()


def get_trace_id() -> uuid.UUID:
    """Return the current trace_id, generating one if none exists.

    The generated value is stored in the ContextVar so subsequent calls in the
    same request context reuse it.
    """
    tid = TraceIdContext.get()
    if tid is None:
        tid = new_trace_id()
        TraceIdContext.set(tid)
    return tid


# -- DomainError hierarchy ---------------------------------------------------


class DomainError(Exception):
    """Base class for all domain errors.

    Attributes:
        code: machine-readable error code (snake_case).
        message: human-readable error message.
        details: structured details (field errors, context).
        http_status: HTTP status code this error maps to.
    """

    code: str = "domain_error"
    http_status: int = 500

    def __init__(
        self,
        message: str = "",
        *,
        details: dict[str, Any] | None = None,
        code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        self.message = message or self.code
        self.details = details if details is not None else {}
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        super().__init__(self.message)


class ValidationError(DomainError):
    """Input validation failed."""

    code = "validation_error"
    http_status = 400


class NotFoundError(DomainError):
    """Resource not found."""

    code = "not_found"
    http_status = 404


class AuthenticationError(DomainError):
    """Authentication required or failed."""

    code = "authentication_error"
    http_status = 401


class AuthorizationError(DomainError):
    """Permission denied."""

    code = "authorization_error"
    http_status = 403


class ConflictError(DomainError):
    """Resource conflict (duplicate, stale version)."""

    code = "conflict"
    http_status = 409


class RateLimitError(DomainError):
    """Rate limit exceeded."""

    code = "rate_limit"
    http_status = 429


class UpstreamError(DomainError):
    """Upstream service failure."""

    code = "upstream_error"
    http_status = 502


class MissingTenantContextError(DomainError):
    """Tenant context required but not set."""

    code = "missing_tenant_context"
    http_status = 500


# -- Envelope models ---------------------------------------------------------


class ErrorEnvelope(BaseModel):
    """The inner ``error`` object: {code, message, details, trace_id}.

    The FastAPI handler wraps this in ``{"error": <ErrorEnvelope>}`` to produce
    the full response body ``{error: {code, message, details, trace_id}}``.
    """

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: uuid.UUID


# -- FastAPI exception handlers ----------------------------------------------


def _build_error_response(
    *,
    code: str,
    message: str,
    details: dict[str, Any],
    http_status: int,
) -> JSONResponse:
    """Build a JSONResponse with the error envelope and X-Trace-Id header.

    The response body is ``{error: {code, message, details, trace_id}}``.
    """
    trace_id = get_trace_id()
    envelope = ErrorEnvelope(
        code=code,
        message=message,
        details=details,
        trace_id=trace_id,
    )
    body = {"error": envelope.model_dump(mode="json")}
    return JSONResponse(
        status_code=http_status,
        content=body,
        headers={"X-Trace-Id": str(trace_id)},
    )


async def _domain_exception_handler(
    request: Request, exc: DomainError,
) -> JSONResponse:
    """Translate a DomainError into the error envelope."""
    _ = request  # unused but required by FastAPI signature
    return _build_error_response(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        http_status=exc.http_status,
    )


async def _unhandled_exception_handler(
    request: Request, exc: Exception,
) -> JSONResponse:
    """Translate any unhandled exception into a 500 error envelope.

    Never leaks the stack trace to the client. Logs the full exception server-side.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return _build_error_response(
        code="internal_error",
        message="An internal error occurred.",
        details={},
        http_status=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Wire all exception handlers onto a FastAPI app instance."""
    app.add_exception_handler(DomainError, _domain_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
