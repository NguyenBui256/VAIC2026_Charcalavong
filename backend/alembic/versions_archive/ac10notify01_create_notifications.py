"""create notifications table with RLS.

Tenant-isolation RLS (app.tenant_id GUC), mirroring
aa10database01_create_mini_app_databases.py. Each row also carries user_id
(recipient); the API additionally filters WHERE user_id = current user.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ac10notify01"
down_revision: str | Sequence[str] | None = "aa10database01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("ref", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])

    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY;")
    op.execute(
        """CREATE POLICY tenant_isolation_policy ON notifications
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON notifications TO vaic_app;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON notifications;")
    op.execute("ALTER TABLE notifications NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
