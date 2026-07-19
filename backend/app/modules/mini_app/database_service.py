"""Mini-App Database service — CRUD over reusable entity-schema templates.

A database is a named `entity_schema`. Mini-apps reference it via
`mini_apps.database_id`; binding copies the schema. `list_database_rows`
aggregates `mini_app_rows` for every app referencing the database (read-only).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.mini_app.database_models import MiniAppDatabase
from app.modules.mini_app.models import MiniApp, MiniAppRow
from app.modules.mini_app.schema_validation import validate_entity_schema
from app.modules.mini_app.visibility import MiniAppPrincipal


def list_databases(session: Session) -> list[MiniAppDatabase]:
    return list(
        session.execute(
            select(MiniAppDatabase).order_by(MiniAppDatabase.created_at.desc())
        ).scalars()
    )


def get_database(session: Session, db_id: uuid.UUID) -> MiniAppDatabase:
    db = session.get(MiniAppDatabase, db_id)
    if db is None:
        raise NotFoundError(f"mini-app database {db_id} not found")
    return db


def create_database(
    session: Session, *, principal: MiniAppPrincipal,
    name: str, description: str, entity_schema: dict[str, Any],
) -> MiniAppDatabase:
    validate_entity_schema(entity_schema)  # raises SchemaValidationError (-> 422)
    if _name_taken(session, principal.tenant_id, name):
        raise ConflictError(f"a database named '{name}' already exists")
    db = MiniAppDatabase(
        tenant_id=principal.tenant_id, owner_id=principal.user_id,
        name=name, description=description or "", entity_schema=entity_schema,
    )
    session.add(db)
    session.commit()
    session.refresh(db)
    return db


def update_database(
    session: Session, db_id: uuid.UUID, *,
    name: str | None, description: str | None, entity_schema: dict[str, Any] | None,
) -> MiniAppDatabase:
    db = get_database(session, db_id)
    if entity_schema is not None:
        validate_entity_schema(entity_schema)
        db.entity_schema = entity_schema
    if name is not None and name != db.name:
        if _name_taken(session, db.tenant_id, name):
            raise ConflictError(f"a database named '{name}' already exists")
        db.name = name
    if description is not None:
        db.description = description
    session.commit()
    session.refresh(db)
    return db


def delete_database(session: Session, db_id: uuid.UUID) -> None:
    db = get_database(session, db_id)
    session.delete(db)  # referencing apps' database_id -> NULL via FK ON DELETE
    session.commit()


def list_database_rows(session: Session, db_id: uuid.UUID) -> list[dict[str, Any]]:
    get_database(session, db_id)  # 404 if missing
    stmt = (
        select(MiniAppRow)
        .join(MiniApp, MiniApp.id == MiniAppRow.app_id)
        .where(MiniApp.database_id == db_id)
        .order_by(MiniAppRow.created_at.desc())
    )
    rows = session.execute(stmt).scalars()
    return [
        {
            "row_id": str(r.id), "app_id": str(r.app_id), "data": r.data,
            "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


def _name_taken(session: Session, tenant_id: uuid.UUID, name: str) -> bool:
    stmt = select(MiniAppDatabase.id).where(
        MiniAppDatabase.tenant_id == tenant_id, MiniAppDatabase.name == name
    )
    return session.execute(stmt).first() is not None


def serialize_database(db: MiniAppDatabase) -> dict[str, Any]:
    return {
        "id": str(db.id), "name": db.name, "description": db.description,
        "entity_schema": db.entity_schema, "owner_id": str(db.owner_id),
        "created_at": db.created_at.isoformat(), "updated_at": db.updated_at.isoformat(),
    }
