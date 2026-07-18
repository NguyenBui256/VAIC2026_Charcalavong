"""App-layer Visibility Tier enforcement (FR-16, story 4-3).

Tenant isolation is guaranteed at the DB by RLS; THIS module enforces the
per-app tier using the caller's principal (user_id/department_id already on
request.state). Raises AuthorizationError (403) — the auth middleware has
already produced 401 for anonymous callers on protected paths.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.errors import AuthorizationError
from app.modules.mini_app.models import MiniApp


@dataclass(frozen=True)
class MiniAppPrincipal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    department_id: uuid.UUID | None
    role: str


def can_access(app: MiniApp, principal: MiniAppPrincipal) -> bool:
    tier = app.visibility_tier
    if tier == "public":
        return True  # RLS already scoped to the same tenant
    if tier == "need_auth":
        return principal.department_id is not None and principal.department_id == app.department_id
    if tier == "private":
        return principal.user_id == app.owner_id or principal.user_id in (app.whitelist_user_ids or [])
    return False


def assert_can_access(app: MiniApp, principal: MiniAppPrincipal) -> None:
    if not can_access(app, principal):
        raise AuthorizationError(
            f"visibility tier '{app.visibility_tier}' denies access to mini-app {app.id}"
        )
