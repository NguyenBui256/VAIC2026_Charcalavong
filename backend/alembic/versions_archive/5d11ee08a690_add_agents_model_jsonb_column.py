"""add agents model jsonb column

Revision ID: 5d11ee08a690
Revises: 7e8b08b45590
Create Date: 2026-07-17 23:58:47.931999

Story 2.3 (AD-7, T2.1): adds `agents.model` -- the ModelRef
{provider, model_name, parameters} the Model tab writes. Stored as JSONB
data, never as code; defaults to `{}` (not yet configured).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d11ee08a690"
down_revision: str | Sequence[str] | None = "7e8b08b45590"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "agents"


def upgrade() -> None:
    """Add `model` JSONB column, defaulting to an empty object."""
    op.add_column(
        TABLE,
        sa.Column(
            "model",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    """Drop `model` column."""
    op.drop_column(TABLE, "model")
