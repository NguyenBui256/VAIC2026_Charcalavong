"""widen workflow_files.content_type 128 -> 255

Avoids a 500 on unusually long client-supplied Content-Type values
(mini-app file uploads store this verbatim). Widening is backward
compatible — no data change, existing rows fit.

Revision ID: c1d2e3f4a5b6
Revises: ad30agenttarget01
Create Date: 2026-07-19 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "ad30agenttarget01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "workflow_files",
        "content_type",
        existing_type=sa.String(128),
        type_=sa.String(255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "workflow_files",
        "content_type",
        existing_type=sa.String(255),
        type_=sa.String(128),
        existing_nullable=False,
    )
