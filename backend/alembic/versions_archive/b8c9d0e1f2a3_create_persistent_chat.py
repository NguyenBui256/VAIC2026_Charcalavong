"""create persistent chat, attachments, and mutations

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "chat_sessions",
    "chat_messages",
    "chat_attachments",
    "chat_message_attachments",
    "chat_mutations",
)


def _tenant_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        *_tenant_columns(),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", sa.String(32), nullable=True),
        sa.Column("model_name", sa.String(255), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "scope IN ('execution','graph_authoring','mini_app_edit')",
            name="ck_chat_sessions_scope",
        ),
        sa.CheckConstraint(
            "target_type IN ('agent','workflow','mini_app')", name="ck_chat_sessions_target"
        ),
    )
    op.create_table(
        "chat_messages",
        *_tenant_columns(),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("client_message_id", sa.String(128), nullable=True),
        sa.Column(
            "reply_to_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_id", sa.String(32), nullable=True),
        sa.Column("model_name", sa.String(255), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("session_id", "client_message_id", name="uq_chat_client_message"),
        sa.CheckConstraint(
            "role IN ('user','assistant','system','tool')", name="ck_chat_messages_role"
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed','failed')", name="ck_chat_messages_status"
        ),
    )
    op.create_table(
        "chat_attachments",
        *_tenant_columns(),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("extraction_status", sa.String(16), nullable=False, server_default="extracting"),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "extraction_status IN ('extracting','ready','failed')", name="ck_chat_attachment_status"
        ),
    )
    op.create_table(
        "chat_message_attachments",
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "attachment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_attachments.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_table(
        "chat_mutations",
        *_tenant_columns(),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("before_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("after_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("before_version", sa.String(64), nullable=False),
        sa.Column("after_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="applied"),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("undone_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('applied','undone')", name="ck_chat_mutation_status"),
    )
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_policy ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO vaic_app")
    op.create_index("ix_chat_sessions_owner_updated", "chat_sessions", ["owner_id", "updated_at"])
    op.create_index(
        "ix_chat_messages_session_created", "chat_messages", ["session_id", "created_at"]
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
