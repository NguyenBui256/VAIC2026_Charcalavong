"""T8.2 — RLS applied to `kb_documents`; raw SQL cross-tenant read returns empty.

Mirrors `test_agents_rls.py`'s pattern: `SET LOCAL ROLE vaic_app` to drop
superuser privileges, then verify tenant isolation via ORM and raw SQL.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import AdminSessionLocal
from app.modules.agent_builder.kb_models import KbDocument


def _as_app(session: Session, tenant_id: uuid.UUID) -> None:
    session.execute(text("SET LOCAL ROLE vaic_app"))
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def _seed_kb_doc(
    *, tenant_id: uuid.UUID, agent_id: uuid.UUID, department_id: uuid.UUID, filename: str
) -> uuid.UUID:
    doc_id = uuid.uuid4()
    with AdminSessionLocal() as s:
        s.add(
            KbDocument(
                id=doc_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                department_id=department_id,
                filename=filename,
                content_type="application/pdf",
                size_bytes=100,
                status="indexed",
            )
        )
        s.commit()
    return doc_id


def test_rls_enabled_and_forced_on_kb_documents() -> None:
    with AdminSessionLocal() as s:
        row = s.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = 'kb_documents'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] is True
    assert row[1] is True


def test_rls_policy_uses_tenant_id() -> None:
    with AdminSessionLocal() as s:
        policies = s.execute(
            text(
                "SELECT policyname, qual, with_check FROM pg_policies "
                "WHERE tablename = 'kb_documents'"
            )
        ).fetchall()
    assert len(policies) >= 1
    for _name, qual, check in policies:
        assert "tenant_id" in str(qual).lower()
        assert "tenant_id" in str(check).lower()


def test_cross_tenant_orm_and_raw_sql_returns_empty(
    app_session: Session, seeded_agent: dict[str, Any]
) -> None:
    """TenantB's kb_document is invisible under TenantA's RLS context."""
    doc_a = _seed_kb_doc(
        tenant_id=seeded_agent["tenant_agents_id"],
        agent_id=seeded_agent["agent_a_id"],
        department_id=seeded_agent["dept_agents_id"],
        filename="tenant-a-doc.pdf",
    )
    doc_b = _seed_kb_doc(
        tenant_id=seeded_agent["tenant_b_id"],
        agent_id=seeded_agent["agent_b_id"],
        department_id=seeded_agent["dept_b_id"],
        filename="tenant-b-doc.pdf",
    )
    try:
        _as_app(app_session, seeded_agent["tenant_agents_id"])

        rows = app_session.execute(select(KbDocument)).scalars().all()
        names = {r.filename for r in rows}
        assert "tenant-a-doc.pdf" in names
        assert "tenant-b-doc.pdf" not in names

        raw = app_session.execute(
            text("SELECT filename FROM kb_documents WHERE id = :did"),
            {"did": str(doc_b)},
        ).fetchall()
        assert raw == []
    finally:
        with AdminSessionLocal() as s:
            s.execute(
                text("DELETE FROM kb_documents WHERE id IN (:a, :b)"),
                {"a": str(doc_a), "b": str(doc_b)},
            )
            s.commit()


def test_vaic_app_can_delete_kb_documents(seeded_agent: dict[str, Any]) -> None:
    """DELETE is permitted for vaic_app on kb_documents (OQ-3, unlike agents)."""
    from app.core.db import SessionLocal

    doc_id = _seed_kb_doc(
        tenant_id=seeded_agent["tenant_agents_id"],
        agent_id=seeded_agent["agent_a_id"],
        department_id=seeded_agent["dept_agents_id"],
        filename="deletable.pdf",
    )
    with SessionLocal() as s:
        _as_app(s, seeded_agent["tenant_agents_id"])
        s.execute(text("DELETE FROM kb_documents WHERE id = :id"), {"id": str(doc_id)})
        s.commit()

    with AdminSessionLocal() as s:
        row = s.execute(
            text("SELECT id FROM kb_documents WHERE id = :id"), {"id": str(doc_id)}
        ).fetchone()
    assert row is None
