"""Squashed baseline: full schema (tables + RLS + grants + functions + triggers).

This single migration replaces the 32 pre-`rebuild` migrations, which had a
duplicate revision id and unmerged heads (see docs / git history). It rebuilds
the ENTIRE current schema from a `pg_dump --schema-only` of a database that was
migrated through the full (repaired) chain, so RLS policies, GRANTs, the
`users_set_updated_at` trigger/function, and every table/index/constraint are
reproduced exactly on a fresh production database.

`revision = "baseline_0001"`, `down_revision = None` — this is the new root.
Existing databases were `alembic stamp baseline_0001`-ed (schema already
present); only truly empty (production) databases run the DDL below.

The `vaic_app` app role is created here because roles are cluster-global and a
single-database `pg_dump` does not emit `CREATE ROLE`; the dumped GRANT/POLICY
statements reference it, so it must exist first.

The dumped script contains many statements plus a dollar-quoted function body.
psycopg3's parameterized `execute()` rejects multi-statement strings, so the
script is sent through libpq's simple-query protocol (`PGconn.exec_`), which
runs the whole batch inside Alembic's migration transaction.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "baseline_0001"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA_SQL = Path(__file__).resolve().parent / "baseline_0001_schema.sql"


def _run_script(sql: str) -> None:
    """Execute a multi-statement SQL script on Alembic's bound connection.

    Uses libpq `PGconn.exec_` (simple query protocol) so the whole dump — with
    its dollar-quoted function body — runs as one batch inside the current
    transaction. Raises on any non-OK result so a failure rolls the migration
    back instead of leaving a half-built schema.
    """
    from psycopg import pq

    raw = op.get_bind().connection.driver_connection  # psycopg.Connection
    result = raw.pgconn.exec_(sql.encode("utf-8"))
    if result.status not in (pq.ExecStatus.COMMAND_OK, pq.ExecStatus.TUPLES_OK):
        message = (result.error_message or b"").decode("utf-8", "replace")
        raise RuntimeError(f"baseline schema load failed: {message or 'unknown error'}")


def upgrade() -> None:
    # App role first — cluster-global, not emitted by a single-db pg_dump, but
    # referenced by the dumped GRANT/POLICY statements. Idempotent (DO block:
    # CREATE ROLE IF NOT EXISTS is not available to non-superusers).
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vaic_app') "
        "THEN CREATE ROLE vaic_app NOLOGIN; END IF; END $$;"
    )
    op.execute("ALTER ROLE vaic_app NOBYPASSRLS;")

    _run_script(_SCHEMA_SQL.read_text(encoding="utf-8"))

    # pg_dump sets an empty search_path for the session; restore it so Alembic's
    # own bookkeeping (unqualified `alembic_version`) resolves normally.
    op.execute("RESET search_path;")


def downgrade() -> None:
    # Full teardown — this is the root migration, so downgrading drops everything.
    op.execute("DROP SCHEMA public CASCADE;")
    op.execute("CREATE SCHEMA public;")
