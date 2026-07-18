"""Audit V2 trace sessions, spans, immutable events and signed exports.

Revision ID: b7a2d4e91f30
Revises: 34cd8281e2b3
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7a2d4e91f30"
down_revision: str | Sequence[str] | None = "34cd8281e2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"
TABLES = (
    "audit_sessions",
    "audit_spans",
    "audit_payloads",
    "audit_events",
    "audit_evaluations",
    "tenant_audit_keys",
)


def _uuid(name: str, *, nullable: bool = True, primary_key: bool = False) -> sa.Column:
    return sa.Column(
        name, postgresql.UUID(as_uuid=True), nullable=nullable, primary_key=primary_key
    )


def upgrade() -> None:
    op.drop_table("audit_trail")

    op.create_table(
        "audit_sessions",
        _uuid("id", nullable=False, primary_key=True),
        _uuid("tenant_id", nullable=False),
        _uuid("run_id", nullable=False),
        _uuid("department_id"),
        _uuid("workflow_id"),
        sa.Column("workflow_version", sa.String(128), nullable=False, server_default=""),
        _uuid("correlation_id", nullable=False),
        _uuid("parent_session_id"),
        _uuid("trace_id", nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("trigger_type", sa.String(32), nullable=False, server_default="manual"),
        _uuid("trigger_id"),
        _uuid("source_event_id"),
        _uuid("initiator_user_id"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        _uuid("current_span_id"),
        _uuid("input_payload_id"),
        _uuid("result_payload_id"),
        sa.Column("failure_summary", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        *[
            sa.Column(name, sa.BigInteger, nullable=False, server_default="0")
            for name in (
                "llm_call_count",
                "tool_call_count",
                "rag_call_count",
                "agent_count",
                "retry_count",
                "escalation_count",
                "input_tokens",
                "output_tokens",
                "cached_tokens",
                "reasoning_tokens",
                "human_wait_ms",
                "critical_path_ms",
                "last_sequence",
                "redaction_count",
            )
        ],
        sa.Column("estimated_cost_usd", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("last_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="2"),
        sa.Column("completeness_status", sa.String(32), nullable=False, server_default="complete"),
        sa.Column("attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["parent_session_id"], ["audit_sessions.id"]),
        sa.UniqueConstraint("tenant_id", "run_id", name="uq_audit_session_run"),
    )

    op.create_table(
        "audit_payloads",
        _uuid("id", nullable=False, primary_key=True),
        _uuid("tenant_id", nullable=False),
        _uuid("department_id"),
        sa.Column(
            "content_type", sa.String(128), nullable=False, server_default="application/json"
        ),
        sa.Column("classification", sa.String(32), nullable=False, server_default="confidential"),
        sa.Column("data", postgresql.JSONB, nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("redaction_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("redaction_paths", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("policy_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "audit_spans",
        _uuid("id", nullable=False, primary_key=True),
        _uuid("tenant_id", nullable=False),
        _uuid("session_id", nullable=False),
        _uuid("parent_span_id"),
        sa.Column("logical_node_id", sa.String(255), nullable=False, server_default=""),
        _uuid("task_id"),
        _uuid("agent_id"),
        _uuid("department_id"),
        sa.Column("actor_type", sa.String(32), nullable=False, server_default="system"),
        sa.Column("node_type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("attempt_no", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.BigInteger),
        sa.Column("ttft_ms", sa.BigInteger),
        sa.Column("provider", sa.String(64), nullable=False, server_default=""),
        sa.Column("model", sa.String(255), nullable=False, server_default=""),
        sa.Column("tool_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("tool_version", sa.String(128), nullable=False, server_default=""),
        _uuid("kb_id"),
        sa.Column("kb_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("error_code", sa.String(128), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text, nullable=False, server_default=""),
        *[
            sa.Column(name, sa.BigInteger, nullable=False, server_default="0")
            for name in (
                "input_tokens",
                "output_tokens",
                "cached_tokens",
                "reasoning_tokens",
            )
        ],
        sa.Column("estimated_cost_usd", sa.Numeric(18, 8), nullable=False, server_default="0"),
        _uuid("input_payload_id"),
        _uuid("output_payload_id"),
        sa.Column("attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["session_id"], ["audit_sessions.id"]),
    )

    op.create_table(
        "audit_events",
        _uuid("id", nullable=False, primary_key=True),
        _uuid("tenant_id", nullable=False),
        _uuid("session_id", nullable=False),
        _uuid("span_id"),
        _uuid("parent_span_id"),
        sa.Column("sequence_no", sa.BigInteger, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("event_type", sa.String(96), nullable=False),
        sa.Column("phase", sa.String(16), nullable=False, server_default="instant"),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
        sa.Column("actor_type", sa.String(32), nullable=False, server_default="system"),
        _uuid("actor_id"),
        sa.Column("status", sa.String(32)),
        _uuid("input_payload_id"),
        _uuid("output_payload_id"),
        sa.Column("attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="2"),
        sa.Column("prev_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["audit_sessions.id"]),
        sa.ForeignKeyConstraint(["input_payload_id"], ["audit_payloads.id"]),
        sa.ForeignKeyConstraint(["output_payload_id"], ["audit_payloads.id"]),
        sa.UniqueConstraint("session_id", "sequence_no", name="uq_audit_event_sequence"),
    )

    op.create_table(
        "audit_evaluations",
        _uuid("id", nullable=False, primary_key=True),
        _uuid("tenant_id", nullable=False),
        _uuid("session_id", nullable=False),
        sa.Column("evaluator_name", sa.String(255), nullable=False),
        sa.Column("evaluator_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("evaluator_type", sa.String(32), nullable=False, server_default="rule"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("score", sa.Numeric(8, 5)),
        sa.Column("metrics", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("criteria", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("evidence_span_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["session_id"], ["audit_sessions.id"]),
    )

    op.create_table(
        "tenant_audit_keys",
        _uuid("id", nullable=False, primary_key=True),
        _uuid("tenant_id", nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("algorithm", sa.String(32), nullable=False, server_default="Ed25519"),
        sa.Column("public_key", sa.LargeBinary, nullable=False),
        sa.Column("encrypted_private_key", sa.LargeBinary, nullable=False),
        sa.Column("nonce", sa.LargeBinary, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "version", name="uq_tenant_audit_key_version"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_tenant", table, ["tenant_id"])
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_policy ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
        )

    op.create_index("ix_audit_sessions_status_created", "audit_sessions", ["status", "created_at"])
    op.create_index(
        "ix_audit_spans_session_parent", "audit_spans", ["session_id", "parent_span_id"]
    )
    op.create_index(
        "ix_audit_spans_dimensions", "audit_spans", ["agent_id", "node_type", "status", "model"]
    )
    op.create_index(
        "ix_audit_events_session_sequence", "audit_events", ["session_id", "sequence_no"]
    )
    op.create_index("ix_audit_events_type_time", "audit_events", ["event_type", "occurred_at"])

    op.execute(f"GRANT SELECT, INSERT, UPDATE ON audit_sessions, audit_spans TO {APP_ROLE}")
    op.execute(
        "GRANT SELECT, INSERT ON audit_events, audit_payloads, "
        f"audit_evaluations, tenant_audit_keys TO {APP_ROLE}"
    )
    op.execute(
        "REVOKE UPDATE, DELETE, TRUNCATE ON audit_events, audit_payloads, "
        f"audit_evaluations FROM {APP_ROLE}"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
    op.create_table(
        "audit_trail",
        _uuid("id", nullable=False, primary_key=True),
        _uuid("tenant_id", nullable=False),
        _uuid("run_id", nullable=False),
        _uuid("step_id", nullable=False),
        _uuid("agent_id"),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("input", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("output", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("model", sa.String(255)),
    )
