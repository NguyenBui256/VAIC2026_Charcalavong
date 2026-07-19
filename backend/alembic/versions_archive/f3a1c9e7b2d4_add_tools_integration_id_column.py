"""add tools integration_id column

Revision ID: f3a1c9e7b2d4
Revises: dbbf3cb533e9
Create Date: 2026-07-18 02:55:00.000000

Story 2.8 (carried item #1) — nullable `integration_id` FK on `tools` so a
Tool can reference a registered `ApiIntegration` (wired into `ToolEditor` /
`IntegrationSelect` on the frontend, Story 2.7 AC3). RLS on `tools` (Story
2.6 migration 82478b8e9fea) already covers this table — no new policy
needed, just the column. `ADD COLUMN IF NOT EXISTS` keeps this idempotent.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a1c9e7b2d4"
down_revision: str | Sequence[str] | None = "dbbf3cb533e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "tools"
COLUMN = "integration_id"


def upgrade() -> None:
    """Add nullable `integration_id` FK -> api_integrations(id) ON DELETE SET NULL."""
    op.execute(
        f"""ALTER TABLE {TABLE}
            ADD COLUMN IF NOT EXISTS {COLUMN} UUID
            REFERENCES api_integrations(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_tools_integration_id ON {TABLE} ({COLUMN});"
    )


def downgrade() -> None:
    """Reverse: drop index + column."""
    op.execute(f"DROP INDEX IF EXISTS ix_tools_integration_id;")
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS {COLUMN};")
