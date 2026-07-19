"""Add tenant criteria library and asynchronous LLM evaluation jobs.

Revision ID: d91f4a8c2e70
Revises: b7a2d4e91f30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d91f4a8c2e70"
down_revision: str | None = "b7a2d4e91f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def _uuid(name: str, **kwargs: object) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), **kwargs)


def _tenant_table(table: str) -> None:
    op.create_index(f"ix_{table}_tenant", table, ["tenant_id"])
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_policy ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "audit_evaluation_criteria",
        _uuid("id", primary_key=True, nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        _uuid("created_by_user_id", nullable=False),
        _uuid("updated_by_user_id", nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_audit_eval_criterion_active_name",
        "audit_evaluation_criteria",
        [sa.text("tenant_id"), sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    _tenant_table("audit_evaluation_criteria")

    op.create_table(
        "audit_evaluation_jobs",
        _uuid("id", primary_key=True, nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("session_id", nullable=False),
        _uuid("requested_by_user_id", nullable=False),
        sa.Column("requester_role", sa.String(64), nullable=False),
        _uuid("requester_department_id"),
        sa.Column("criteria_snapshot", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("phase", sa.String(64), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("error_code", sa.String(128), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        _uuid("evaluation_id"),
        sa.Column("boundary_sequence", sa.BigInteger(), nullable=False),
        sa.Column("boundary_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["session_id"], ["audit_sessions.id"]),
    )
    op.create_index(
        "uq_audit_eval_job_active_session",
        "audit_evaluation_jobs",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','collecting_context','judging','validating')"),
    )
    _tenant_table("audit_evaluation_jobs")

    additions = [
        ("requested_by_user_id", postgresql.UUID(as_uuid=True)),
        ("provider", sa.String(64), "''"),
        ("model", sa.String(255), "''"),
        ("overall_pass", sa.Boolean()),
        ("summary", sa.Text(), "''"),
        ("assessment", sa.Text(), "''"),
        ("insights", postgresql.JSONB(), "[]"),
        ("issues", postgresql.JSONB(), "[]"),
        ("strengths", postgresql.JSONB(), "[]"),
        ("context_manifest", postgresql.JSONB(), "{}"),
        ("input_tokens", sa.BigInteger(), "0"),
        ("output_tokens", sa.BigInteger(), "0"),
        ("latency_ms", sa.BigInteger(), "0"),
        ("estimated_cost_usd", sa.Numeric(18, 8), "0"),
    ]
    for item in additions:
        name, typ, *default = item
        op.add_column(
            "audit_evaluations",
            sa.Column(name, typ, nullable=True if not default else False, server_default=default[0] if default else None),
        )

    op.execute(f"GRANT SELECT, INSERT, UPDATE ON audit_evaluation_criteria, audit_evaluation_jobs TO {APP_ROLE}")
    op.execute(f"GRANT DELETE ON audit_evaluation_jobs TO {APP_ROLE}")


def downgrade() -> None:
    for name in (
        "estimated_cost_usd", "latency_ms", "output_tokens", "input_tokens", "context_manifest",
        "strengths", "issues", "insights", "assessment", "summary", "overall_pass", "model",
        "provider", "requested_by_user_id",
    ):
        op.drop_column("audit_evaluations", name)
    op.drop_table("audit_evaluation_jobs")
    op.drop_table("audit_evaluation_criteria")
