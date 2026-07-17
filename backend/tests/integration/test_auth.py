"""ACs for Story 1.3 — Auth & Tenant Context Middleware.

Test plan (AC # → test name):
- AC1 valid login returns JWT with user_id, tenant_id, department_id, role claims
  → test_login_returns_jwt_with_required_claims
- AC2 JWT expires per configurable TTL
  → test_jwt_has_configurable_expiration
- AC3 protected endpoint without Authorization header → 401 envelope
  → test_protected_endpoint_without_auth_header_returns_401_envelope
- AC4 protected endpoint with expired/invalid JWT → 401 envelope
  → test_protected_endpoint_with_invalid_jwt_returns_401_envelope
  → test_protected_endpoint_with_expired_jwt_returns_401_envelope
- AC5 protected endpoint with valid JWT → tenant_context.get() populated
  → test_protected_endpoint_sees_tenant_context
- AC6 middleware sets RLS session var; protected handler sees only same-tenant rows
  → test_protected_endpoint_enforces_rls_isolation
- AC7 password hashing uses Argon2 (hash starts with $argon2)
  → test_password_hash_uses_argon2
- AC8 tenant_context is reset between requests (ContextVar default is None)
  → test_tenant_context_resets_between_requests
- AC9 deactivated user → 401 with code ACCOUNT_DEACTIVATED
  → test_deactivated_user_login_returns_401_account_deactivated
- AC10 GET /auth/me returns the user profile
  → test_auth_me_returns_user_profile
- AC11 two different JWTs never cross tenant boundaries
  → test_two_jwts_never_cross_tenant_boundaries
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from app.core.settings import get_settings
from app.core.tenant_context import tenant_context
from app.modules.tenant.service import hash_password

_settings = get_settings()


def _login(client: TestClient, email: str, password: str) -> dict[str, Any]:
    """POST /auth/login and return the parsed JSON. Asserts 200."""
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# AC1 — JWT contains user_id, tenant_id, department_id, role
# ---------------------------------------------------------------------------

def test_login_returns_jwt_with_required_claims(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """POST /auth/login with valid creds returns a JWT carrying the 4 claims."""
    body = _login(api_client, "alice@tenanta.example", "Password123!")
    token = body["data"]["access_token"]
    decoded = jwt.decode(
        token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm]
    )
    assert str(decoded["user_id"]) == str(auth_seed["user_a_id"])
    assert str(decoded["tenant_id"]) == str(auth_seed["tenant_a_id"])
    assert str(decoded["department_id"]) == str(auth_seed["dept_a_id"])
    assert decoded["role"] == "admin"


def test_login_wrong_password_returns_401(api_client: TestClient) -> None:
    """Wrong password → 401 UNAUTHENTICATED envelope."""
    r = api_client.post(
        "/auth/login",
        json={"email": "alice@tenanta.example", "password": "wrong"},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert "trace_id" in body["error"]


# ---------------------------------------------------------------------------
# AC2 — JWT expires per configurable TTL
# ---------------------------------------------------------------------------

def test_jwt_has_configurable_expiration(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """Decoded JWT `exp` minus `iat` equals the configured TTL."""
    body = _login(api_client, "alice@tenanta.example", "Password123!")
    decoded = jwt.decode(
        body["data"]["access_token"],
        _settings.jwt_secret,
        algorithms=[_settings.jwt_algorithm],
    )
    ttl_seconds = decoded["exp"] - decoded["iat"]
    expected_seconds = _settings.jwt_ttl_minutes * 60
    assert ttl_seconds == expected_seconds


# ---------------------------------------------------------------------------
# AC3 — Missing Authorization header → 401 envelope
# ---------------------------------------------------------------------------

def test_protected_endpoint_without_auth_header_returns_401_envelope(
    api_client: TestClient,
) -> None:
    """No Authorization header on /auth/me → 401 with the error envelope."""
    r = api_client.get("/auth/me")
    assert r.status_code == 401
    body = r.json()
    err = body["error"]
    assert err["code"] == "UNAUTHENTICATED"
    assert isinstance(err["message"], str) and err["message"]
    assert "details" in err
    assert "trace_id" in err
    uuid.UUID(err["trace_id"])  # must parse as UUID


# ---------------------------------------------------------------------------
# AC4 — Invalid / expired JWT → 401 envelope
# ---------------------------------------------------------------------------

def test_protected_endpoint_with_invalid_jwt_returns_401_envelope(
    api_client: TestClient,
) -> None:
    """Garbage token → 401 envelope."""
    r = api_client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_protected_endpoint_with_expired_jwt_returns_401_envelope(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """Hand-craft an already-expired JWT — middleware must reject it."""
    now = int(time.time())
    payload = {
        "sub": str(auth_seed["user_a_id"]),
        "user_id": str(auth_seed["user_a_id"]),
        "tenant_id": str(auth_seed["tenant_a_id"]),
        "department_id": str(auth_seed["dept_a_id"]),
        "role": "admin",
        "iat": now - 3600,
        "exp": now - 1800,  # expired 30 min ago
    }
    expired = jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)
    r = api_client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# AC5 — Valid JWT → tenant_context.get() populated in handler
# ---------------------------------------------------------------------------

def test_protected_endpoint_sees_tenant_context(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """GET /auth/me with a valid JWT — handler reads tenant_context.get()."""
    body = _login(api_client, "alice@tenanta.example", "Password123!")
    token = body["data"]["access_token"]
    r = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert str(data["id"]) == str(auth_seed["user_a_id"])
    assert str(data["tenant_id"]) == str(auth_seed["tenant_a_id"])
    assert str(data["department_id"]) == str(auth_seed["dept_a_id"])
    assert data["email"] == "alice@tenanta.example"
    assert data["role"] == "admin"


# ---------------------------------------------------------------------------
# AC6 — RLS session var is set; handler sees only same-tenant rows
# ---------------------------------------------------------------------------

def test_protected_endpoint_enforces_rls_isolation(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """Login as TenantA, call a handler that queries users via RLS — only
    TenantA rows visible."""
    body = _login(api_client, "alice@tenanta.example", "Password123!")
    token = body["data"]["access_token"]

    # /auth/users is protected and lists users under the current tenant's RLS
    # context (the middleware set app.tenant_id from the JWT).
    r = api_client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()["data"]}
    assert "alice@tenanta.example" in emails
    assert "bob@tenantb.example" not in emails


# ---------------------------------------------------------------------------
# AC7 — Password hashing uses Argon2
# ---------------------------------------------------------------------------

def test_password_hash_uses_argon2() -> None:
    """hash_password() returns a string starting with $argon2."""
    h = hash_password("anything")
    assert h.startswith("$argon2")


# ---------------------------------------------------------------------------
# AC8 — tenant_context is reset between requests
# ---------------------------------------------------------------------------

def test_tenant_context_resets_between_requests(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """After a request completes, the contextvar returns to its default (None)."""
    tenant_context.set(None)  # clear any stale state

    body = _login(api_client, "alice@tenanta.example", "Password123!")
    token = body["data"]["access_token"]
    r = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    # After the request, the contextvar must be back to its default.
    assert tenant_context.get() is None


# ---------------------------------------------------------------------------
# AC9 — Deactivated user → 401 with code ACCOUNT_DEACTIVATED
# ---------------------------------------------------------------------------

def test_deactivated_user_login_returns_401_account_deactivated(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """Set is_active=false on alice, attempt login — get ACCOUNT_DEACTIVATED."""
    with AdminSessionLocal() as s:
        s.execute(
            text("UPDATE users SET is_active = false WHERE email = 'alice@tenanta.example'")
        )
        s.commit()
    try:
        r = api_client.post(
            "/auth/login",
            json={"email": "alice@tenanta.example", "password": "Password123!"},
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"
    finally:
        with AdminSessionLocal() as s:
            s.execute(
                text("UPDATE users SET is_active = true WHERE email = 'alice@tenanta.example'")
            )
            s.commit()


# ---------------------------------------------------------------------------
# AC10 — GET /auth/me returns profile
# ---------------------------------------------------------------------------

def test_auth_me_returns_user_profile(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    body = _login(api_client, "bob@tenantb.example", "Password123!")
    token = body["data"]["access_token"]
    r = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data.keys()) >= {"id", "email", "tenant_id", "department_id", "role"}
    assert data["email"] == "bob@tenantb.example"


# ---------------------------------------------------------------------------
# AC11 — Two different JWTs never cross tenant boundaries
# ---------------------------------------------------------------------------

def test_two_jwts_never_cross_tenant_boundaries(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """Login as both alice (TenantA) and bob (TenantB). Each /auth/users
    call must only see their own tenant's users."""
    alice = _login(api_client, "alice@tenanta.example", "Password123!")
    bob = _login(api_client, "bob@tenantb.example", "Password123!")

    alice_users = api_client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {alice['data']['access_token']}"},
    ).json()["data"]
    bob_users = api_client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {bob['data']['access_token']}"},
    ).json()["data"]

    alice_emails = {u["email"] for u in alice_users}
    bob_emails = {u["email"] for u in bob_users}

    assert "alice@tenanta.example" in alice_emails
    assert "bob@tenantb.example" not in alice_emails
    assert "bob@tenantb.example" in bob_emails
    assert "alice@tenanta.example" not in bob_emails
