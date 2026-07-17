"""Tenant module service layer.

Story 1.3 implements:
- `hash_password(plain)` — re-exported from app.core.auth
- `authenticate(session, email, password)` — verify creds, return User or raise AuthError
- `issue_token(user)` — build JWT claims and call create_access_token

Domain code never passes tenant_id as a function argument — it reads
`tenant_context.get()` after the middleware has populated it.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthError,
    create_access_token,
    verify_password,
)
from app.core.auth import (
    hash_password as _hash_password,
)
from app.modules.tenant.models import Department, User

__all__ = [
    "authenticate",
    "hash_password",
    "issue_token",
    "user_profile",
    "list_tenant_users",
    "list_departments",
    "department_profile",
]


def hash_password(plain: str) -> str:
    """Re-export passlib Argon2 hash for callers that only need hashing."""
    return _hash_password(plain)


def authenticate(session: Session, email: str, password: str) -> User:
    """Verify email+password. Returns the User on success; raises AuthError.

    Uses AdminSessionLocal-level access semantics — this function is called
    from the login route, which uses a session bound to the runtime engine
    WITHOUT setting app.tenant_id yet (the user is not authenticated).
    Therefore the SELECT must bypass RLS. The login route is responsible
    for using an admin session (BYPASSRLS) here.

    Raises:
        AuthError(code="UNAUTHENTICATED") — bad email or password.
        AuthError(code="ACCOUNT_DEACTIVATED") — is_active=false.
    """
    stmt = select(User).where(User.email == email)
    user = session.execute(stmt).scalar_one_or_none()
    if user is None or not user.password_hash:
        raise AuthError("Invalid email or password")
    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError(
            "Account has been deactivated",
            code="ACCOUNT_DEACTIVATED",
        )
    return user


def issue_token(user: User) -> str:
    """Build JWT claims for a User and return the encoded token."""
    claims: dict[str, Any] = {
        "sub": str(user.id),
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "department_id": str(user.department_id) if user.department_id else None,
        "role": user.role,
    }
    return create_access_token(claims)


def user_profile(user: User) -> dict[str, Any]:
    """Serialize a User to the response payload shape (no password_hash)."""
    return {
        "id": str(user.id),
        "email": user.email,
        "tenant_id": str(user.tenant_id),
        "department_id": str(user.department_id) if user.department_id else None,
        "role": user.role,
    }


def list_tenant_users(session: Session) -> list[dict[str, Any]]:
    """List users visible under the current RLS context.

    The caller's session MUST have app.tenant_id already set (middleware
    does this via get_session_with_tenant). RLS enforces isolation; no
    Python-side filter.
    """
    rows = session.execute(select(User)).scalars().all()
    return [user_profile(u) for u in rows]


def user_by_id(session: Session, user_id: uuid.UUID | str) -> User | None:
    """Fetch a single user by id — subject to RLS isolation."""
    stmt = select(User).where(User.id == uuid.UUID(str(user_id)))
    return session.execute(stmt).scalar_one_or_none()


def department_profile(department: Department) -> dict[str, Any]:
    """Serialize a Department to the response payload shape."""
    return {"id": str(department.id), "name": department.name}


def list_departments(session: Session) -> list[dict[str, Any]]:
    """List Departments visible under the current RLS context (Story 2.8).

    The caller's session MUST already have `app.tenant_id` set (via
    `get_tenant_session`) — RLS enforces isolation, no Python-side filter.
    Ordered by name for a stable dropdown/filter listing.
    """
    rows = session.execute(select(Department).order_by(Department.name)).scalars().all()
    return [department_profile(d) for d in rows]
