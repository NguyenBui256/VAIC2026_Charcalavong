"""Integration tests for the audit sink — AD-4 compliance (Story 1.5).

Test plan covers every AC in the story:
    - audit_trail table exists with correct columns
    - RLS enabled + forced, policy enforces tenant_id
    - vaic_app has INSERT only (UPDATE/DELETE/TRUNCATE revoked)
    - audit.log() is the only write path (PostgresAuditSink.log)
    - log() RAISES on DB failure (AD-4 — crash the Run)
    - Pre-crash log() calls are persisted (durability)
    - Every entry has UTC ISO 8601 timestamp with milliseconds
    - Every entry has UUID v7 step_id
    - audit_trail is tenant-scoped via RLS (cross-tenant isolation)
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.db import AdminSessionLocal, SessionLocal
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.tenant_context import set_tenant_context, set_tenant_session_var

# --- Helper: run SQL as vaic_app role within a transaction ---------------


def _as_app(session: Session, tenant_id: uuid.UUID) -> None:
    """Switch session to vaic_app role + set tenant GUC.

    Issues ``SET LOCAL ROLE vaic_app`` so the superuser connection drops
    privileges and becomes subject to RLS, then sets ``app.tenant_id``.
    """
    session.execute(text("SET LOCAL ROLE vaic_app;"))
    set_tenant_session_var(session, tenant_id)


# --- Helper: build a valid AuditEntry ------------------------------------


def make_entry(
    run_id: str | None = None,
    step_id: str | None = None,
    agent_id: str | None = None,
    ts: str | None = None,
    type_: str = "model_invocation",
    model: str = "claude-sonnet-4-20250514",
) -> AuditEntry:
    """Build a valid AuditEntry with sensible defaults."""
    return AuditEntry(
        run_id=run_id or str(uuid7()),
        step_id=step_id or str(uuid7()),
        agent_id=agent_id or str(uuid7()),
        ts=ts or utcnow_iso_ms(),
        type=type_,
        input={"prompt": "Hello"},
        output={"response": "World"},
        latency_ms=42,
        model=model,
    )


# =====================================================================
# AC: audit_trail table exists with correct columns
# =====================================================================


class TestAuditTrailTable:
    """Verify the audit_trail table schema."""

    def test_audit_trail_table_exists(self, seed_data):
        """Table exists in the database."""
        with AdminSessionLocal() as s:
            result = s.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'audit_trail')"
                )
            ).scalar()
            assert result is True

    def test_audit_trail_has_expected_columns(self, seed_data):
        """All FR-21 columns + tenant_id + id PK present."""
        expected = {
            "id",
            "tenant_id",
            "run_id",
            "step_id",
            "agent_id",
            "ts",
            "type",
            "input",
            "output",
            "latency_ms",
            "model",
        }
        with AdminSessionLocal() as s:
            cols = {
                row[0]
                for row in s.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'audit_trail'"
                    )
                ).fetchall()
            }
        assert expected.issubset(cols), (
            f"Missing columns: {expected - cols}"
        )

    def test_audit_trail_id_is_primary_key(self, seed_data):
        """The `id` column is the primary key."""
        with AdminSessionLocal() as s:
            result = s.execute(
                text(
                    "SELECT a.attname FROM pg_index i "
                    "JOIN pg_attribute a ON "
                    "  a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
                    "WHERE i.indrelid = 'audit_trail'::regclass "
                    "AND i.indisprimary"
                )
            ).scalar()
            assert result == "id"


# =====================================================================
# AC: RLS enabled + forced on audit_trail
# =====================================================================


class TestAuditTrailRLS:
    """Verify RLS configuration on audit_trail."""

    def test_rls_enabled_on_audit_trail(self, seed_data):
        """RLS is enabled."""
        with AdminSessionLocal() as s:
            result = s.execute(
                text(
                    "SELECT relrowsecurity FROM pg_class "
                    "WHERE relname = 'audit_trail'"
                )
            ).scalar()
            assert result is True

    def test_rls_forced_on_audit_trail(self, seed_data):
        """RLS is FORCED (even owner subject)."""
        with AdminSessionLocal() as s:
            result = s.execute(
                text(
                    "SELECT relforcerowsecurity FROM pg_class "
                    "WHERE relname = 'audit_trail'"
                )
            ).scalar()
            assert result is True

    def test_rls_policy_uses_tenant_id(self, seed_data):
        """Policy uses tenant_id = current_setting('app.tenant_id')::uuid."""
        with AdminSessionLocal() as s:
            policies = s.execute(
                text(
                    "SELECT policyname, qual, with_check "
                    "FROM pg_policies "
                    "WHERE tablename = 'audit_trail'"
                )
            ).fetchall()
            assert len(policies) >= 1
            for polname, qual, check in policies:
                qual_str = str(qual) if qual else ""
                check_str = str(check) if check else ""
                assert "tenant_id" in qual_str.lower(), (
                    f"Policy {polname} USING does not reference tenant_id"
                )
                assert "tenant_id" in check_str.lower(), (
                    f"Policy {polname} WITH CHECK does not reference tenant_id"
                )
                assert "current_setting" in qual_str.lower(), (
                    f"Policy {polname} USING does not use current_setting"
                )


# =====================================================================
# AC: vaic_app has INSERT only — UPDATE/DELETE/TRUNCATE revoked
# =====================================================================


class TestAppendOnlyPrivileges:
    """Verify vaic_app cannot UPDATE, DELETE, or TRUNCATE audit_trail."""

    def test_vaic_app_cannot_update_audit_trail(self, seed_data):
        """UPDATE raises InsufficientPrivilege as vaic_app."""
        tenant_a = seed_data["tenant_a_id"]
        with SessionLocal() as s:
            _as_app(s, tenant_a)
            with pytest.raises(Exception) as exc_info:
                s.execute(text("UPDATE audit_trail SET type = 'hacked'"))
            assert "permission" in str(exc_info.value).lower() or (
                "insufficient" in str(exc_info.value).lower()
            )
            s.rollback()

    def test_vaic_app_cannot_delete_audit_trail(self, seed_data):
        """DELETE raises InsufficientPrivilege as vaic_app."""
        tenant_a = seed_data["tenant_a_id"]
        with SessionLocal() as s:
            _as_app(s, tenant_a)
            with pytest.raises(Exception) as exc_info:
                s.execute(text("DELETE FROM audit_trail"))
            assert "permission" in str(exc_info.value).lower() or (
                "insufficient" in str(exc_info.value).lower()
            )
            s.rollback()

    def test_vaic_app_cannot_truncate_audit_trail(self, seed_data):
        """TRUNCATE raises InsufficientPrivilege as vaic_app."""
        tenant_a = seed_data["tenant_a_id"]
        with SessionLocal() as s:
            _as_app(s, tenant_a)
            with pytest.raises(Exception) as exc_info:
                s.execute(text("TRUNCATE TABLE audit_trail"))
            assert "permission" in str(exc_info.value).lower() or (
                "insufficient" in str(exc_info.value).lower()
            )
            s.rollback()

    def test_vaic_app_grants_audit_trail(self, seed_data):
        """Verify privilege bits: INSERT=yes, UPDATE/DELETE=no."""
        with AdminSessionLocal() as s:
            # Check what privileges vaic_app has on audit_trail.
            result = s.execute(
                text(
                    """
                    SELECT privilege_type
                    FROM information_schema.role_table_grants
                    WHERE table_name = 'audit_trail'
                      AND grantee = 'vaic_app'
                    """
                )
            ).fetchall()
            privs = {r[0] for r in result}
            assert "INSERT" in privs, "vaic_app must have INSERT"
            assert "UPDATE" not in privs, "vaic_app must NOT have UPDATE"
            assert "DELETE" not in privs, "vaic_app must NOT have DELETE"


# =====================================================================
# AC: audit.log(entry) is the ONLY path to write
# =====================================================================


class TestPostgresAuditSink:
    """Verify the PostgresAuditSink implements AuditPort and works."""

    def test_postgres_audit_sink_implements_audit_port(self):
        """PostgresAuditSink satisfies the AuditPort protocol."""
        sink = PostgresAuditSink()
        assert isinstance(sink, AuditPort)

    def test_log_inserts_entry_successfully(self, seed_data):
        """log() persists a single entry to audit_trail."""
        tenant_a = seed_data["tenant_a_id"]
        set_tenant_context(tenant_a)

        entry = make_entry()
        sink = PostgresAuditSink()
        sink.log(entry)

        # Read it back from admin connection.
        with AdminSessionLocal() as s:
            row = s.execute(
                text(
                    "SELECT run_id, step_id, type, latency_ms, model "
                    "FROM audit_trail "
                    "WHERE step_id = :sid"
                ),
                {"sid": entry.step_id},
            ).fetchone()

        assert row is not None
        assert str(row[0]) == entry.run_id
        assert str(row[1]) == entry.step_id
        assert row[2] == entry.type
        assert row[3] == 42
        assert row[4] == "claude-sonnet-4-20250514"

    def test_log_with_null_agent_id(self, seed_data):
        """agent_id can be None (orchestrator steps)."""
        tenant_a = seed_data["tenant_a_id"]
        set_tenant_context(tenant_a)

        entry = AuditEntry(
            run_id=str(uuid7()),
            step_id=str(uuid7()),
            agent_id="",  # empty string → NULL in DB
            ts=utcnow_iso_ms(),
            type="decomposition",
            input={"task": "split"},
            output={"subtasks": 3},
            latency_ms=10,
            model="",
        )
        sink = PostgresAuditSink()
        sink.log(entry)

        with AdminSessionLocal() as s:
            row = s.execute(
                text(
                    "SELECT agent_id FROM audit_trail "
                    "WHERE step_id = :sid"
                ),
                {"sid": entry.step_id},
            ).fetchone()

        assert row is not None
        assert row[0] is None  # agent_id is NULL


# =====================================================================
# AC: When log() fails, it RAISES (AD-4)
# =====================================================================


class TestAuditSinkFailureCrashes:
    """AD-4: log() failure must propagate — never swallow."""

    def test_log_raises_on_db_failure(self, seed_data):
        """If DB write fails, log() raises — Run transitions to failed."""
        tenant_a = seed_data["tenant_a_id"]
        set_tenant_context(tenant_a)

        entry = make_entry()
        sink = PostgresAuditSink()

        # Patch SessionLocal to simulate a broken session.
        class _BrokenSession:
            def execute(self, *a, **kw):
                raise ConnectionError("DB is down")

            def commit(self):
                raise ConnectionError("DB is down")

            def rollback(self):
                pass

            def close(self):
                pass

        with (
            patch(
                "app.core.adapters.audit_postgres.SessionLocal",
                return_value=_BrokenSession(),
            ),
            pytest.raises(ConnectionError),
        ):
            sink.log(entry)

    def test_log_raises_on_constraint_violation(self, seed_data):
        """Constraint violation propagates — not swallowed."""
        tenant_a = seed_data["tenant_a_id"]
        set_tenant_context(tenant_a)

        entry = make_entry()
        sink = PostgresAuditSink()

        # Patch execute to simulate a constraint error.
        original = SessionLocal

        class _ConstraintSession:
            def __init__(self):
                self._real = original()

            def execute(self, stmt, params=None):
                # Simulate IntegrityError on the INSERT only.
                raise RuntimeError("unique constraint violation")

            def commit(self):
                pass

            def rollback(self):
                self._real.rollback()

            def close(self):
                self._real.close()

        with (
            patch(
                "app.core.adapters.audit_postgres.SessionLocal",
                return_value=_ConstraintSession(),
            ),
            pytest.raises(RuntimeError, match="constraint"),
        ):
            sink.log(entry)


# =====================================================================
# AC: Pre-crash log() calls are persisted (durability)
# =====================================================================


class TestAuditDurability:
    """Entries written before a crash survive (each log() commits)."""

    def test_entries_persist_before_crash(self, seed_data):
        """Two log() calls succeed, then caller crashes — both rows present."""
        tenant_a = seed_data["tenant_a_id"]
        set_tenant_context(tenant_a)

        entry1 = make_entry(type_="decomposition")
        entry2 = make_entry(type_="task_dispatch")

        sink = PostgresAuditSink()
        sink.log(entry1)
        sink.log(entry2)

        # Simulate caller crash.
        try:
            raise RuntimeError("caller crashed after two audit writes")
        except RuntimeError:
            pass

        # Both rows must be in the DB (admin bypasses RLS).
        with AdminSessionLocal() as s:
            rows = s.execute(
                text(
                    "SELECT step_id, type FROM audit_trail "
                    "WHERE step_id IN (:s1, :s2) ORDER BY ts"
                ),
                {"s1": entry1.step_id, "s2": entry2.step_id},
            ).fetchall()

        assert len(rows) == 2
        assert str(rows[0][0]) == entry1.step_id
        assert str(rows[1][0]) == entry2.step_id


# =====================================================================
# AC: Every entry has UTC ISO 8601 timestamp with millisecond precision
# =====================================================================


class TestTimestampFormat:
    """Verify ts column stores timestamptz with millisecond precision."""

    def test_ts_is_timestamptz_type(self, seed_data):
        """The ts column is timestamptz in the DB."""
        with AdminSessionLocal() as s:
            data_type = s.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name = 'audit_trail' AND column_name = 'ts'"
                )
            ).scalar()
            assert data_type == "timestamp with time zone"

    def test_log_stores_utc_timestamp(self, seed_data):
        """The ts value is stored and reads back as UTC."""
        tenant_a = seed_data["tenant_a_id"]
        set_tenant_context(tenant_a)

        # Use a specific timestamp with milliseconds.
        ts_str = "2026-07-17T12:34:56.789Z"
        entry = make_entry(ts=ts_str)
        sink = PostgresAuditSink()
        sink.log(entry)

        with AdminSessionLocal() as s:
            row = s.execute(
                text(
                    "SELECT ts FROM audit_trail WHERE step_id = :sid"
                ),
                {"sid": entry.step_id},
            ).fetchone()

        assert row is not None
        stored_ts = row[0]
        # Should be a timezone-aware datetime.
        assert stored_ts.tzinfo is not None
        # Should be in UTC (offset zero).
        assert stored_ts.utcoffset().total_seconds() == 0
        # Should have millisecond precision.
        assert stored_ts.microsecond == 789000


# =====================================================================
# AC: Every entry has UUID v7 step_id
# =====================================================================


class TestUUIDv7StepId:
    """Verify step_id is UUID v7 (version nibble = 7)."""

    def test_step_id_is_uuid_v7(self, seed_data):
        """step_id in the DB has version nibble 7."""
        tenant_a = seed_data["tenant_a_id"]
        set_tenant_context(tenant_a)

        step_id = uuid7()
        assert step_id.version == 7, "Pre-condition: uuid7() must be v7"

        entry = make_entry(step_id=str(step_id))
        sink = PostgresAuditSink()
        sink.log(entry)

        with AdminSessionLocal() as s:
            row = s.execute(
                text(
                    "SELECT step_id FROM audit_trail WHERE step_id = :sid"
                ),
                {"sid": str(step_id)},
            ).fetchone()

        assert row is not None
        stored = uuid.UUID(str(row[0]))
        assert stored.version == 7, (
            f"step_id version nibble is {stored.version}, expected 7"
        )


# =====================================================================
# AC: audit_trail is tenant-scoped via RLS
# =====================================================================


class TestAuditTrailTenantIsolation:
    """TenantA cannot read TenantB's audit rows (RLS)."""

    def test_tenant_a_cannot_read_tenant_b_audit_rows(self, seed_data):
        """Cross-tenant SELECT returns empty under RLS."""
        tenant_a = seed_data["tenant_a_id"]
        tenant_b = seed_data["tenant_b_id"]

        # Write an entry as TenantA.
        set_tenant_context(tenant_a)
        entry_a = make_entry(type_="model_invocation")
        sink = PostgresAuditSink()
        sink.log(entry_a)

        # Write an entry as TenantB.
        set_tenant_context(tenant_b)
        entry_b = make_entry(type_="tool_call")
        sink2 = PostgresAuditSink()
        sink2.log(entry_b)

        # Reset context
        set_tenant_context(tenant_a)

        # As TenantA, query for TenantB's step_id — should get nothing.
        with SessionLocal() as s:
            _as_app(s, tenant_a)
            row = s.execute(
                text(
                    "SELECT step_id FROM audit_trail "
                    "WHERE step_id = :sid"
                ),
                {"sid": entry_b.step_id},
            ).fetchone()

        assert row is None, (
            "TenantA should NOT see TenantB's audit row (RLS)"
        )

        # As TenantA, query own row — should find it.
        with SessionLocal() as s:
            _as_app(s, tenant_a)
            row = s.execute(
                text(
                    "SELECT step_id FROM audit_trail "
                    "WHERE step_id = :sid"
                ),
                {"sid": entry_a.step_id},
            ).fetchone()

        assert row is not None, (
            "TenantA should see own audit row (RLS)"
        )

    def test_tenant_b_cannot_read_tenant_a_audit_rows(self, seed_data):
        """Reverse direction: TenantB cannot see TenantA's rows."""
        tenant_a = seed_data["tenant_a_id"]
        tenant_b = seed_data["tenant_b_id"]

        # Write as TenantA.
        set_tenant_context(tenant_a)
        entry_a = make_entry(type_="escalation")
        sink = PostgresAuditSink()
        sink.log(entry_a)

        # As TenantB, query for TenantA's step_id.
        with SessionLocal() as s:
            _as_app(s, tenant_b)
            row = s.execute(
                text(
                    "SELECT step_id FROM audit_trail "
                    "WHERE step_id = :sid"
                ),
                {"sid": entry_a.step_id},
            ).fetchone()

        assert row is None, (
            "TenantB should NOT see TenantA's audit row (RLS)"
        )

    def test_rls_rejects_wrong_tenant_insert(self, seed_data):
        """RLS WITH CHECK rejects INSERT with wrong tenant_id."""
        tenant_a = seed_data["tenant_a_id"]
        tenant_b = seed_data["tenant_b_id"]

        # Set context as TenantA but try to INSERT with TenantB's tenant_id.
        set_tenant_context(tenant_a)
        with SessionLocal() as s:
            _as_app(s, tenant_a)
            # RLS WITH CHECK violation on INSERT with mismatched tenant_id.
            with pytest.raises(Exception) as exc_info:
                s.execute(
                    text(
                        "INSERT INTO audit_trail "
                        "(id, tenant_id, run_id, step_id, agent_id, "
                        " ts, type, input, output, latency_ms, model) "
                        "VALUES "
                        "(:id, :tid, :rid, :sid, NULL, now(), 'test', "
                        " '{}'::jsonb, '{}'::jsonb, 1, NULL)"
                    ),
                    {
                        "id": str(uuid7()),
                        "tid": str(tenant_b),
                        "rid": str(uuid7()),
                        "sid": str(uuid7()),
                    },
                )
                s.commit()
            # Verify it's an RLS violation error.
            assert "row-level security" in str(exc_info.value).lower() or (
                "check" in str(exc_info.value).lower()
            )
            s.rollback()
