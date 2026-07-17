"""add users password hash is_active updated_at

Revision ID: ec784b72f20c
Revises: a466fb9b53c6
Create Date: 2026-07-17 20:09:53.180238

Story 1.3: adds auth-related columns to `users`:
- `password_hash`  — Argon2 hash from passlib[argon2]
- `is_active`      — boolean flag; deactivated users cannot log in
- `updated_at`     — track modification time (updated via trigger)

The columns are nullable on addition so existing rows (if any) survive.
Application code enforces `password_hash IS NOT NULL` for new writes.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ec784b72f20c"
down_revision: str | Sequence[str] | None = "a466fb9b53c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add password_hash, is_active, updated_at columns to users."""
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Trigger: keep updated_at in sync on UPDATE.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION users_set_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS users_updated_at_trigger ON users;
        CREATE TRIGGER users_updated_at_trigger
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION users_set_updated_at();
        """
    )


def downgrade() -> None:
    """Reverse: drop trigger, function, columns."""
    op.execute("DROP TRIGGER IF EXISTS users_updated_at_trigger ON users;")
    op.execute("DROP FUNCTION IF EXISTS users_set_updated_at();")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
