"""Alembic env — uses VAIC's settings + Base metadata; sync engine.

The migration URL is taken from `VAIC_DATABASE_ADMIN_URL` (defaults to
`VAIC_DATABASE_URL`) — the migration role is BYPASSRLS-capable so DDL can
create RLS policies without themselves being subject to policies.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ensure `app.*` resolves regardless of where alembic is invoked from.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import Base  # noqa: E402  -- sys.path tweak above
from app.core.settings import get_settings  # noqa: E402

# Import every module whose models contribute to Base.metadata so
# `alembic revision --autogenerate` can see them.
from app.modules.tenant import models as _tenant_models  # noqa: E402, F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the admin URL from VAIC settings, unless explicitly overridden.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option(
        "sqlalchemy.url", get_settings().database_admin_url
    )

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline mode — emit SQL to stdout without a live connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online mode — run against a real DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
