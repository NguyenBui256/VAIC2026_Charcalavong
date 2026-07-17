"""Unit tests for the error envelope, DomainError hierarchy, and TraceIdContext.

Covers ACs:
- DomainError subclasses carry correct .code, .http_status
- ErrorEnvelope shape matches {error: {code, message, details, trace_id}}
- TraceIdContext is a ContextVar storing a UUID v7
- TraceIdContext can be set/reset per-request
"""

from __future__ import annotations

import uuid
from contextvars import copy_context

import pytest

from app.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    ErrorEnvelope,
    MissingTenantContextError,
    NotFoundError,
    RateLimitError,
    TraceIdContext,
    UpstreamError,
    ValidationError,
)

# -- DomainError base --------------------------------------------------------

def test_domain_error_is_exception() -> None:
    """DomainError subclasses Exception."""
    assert issubclass(DomainError, Exception)


def test_domain_error_carries_code_message_details_http_status() -> None:
    """DomainError exposes .code, .message, .details, .http_status."""
    err = DomainError(
        code="custom_error",
        message="something broke",
        details={"field": "value"},
        http_status=418,
    )
    assert err.code == "custom_error"
    assert err.message == "something broke"
    assert err.details == {"field": "value"}
    assert err.http_status == 418


def test_domain_error_defaults_details_to_empty_dict() -> None:
    """When details is not provided, it defaults to an empty dict."""
    err = DomainError(code="x", message="y", http_status=400)
    assert err.details == {}


# -- HTTP status code mapping ------------------------------------------------

@pytest.mark.parametrize(
    ("exc_cls", "expected_status", "expected_code"),
    [
        (ValidationError, 400, "validation_error"),
        (NotFoundError, 404, "not_found"),
        (AuthenticationError, 401, "authentication_error"),
        (AuthorizationError, 403, "authorization_error"),
        (ConflictError, 409, "conflict"),
        (RateLimitError, 429, "rate_limit"),
        (UpstreamError, 502, "upstream_error"),
        (MissingTenantContextError, 500, "missing_tenant_context"),
    ],
)
def test_error_subclass_http_status_and_code(
    exc_cls: type[DomainError], expected_status: int, expected_code: str,
) -> None:
    """Each DomainError subclass maps to the correct HTTP status and code."""
    err = exc_cls("test message")
    assert err.http_status == expected_status
    assert err.code == expected_code


def test_validation_error_accepts_details() -> None:
    """ValidationError can carry field-level details."""
    err = ValidationError("bad input", details={"field": "name", "issue": "required"})
    assert err.details == {"field": "name", "issue": "required"}
    assert err.http_status == 400


# -- ErrorEnvelope shape -----------------------------------------------------

def test_error_envelope_has_correct_shape() -> None:
    """ErrorEnvelope serialises to {error: {code, message, details, trace_id}}."""
    trace_id = uuid.uuid4()
    envelope = ErrorEnvelope(
        code="test_code",
        message="test message",
        details={"k": "v"},
        trace_id=trace_id,
    )
    dumped = envelope.model_dump(mode="json")
    assert dumped["code"] == "test_code"
    assert dumped["message"] == "test message"
    assert dumped["details"] == {"k": "v"}
    assert dumped["trace_id"] == str(trace_id)


def test_error_envelope_trace_id_accepts_uuid() -> None:
    """ErrorEnvelope.trace_id accepts a UUID object."""
    trace_id = uuid.uuid4()
    envelope = ErrorEnvelope(
        code="x", message="y", details={}, trace_id=trace_id,
    )
    assert envelope.trace_id == trace_id


# -- TraceIdContext ----------------------------------------------------------

def test_trace_id_context_starts_none() -> None:
    """TraceIdContext defaults to None when no value has been set."""
    # Use a fresh context to avoid pollution from other tests.
    ctx = copy_context()

    def _get() -> uuid.UUID | None:
        # Reset any inherited value
        token = TraceIdContext.set(None)
        try:
            return TraceIdContext.get()
        finally:
            TraceIdContext.reset(token)

    value = ctx.run(_get)
    assert value is None


def test_trace_id_context_set_and_get() -> None:
    """TraceIdContext stores a UUID v7."""
    trace_id = uuid.uuid4()
    token = TraceIdContext.set(trace_id)
    try:
        assert TraceIdContext.get() == trace_id
    finally:
        TraceIdContext.reset(token)
        assert TraceIdContext.get() is None


def test_trace_id_context_is_isolated_per_context() -> None:
    """TraceIdContext does not leak across contexts."""
    trace_id = uuid.uuid4()
    token = TraceIdContext.set(trace_id)
    try:
        def child_get() -> uuid.UUID | None:
            return TraceIdContext.get()

        ctx = copy_context()
        # The child context inherits the value from the parent at fork time.
        assert ctx.run(child_get) == trace_id

        # But setting in the child does not affect the parent.
        other_id = uuid.uuid4()
        ctx.run(TraceIdContext.set, other_id)
        assert TraceIdContext.get() == trace_id  # parent unchanged
    finally:
        TraceIdContext.reset(token)
        assert TraceIdContext.get() is None


def test_new_trace_id_returns_uuid_v7() -> None:
    """new_trace_id() returns a UUID with version nibble 7."""
    from app.core.errors import new_trace_id

    tid = new_trace_id()
    assert isinstance(tid, uuid.UUID)
    assert tid.version == 7
