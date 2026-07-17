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
from sqlalchemy.orm import Session

from app.core.auth import AuthError, create_access_token, decode_access_token
from app.core.db import AdminSessionLocal, SessionLocal
from app.core.deps import assume_app_role, get_tenant_session
from app.core.tenant_context import set_tenant_session_var, tenant_context
from app.modules.tenant.models import User
from app.modules.tenant.service import (
    authenticate,
    issue_token,
    list_departments,
    list_tenant_users,
    user_profile,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Story 2.8 (carried item #2) — tenant-scoped Department listing, consumed by
# the Agent Builder Identity-tab dropdown and the Agent-list Department
# filter. Unprefixed (not under /auth) since it's a general tenant resource.
departments_router = APIRouter(tags=["departments"])


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
        assume_app_role(session)
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


@departments_router.get("/departments")
def list_departments_route(
    session: Session = Depends(get_tenant_session),  # noqa: B008 -- FastAPI idiom
) -> JSONResponse:
    """GET /departments — tenant-scoped Department list (Story 2.8 item #2).

    RLS on `departments` (Story 1.2) hides cross-tenant rows; no Python-side
    tenant filter here.
    """
    departments = list_departments(session)
    return JSONResponse(status_code=200, content=_ok(departments))
