"""KB document user-ACL (owner + grants) — Sub-project A (spec D2).

Access resolution (service layer; RLS only isolates tenants):
- Owner  -> effective 'manager'.
- Grant  -> its role ('viewer'|'manager').
- Else   -> no access.
`viewer` may read + tick into an editable agent; `manager` may also
add/remove grants + delete the doc.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AuthorizationError, ValidationError
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.kb_models import KbDocument, KbDocumentGrant
from app.modules.agent_builder.service import Principal

__all__ = [
    "effective_role", "require_access", "list_grants", "set_grant",
    "revoke_grant", "serialize_grant",
]

_VALID_ROLES = {"viewer", "manager"}


def effective_role(session: Session, doc: KbDocument, user_id: uuid.UUID) -> str | None:
    if doc.owner_id == user_id:
        return "manager"
    grant = session.get(KbDocumentGrant, {"document_id": doc.id, "user_id": user_id})
    return grant.role if grant is not None else None


def require_access(
    session: Session, doc: KbDocument, user_id: uuid.UUID, *, need_manage: bool = False
) -> None:
    role = effective_role(session, doc, user_id)
    if role is None or (need_manage and role != "manager"):
        raise AuthorizationError("Not authorized for this document", code="FORBIDDEN")


def list_grants(session: Session, doc_id: uuid.UUID) -> list[KbDocumentGrant]:
    return list(
        session.execute(
            select(KbDocumentGrant).where(KbDocumentGrant.document_id == doc_id)
        ).scalars().all()
    )


def set_grant(
    session: Session, *, doc_id: uuid.UUID, principal: Principal,
    user_id: uuid.UUID, role: str,
) -> KbDocumentGrant:
    if role not in _VALID_ROLES:
        raise ValidationError(f"Invalid role '{role}'", code="validation_error")
    from app.modules.agent_builder.kb_service import _get_document_row  # local import avoids cycle
    doc = _get_document_row(session, doc_id)
    require_access(session, doc, principal.user_id, need_manage=True)
    grant = session.get(KbDocumentGrant, {"document_id": doc_id, "user_id": user_id})
    if grant is None:
        grant = KbDocumentGrant(
            document_id=doc_id, user_id=user_id, role=role, tenant_id=tenant_context.get()
        )
        session.add(grant)
    else:
        grant.role = role
    session.commit()
    session.refresh(grant)
    return grant


def revoke_grant(
    session: Session, *, doc_id: uuid.UUID, principal: Principal, user_id: uuid.UUID
) -> None:
    from app.modules.agent_builder.kb_service import _get_document_row
    doc = _get_document_row(session, doc_id)
    require_access(session, doc, principal.user_id, need_manage=True)
    grant = session.get(KbDocumentGrant, {"document_id": doc_id, "user_id": user_id})
    if grant is not None:
        session.delete(grant)
        session.commit()


def serialize_grant(g: KbDocumentGrant) -> dict:
    return {"document_id": str(g.document_id), "user_id": str(g.user_id), "role": g.role}
