"""Auth core — JWT encode/decode, Argon2 hashing, ASGI middleware.

Story 1.3 implements:
- `hash_password(plain) -> str` / `verify_password(plain, hash) -> bool` via passlib[argon2]
- `create_access_token(claims, ttl_minutes)` — JWT.encode with HS256
- `decode_access_token(token)` — JWT.decode; raises AuthError on failure
- `AuthMiddleware` — Starlette ASGI middleware that authenticates each request
  by extracting the Bearer token, decoding the JWT, and populating
  `tenant_context.ContextVar` from the JWT claims. It also issues
  `SET LOCAL app.tenant_id` on the request's DB session via FastAPI dep.

Design:
- The middleware does NOT touch the DB on every request. The DB session is
  opened lazily by FastAPI's `get_session` dependency; the session var is
  set there. The middleware only decodes the JWT and sets the contextvar.
- The `get_session` dependency wraps the session to call
  `set_tenant_session_var()` based on the contextvar.
- Public paths (login, refresh, /health, /ready, /openapi.json) bypass auth.
- The error envelope matches AR-14: `{error: {code, message, details, trace_id}}`.

Story 1.4 will provide a shared error envelope module; until then a minimal
AuthError is defined here and the coordinator reconciles at merge.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, ClassVar

from jose import JWTError, jwt
from passlib.context import CryptContext
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.settings import get_settings
from app.core.tenant_context import reset_tenant_context, set_tenant_context

__all__ = [
    "AuthError",
    "AuthMiddleware",
    "PUBLIC_PATHS",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]

_pwd = CryptContext(schemes=["argon2"], deprecated="auto")


# ---------------------------------------------------------------------------
# Error — minimal until Story 1.4 lands the shared envelope.
# ---------------------------------------------------------------------------

class AuthError(Exception):
    """Authentication failure carrying a stable code + http_status."""

    code: ClassVar[str] = "UNAUTHENTICATED"
    http_status: int = 401

    def __init__(
        self,
        message: str = "Authentication required",
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}
        if http_status is not None:
            self.http_status = http_status


# ---------------------------------------------------------------------------
# Password hashing (Argon2)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Argon2 hash a plaintext password."""
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext against an Argon2 hash. Returns False on mismatch."""
    try:
        return _pwd.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(
    claims: dict[str, Any],
    ttl_minutes: int | None = None,
) -> str:
    """Encode a JWT. Adds `iat` and `exp`. Returns the token string."""
    s = get_settings()
    if ttl_minutes is None:
        ttl_minutes = s.jwt_ttl_minutes
    now = int(time.time())
    payload = {
        **claims,
        "iat": now,
        "exp": now + ttl_minutes * 60,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode + verify a JWT. Raises AuthError on any failure."""
    s = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token, s.jwt_secret, algorithms=[s.jwt_algorithm]
        )
    except JWTError as exc:
        raise AuthError("Invalid or expired token") from exc

    for required in ("user_id", "tenant_id"):
        if required not in payload:
            raise AuthError(f"JWT missing required claim: {required}")
    return payload


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# Paths that bypass authentication. Public endpoints must not depend on the
# tenant contextvar being set.
PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/ready",
    "/auth/login",
    "/auth/refresh",
    "/openapi.json",
    "/docs",
    "/redoc",
})


def _is_public(path: str) -> bool:
    """A path is public if it exactly matches a PUBLIC_PATHS entry or is docs.

    `/mini-app-runtime/...` (story 4-5) is the static bundle.js/index.html for
    a generated Mini-App — sandbox-inert markup/JS, not tenant data. It is
    deliberately served without auth here; the actual data plane
    (`/apps/{app_id}/rows*`) stays gated behind a normal or scoped platform
    JWT (story 4-6 `scoped_token.py`), so this exemption never exposes rows.
    """
    if path in PUBLIC_PATHS:
        return True
    # Swagger UI assets
    if path.startswith("/docs") or path.startswith("/redoc"):
        return True
    return path.startswith("/mini-app-runtime/")


def _envelope(
    code: str, message: str, trace_id: uuid.UUID, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the AR-14 error envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "trace_id": str(trace_id),
        }
    }


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate every non-public request via Bearer JWT.

    On success: sets `tenant_context.ContextVar` with `tenant_id`,
    `user_id`, `department_id`, `role` (the four JWT claims required by AC).
    The contextvar is reset to None at request teardown.

    On failure: returns 401 with the standard error envelope.
    """

    async def dispatch(
        self, request: Request, call_next: Any  # noqa: ANN401 -- ASGI contract
    ) -> Any:  # noqa: ANN401
        path = request.url.path
        trace_id = uuid.uuid4()
        request.state.trace_id = trace_id

        if _is_public(path):
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _unauthenticated(trace_id, "Missing or malformed Authorization header")
        token = auth_header[len("Bearer "):].strip()
        if not token:
            return _unauthenticated(trace_id, "Empty bearer token")

        try:
            claims = decode_access_token(token)
        except AuthError as exc:
            return _unauthenticated(trace_id, exc.message, exc.code, exc.details)

        # Populate contextvar — domain code reads tenant_context.get()
        try:
            set_tenant_context(claims["tenant_id"])
        except (ValueError, KeyError) as exc:
            return _unauthenticated(
                trace_id, "Invalid tenant_id in token", details={"reason": str(exc)}
            )

        # Stash the full principal on request.state for handlers/deps that
        # need user_id / department_id / role without re-decoding.
        request.state.user_id = claims.get("user_id")
        request.state.tenant_id = claims.get("tenant_id")
        request.state.department_id = claims.get("department_id")
        request.state.role = claims.get("role")
        # Additive — Mini-App per-app scoped session token (story 4-6).
        # `scope`/`miniapp_id` are only present on tokens minted by
        # `mini_app.scoped_token.mint_scoped_token`; absent on normal
        # platform JWTs, so this never affects existing auth behavior.
        request.state.scope = claims.get("scope")
        request.state.miniapp_id = claims.get("miniapp_id")

        try:
            response = await call_next(request)
        finally:
            # AC8 — always reset the contextvar at request teardown.
            reset_tenant_context()
        return response


def _unauthenticated(
    trace_id: uuid.UUID,
    message: str,
    code: str = "UNAUTHENTICATED",
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Return a 401 JSONResponse carrying the standard error envelope."""
    return JSONResponse(
        status_code=401,
        content=_envelope(code, message, trace_id, details),
    )
