"""create kb_documents rls

Revision ID: 9e84be8908a0
Revises: 5d11ee08a690
Create Date: 2026-07-18 00:18:56.299395

Story 2.4: creates the ``kb_documents`` table — Knowledge Base document
records for the Agent Builder KB tab. Mirrors the RLS + grant DDL pattern of
``34cd8281e2b3_create_audit_trail_table.py`` / ``7e8b08b45590_create_agents_rls.py``.

Schema columns:
    id                     UUID PK (UUID v7, generated app-side)
    tenant_id              UUID NOT NULL FK tenants.id ON DELETE CASCADE
    agent_id               UUID NOT NULL FK agents.id ON DELETE CASCADE
    department_id          UUID NOT NULL FK departments.id ON DELETE RESTRICT
                            (denormalized from the Agent for the AD-11 scope check)
    filename               varchar(512) NOT NULL
    content_type           varchar(128) NOT NULL
    size_bytes             bigint NOT NULL
    status                 varchar(32) NOT NULL DEFAULT 'processing'
                            (processing|indexed|failed)
    failure_reason         text NULL
    external_document_id   varchar(255) NULL
    chunk_count            integer NOT NULL DEFAULT 0
    created_at             timestamptz NOT NULL DEFAULT now()
    updated_at             timestamptz NOT NULL DEFAULT now()

RLS (AD-2): ENABLE + FORCE + tenant_isolation_policy on tenant_id.

Unlike ``agents``/``audit_trail``, DELETE is permitted (OQ-3) — a KB delete
is a legitimate index removal, not audit tampering.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e84be8908a0"
down_revision: str | Sequence[str] | None = "5d11ee08a690"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"
TABLE = "kb_documents"


def upgrade() -> None:
    """Create kb_documents table with RLS + full-grant (incl. DELETE)."""
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="processing"
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("external_document_id", sa.String(255), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index("ix_kb_documents_tenant_id", TABLE, ["tenant_id"])
    op.create_index("ix_kb_documents_agent_id", TABLE, ["agent_id"])

    # --- RLS: ENABLE + FORCE + policy -------------------------------------
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy
            ON {TABLE}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
        """
    )

    # --- Full grant incl. DELETE (OQ-3: index removal, not audit data) ----
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {TABLE} TO {APP_ROLE};")


def downgrade() -> None:
    """Reverse: drop policy, disable RLS, drop table."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {TABLE};")
    op.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")
    op.drop_table(TABLE)
