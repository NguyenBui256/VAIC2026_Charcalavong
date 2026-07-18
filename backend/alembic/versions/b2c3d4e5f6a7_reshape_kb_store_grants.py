"""reshape kb store + grants + agent_kb_documents

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-18

Greenfield reset (Sub-project A): kb_documents becomes a tenant-wide store
(owner_id replaces agent_id, department_id now optional); user access is
granted via kb_document_grants, agent RAG access via agent_kb_documents.
Old agent-owned kb_documents rows are demo-only and are dropped. Mirrors
the RLS DDL of a1b2c3d4e5f6.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE};")


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kb_documents CASCADE;")
    op.create_table(
        "kb_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="processing"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("external_document_id", sa.String(255), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_kb_documents_tenant_id", "kb_documents", ["tenant_id"])
    op.create_index("ix_kb_documents_owner_id", "kb_documents", ["owner_id"])
    _enable_rls("kb_documents")

    op.create_table(
        "kb_document_grants",
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("kb_documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('viewer','manager')", name="ck_kb_grant_role"),
    )
    op.create_index("ix_kb_document_grants_tenant_id", "kb_document_grants", ["tenant_id"])
    op.create_index("ix_kb_document_grants_user_id", "kb_document_grants", ["user_id"])
    _enable_rls("kb_document_grants")

    op.create_table(
        "agent_kb_documents",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("kb_documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_kb_documents_tenant_id", "agent_kb_documents", ["tenant_id"])
    op.create_index("ix_agent_kb_documents_document_id", "agent_kb_documents", ["document_id"])
    _enable_rls("agent_kb_documents")


def downgrade() -> None:
    for t in ("agent_kb_documents", "kb_document_grants", "kb_documents"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {t};")
        op.execute(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")
        op.drop_table(t)
