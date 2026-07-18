"""Database engine, session factory, declarative base, FastAPI dependency.

Sync SQLAlchemy 2.x per AR-13. Two engines are exposed:
- `engine` — used by the FastAPI app at runtime; subject to RLS policies.
- `admin_engine` — used by Alembic and test fixtures; runs with a role that
  has `BYPASSRLS` so it can seed data across tenants.

Session usage:
    with SessionLocal() as s:
        set_tenant_session_var(s, tenant_id)
        s.execute(select(User)).scalars().all()
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import get_settings

_settings = get_settings()


def _build_engine(url: str, **kwargs: Any) -> Engine:
    """Engine factory — `future=True` is implicit on SQLAlchemy 2.x."""
    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        **kwargs,
    )


# Runtime engine — RLS applies.
engine: Engine = _build_engine(_settings.database_url)
# Admin/migration engine — BYPASSRLS capable. Tests use this for fixture setup.
admin_engine: Engine = _build_engine(_settings.database_admin_url)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, future=True
)
AdminSessionLocal: sessionmaker[Session] = sessionmaker(
    bind=admin_engine, autoflush=False, expire_on_commit=False, future=True
)


class Base(DeclarativeBase):
    """Shared declarative base. All models subclass this."""

    pass


def get_session() -> Iterator[Session]:
    """FastAPI dependency — yields a session, closes on exit."""
    with SessionLocal() as session:
        yield session


def get_admin_session() -> Iterator[Session]:
    """FastAPI dependency for paths that legitimately need BYPASSRLS.

    Rarely used — migrations, bootstrap. Do NOT reach for this from domain
    code without explicit justification; AD-2 prohibits app-level bypass.
    """
    with AdminSessionLocal() as session:
        yield session
