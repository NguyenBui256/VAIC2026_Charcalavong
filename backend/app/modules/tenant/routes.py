"""Tenant module HTTP routes — auth endpoints for Story 1.3.

- POST /auth/login   — public; issues a JWT on valid credentials
- POST /auth/refresh — public; re-issues a JWT from a valid (unexpired) one
- GET  /auth/me      — protected; returns the current User's profile
- GET  /auth/users   — protected; lists users under the current tenant (RLS)

Error envelope (AR-14): `{error: {code, message, details, trace_id}}`.
Success envelope: `{data: <payload>, error: null, meta: {}}`.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import AuthError, create_access_token, decode_access_token
from app.core.db import AdminSessionLocal, SessionLocal
from app.core.deps import get_tenant_session
from app.core.settings import get_settings
from app.core.tenant_context import set_tenant_session_var, tenant_context
from app.modules.tenant.models import User
from app.modules.tenant.service import (
    authenticate,
    issue_token,
    list_tenant_users,
    user_profile,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    token: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------

def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _err(
    code: str,
    message: str,
    trace_id: uuid.UUID,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "trace_id": str(trace_id),
        }
    }


def _trace(request: Request) -> uuid.UUID:
    return getattr(request.state, "trace_id", uuid.uuid4())


# ---------------------------------------------------------------------------
# Session dependencies
# ---------------------------------------------------------------------------

def _assume_app_role(session: Session) -> None:
    """Drop superuser privileges for this transaction.

    AD-2: the application role must not have BYPASSRLS. In production the
    runtime DSN connects via `vaic_app` directly (it's the only role the
    app holds). In tests, the DSN connects via the superuser `vaic`, so
    we explicitly `SET LOCAL ROLE vaic_app` to make RLS enforce.

    `SET LOCAL ROLE` is transaction-scoped and only takes effect if the
    current user is a member of the target role. The migration grants
    membership implicitly by creating `vaic_app` from a superuser
    context; `vaic` can SET ROLE to it.
    """
    app_role = get_settings().app_db_role
    if app_role:
        session.execute(text(f"SET LOCAL ROLE {app_role}"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login")
def login(body: LoginRequest, request: Request) -> JSONResponse:
    """Authenticate email+password, return JWT.

    Uses AdminSessionLocal (BYPASSRLS) because the user's tenant is not
    known until AFTER the lookup — RLS would block the SELECT.
    """
    trace_id = _trace(request)
    try:
        with AdminSessionLocal() as session:
            user = authenticate(session, body.email, body.password)
            token = issue_token(user)
    except AuthError as exc:
        return JSONResponse(
            status_code=exc.http_status,
            content=_err(exc.code, exc.message, trace_id, exc.details),
        )
    return JSONResponse(
        status_code=200,
        content=_ok(
            {
                "access_token": token,
                "token_type": "bearer",
                "user": user_profile(user),
            }
        ),
    )


@router.post("/refresh")
def refresh(body: RefreshRequest, request: Request) -> JSONResponse:
    """Exchange a valid (unexpired) JWT for a new one with fresh expiry."""
    trace_id = _trace(request)
    try:
        claims = decode_access_token(body.token)
    except AuthError as exc:
        return JSONResponse(
            status_code=exc.http_status,
            content=_err(exc.code, exc.message, trace_id, exc.details),
        )
    new_claims = {
        "sub": claims.get("sub"),
        "user_id": claims["user_id"],
        "tenant_id": claims["tenant_id"],
        "department_id": claims.get("department_id"),
        "role": claims.get("role"),
    }
    token = create_access_token(new_claims)
    return JSONResponse(
        status_code=200,
        content=_ok({"access_token": token, "token_type": "bearer"}),
    )


@router.get("/me")
def me(request: Request) -> JSONResponse:
    """Return the current user's profile.

    Uses the tenant-scoped session (RLS applies) to also prove the RLS
    session var is correctly set from the JWT's tenant_id claim.
    """
    trace_id = _trace(request)
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return JSONResponse(
            status_code=401,
            content=_err("UNAUTHENTICATED", "No authenticated user", trace_id),
        )

    tenant_id = tenant_context.get()
    if tenant_id is None:
        return JSONResponse(
            status_code=401,
            content=_err("UNAUTHENTICATED", "No tenant context", trace_id),
        )

    with SessionLocal() as session:
        _assume_app_role(session)
        set_tenant_session_var(session, tenant_id)
        from sqlalchemy import select

        user = session.execute(
            select(User).where(User.id == uuid.UUID(str(user_id)))
        ).scalar_one_or_none()

    if user is None:
        return JSONResponse(
            status_code=401,
            content=_err("UNAUTHENTICATED", "User not visible under tenant", trace_id),
        )
    return JSONResponse(status_code=200, content=_ok(user_profile(user)))


@router.get("/users")
def list_users(
    session: Session = Depends(get_tenant_session),  # noqa: B008 -- FastAPI idiom
) -> JSONResponse:
    """List users visible under the current RLS context (tenant-isolated)."""
    users = list_tenant_users(session)
    return JSONResponse(status_code=200, content=_ok(users))
