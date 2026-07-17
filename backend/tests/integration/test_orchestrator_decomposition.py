"""Integration tests for `list_routable_agents` (Story 3.3/3.4 Task 3).

Task 4+ (LLM decomposition) is out of scope for this file's current tests --
`list_routable_agents` is the public selector consumed by that later work.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.agent_builder.service import list_routable_agents


def _as_app(session: Session, tenant_id) -> None:
    """Drop superuser privileges + set RLS context for the current txn."""
    session.execute(text("SET LOCAL ROLE vaic_app"))
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def test_list_routable_agents_shape(app_session: Session, seeded_agent: dict[str, Any]) -> None:
    _as_app(app_session, seeded_agent["tenant_agents_id"])
    rows = list_routable_agents(app_session)
    assert isinstance(rows, list)
    if rows:
        assert set(rows[0]) == {"id", "name", "department_id", "system_prompt"}
