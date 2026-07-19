"""add kb_documents content blob

Revision ID: c1d2e3f4a5b6
Revises: a7b8c9d0e1f2
Create Date: 2026-07-19 07:20:00.000000

KB "view document" feature — persist the original uploaded bytes so builders
and users can view/download the source file. RAG (`rag.ingest`) only keeps
chunks/embeddings, never the original, so the file was previously discarded.

Adds a nullable `content` BYTEA column to `kb_documents`. Nullable so existing
rows (uploaded before this feature) stay valid; those simply have no stored
bytes and the content endpoint returns a friendly 404. RLS on `kb_documents`
(migration 9e84be8908a0) already scopes the table — table-level SELECT covers
the new column, no policy/grant change needed. `ADD COLUMN IF NOT EXISTS`
keeps this idempotent (dev == prod DB).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a11kbcontent01"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "kb_documents"
COLUMN = "content"


def upgrade() -> None:
    """Add nullable `content` BYTEA to store original uploaded file bytes."""
    op.execute(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS {COLUMN} BYTEA;")


def downgrade() -> None:
    """Reverse: drop the content column."""
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS {COLUMN};")
