"""Compatibility import location for the Audit V2 PostgreSQL adapter."""

from app.modules.audit.sink import PostgresAuditSink

__all__ = ["PostgresAuditSink"]
