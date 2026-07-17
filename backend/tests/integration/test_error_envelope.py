"""Integration tests for the API error envelope via FastAPI TestClient.

Covers ACs:
- Raising DomainError in a route → response body is the envelope, status matches .http_status
- Unhandled Exception → envelope with code "internal_error", status 500, no stack trace
- Every error response includes trace_id (UUID v7)
- X-Trace-Id response header is set
- HTTP status mapping for each DomainError subclass
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    MissingTenantContextError,
    NotFoundError,
    RateLimitError,
    UpstreamError,
    ValidationError,
    register_error_handlers,
)

# -- Test app with error-raising routes --------------------------------------

def _make_test_app() -> FastAPI:
    """Build a minimal FastAPI app with error handlers and raising routes."""
    app = FastAPI()

    register_error_handlers(app)

    @app.get("/raise/validation")
    def _raise_validation() -> dict[str, str]:
        raise ValidationError("bad field", details={"field": "name"})

    @app.get("/raise/not-found")
    def _raise_not_found() -> dict[str, str]:
        raise NotFoundError("not here")

    @app.get("/raise/auth")
    def _raise_auth() -> dict[str, str]:
        raise AuthenticationError("no token")

    @app.get("/raise/forbidden")
    def _raise_forbidden() -> dict[str, str]:
        raise AuthorizationError("no access")

    @app.get("/raise/conflict")
    def _raise_conflict() -> dict[str, str]:
        raise ConflictError("duplicate")

    @app.get("/raise/rate-limit")
    def _raise_rate_limit() -> dict[str, str]:
        raise RateLimitError("slow down")

    @app.get("/raise/upstream")
    def _raise_upstream() -> dict[str, str]:
        raise UpstreamError("provider down")

    @app.get("/raise/missing-tenant")
    def _raise_missing_tenant() -> dict[str, str]:
        raise MissingTenantContextError()

    @app.get("/raise/generic")
    def _raise_generic() -> dict[str, str]:
        raise RuntimeError("unexpected boom")

    @app.get("/raise/custom-domain")
    def _raise_custom() -> dict[str, str]:
        raise DomainError(
            code="custom_code", message="custom message", http_status=422,
        )

    @app.get("/ok")
    def _ok() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture()
def client() -> TestClient:
    """TestClient wired to the error-enabled test app.

    Uses ``raise_server_exceptions=False`` so that the generic Exception
    handler can return a 500 response instead of re-raising in the test process.
    """
    return TestClient(_make_test_app(), raise_server_exceptions=False)


# -- Helper ------------------------------------------------------------------

def _assert_envelope_shape(body: dict) -> dict:
    """Assert the response body matches {error: {code, message, details, trace_id}}."""
    assert "error" in body
    err = body["error"]
    assert "code" in err
    assert "message" in err
    assert "details" in err
    assert "trace_id" in err
    return err


def _assert_trace_id_is_uuid_v7(err: dict) -> uuid.UUID:
    """Assert trace_id is present and is a UUID v7."""
    tid_str = err["trace_id"]
    tid = uuid.UUID(str(tid_str))
    assert tid.version == 7, f"trace_id must be UUID v7, got version {tid.version}"
    return tid


# -- Status code mapping tests -----------------------------------------------

@pytest.mark.parametrize(
    ("path", "expected_status", "expected_code"),
    [
        ("/raise/validation", 400, "validation_error"),
        ("/raise/not-found", 404, "not_found"),
        ("/raise/auth", 401, "authentication_error"),
        ("/raise/forbidden", 403, "authorization_error"),
        ("/raise/conflict", 409, "conflict"),
        ("/raise/rate-limit", 429, "rate_limit"),
        ("/raise/upstream", 502, "upstream_error"),
        ("/raise/missing-tenant", 500, "missing_tenant_context"),
    ],
)
def test_domain_error_returns_correct_status_and_envelope(
    client: TestClient, path: str, expected_status: int, expected_code: str,
) -> None:
    """Each DomainError subclass produces the correct HTTP status and envelope code."""
    response = client.get(path)

    assert response.status_code == expected_status
    body = response.json()
    err = _assert_envelope_shape(body)
    assert err["code"] == expected_code
    _assert_trace_id_is_uuid_v7(err)


def test_custom_domain_error_returns_422(client: TestClient) -> None:
    """A DomainError with a custom http_status surfaces correctly."""
    response = client.get("/raise/custom-domain")

    assert response.status_code == 422
    body = response.json()
    err = _assert_envelope_shape(body)
    assert err["code"] == "custom_code"
    assert err["message"] == "custom message"


# -- Unhandled exception → 500 internal_error --------------------------------

def test_unhandled_exception_returns_500_internal_error(client: TestClient) -> None:
    """An unhandled Exception → 500 with code 'internal_error', no stack trace."""
    response = client.get("/raise/generic")

    assert response.status_code == 500
    body = response.json()
    err = _assert_envelope_shape(body)
    assert err["code"] == "internal_error"
    assert "boom" not in err["message"].lower() or "internal" in err["message"].lower()
    # No stack trace should be leaked
    body_str = str(body)
    assert "Traceback" not in body_str
    assert "RuntimeError" not in body_str


# -- trace_id is UUID v7 on every error --------------------------------------

def test_trace_id_present_on_every_error(client: TestClient) -> None:
    """Every error response includes a trace_id that is a valid UUID v7."""
    for path in [
        "/raise/validation",
        "/raise/not-found",
        "/raise/generic",
    ]:
        response = client.get(path)
        body = response.json()
        err = _assert_envelope_shape(body)
        _assert_trace_id_is_uuid_v7(err)


# -- X-Trace-Id header -------------------------------------------------------

def test_trace_id_in_response_header(client: TestClient) -> None:
    """The trace_id is also set as the X-Trace-Id response header."""
    response = client.get("/raise/validation")

    assert response.status_code == 400
    assert "x-trace-id" in response.headers
    header_tid = response.headers["x-trace-id"]
    body_tid = response.json()["error"]["trace_id"]
    assert header_tid == body_tid
    tid = uuid.UUID(header_tid)
    assert tid.version == 7


# -- Success path is unaffected ----------------------------------------------

def test_success_route_still_works(client: TestClient) -> None:
    """Non-error routes still return their normal response."""
    response = client.get("/ok")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# -- ValidationError carries details -----------------------------------------

def test_validation_error_carries_details(client: TestClient) -> None:
    """ValidationError details are surfaced in the envelope."""
    response = client.get("/raise/validation")

    assert response.status_code == 400
    body = response.json()
    err = _assert_envelope_shape(body)
    assert err["details"] == {"field": "name"}
