"""Per-app scoped session token — the sandboxed iframe's RUNTIME auth
boundary (Epic 4, story 4-6 / task 13).

A scoped token is a normal platform JWT (same shape the `AuthMiddleware` /
`MiniAppPrincipal` / RLS pipeline already understands: `user_id`,
`tenant_id`, `department_id`, `role`) PLUS two extra claims that narrow its
authority down to a single mini-app's row endpoints:

- `scope="miniapp:rows"` — marks the token as scoped (not a full platform
  session).
- `miniapp_id=str(app_id)` — the ONLY app whose `/apps/{app_id}/rows*`
  endpoints this token may touch.

CRITICAL: do NOT use the reserved JWT `aud` claim for `miniapp_id`.
`decode_access_token` (app.core.auth) calls `jose.jwt.decode(...)` without
passing `audience=`; python-jose then REJECTS any token that carries an
`aud` claim with "Invalid audience", since it validates `aud` even when the
caller doesn't ask for a specific audience. Using a custom `miniapp_id`
claim avoids that pitfall entirely and requires no change to
`decode_access_token`.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.auth import create_access_token

__all__ = ["SCOPE_MINIAPP_ROWS", "mint_scoped_token", "verify_scoped_token"]

SCOPE_MINIAPP_ROWS = "miniapp:rows"

# Short TTL: the host page mints one right before mounting the iframe; the
# iframe session doesn't need to outlive a normal browsing session.
_SCOPED_TOKEN_TTL_MINUTES = 30


def mint_scoped_token(app_id: uuid.UUID, principal: Any) -> str:
    """Mint a short-lived JWT authorizing ONLY `app_id`'s row endpoints.

    `principal` exposes `.user_id`, `.tenant_id`, `.department_id`, `.role`
    (i.e. `app.modules.mini_app.visibility.MiniAppPrincipal`).
    """
    claims = {
        "user_id": str(principal.user_id),
        "tenant_id": str(principal.tenant_id),
        "department_id": str(principal.department_id) if principal.department_id else None,
        "role": principal.role,
        "scope": SCOPE_MINIAPP_ROWS,
        "miniapp_id": str(app_id),
    }
    return create_access_token(claims, ttl_minutes=_SCOPED_TOKEN_TTL_MINUTES)


def verify_scoped_token(claims: dict[str, Any], app_id: uuid.UUID) -> bool:
    """True iff `claims` is a scoped token authorized for `app_id`."""
    return (
        claims.get("scope") == SCOPE_MINIAPP_ROWS
        and claims.get("miniapp_id") == str(app_id)
    )
