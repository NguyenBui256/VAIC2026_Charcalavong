"""Shared authorization guards for tenant-scoped pool management.

`builder` is the elevated tenant role permitted to CRUD the shared pool
(tools/integrations/KB). `member` may only be granted resources onto agents
they own — never manage the pool itself.
"""
from __future__ import annotations

from app.core.errors import AuthorizationError


def require_builder(principal) -> None:  # principal: Principal (avoid import cycle)
    """Raise FORBIDDEN unless the caller holds the `builder` role."""
    if getattr(principal, "role", None) != "builder":
        raise AuthorizationError("builder role required to manage the shared pool", code="FORBIDDEN")
