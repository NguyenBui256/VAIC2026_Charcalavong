"""arq pool wiring — FastAPI `app.state` lifecycle (Story 3.2, T4.3).

Epic 1's `app/core/jobs.py` built the enqueue/worker-decorator machinery
(`enqueue_job_with_context`, `tenant_aware_job`) but never wired an actual
`ArqRedis` connection pool into the FastAPI app — nothing set
`app.state.arq_pool`. This module adds that minimal plumbing so
`POST /workflows/{id}/runs` can enqueue `run_workflow`.

Pool creation is attempted once at app startup (`init_arq_pool`, wired via
`main.py`'s `lifespan`). If Redis is unreachable at boot, the failure is
logged and `app.state.arq_pool` stays `None` — this deliberately avoids a
hard Redis dependency on every `TestClient`-based test across the whole
suite (most modules never call `POST /runs`). `get_arq_pool` raises a
clear `RuntimeError` if a route depends on the pool before it exists,
which surfaces as a debuggable 500 via the app's unhandled-exception
handler rather than a silent no-op.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Request

from app.core.settings import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

__all__ = ["init_arq_pool", "close_arq_pool", "get_arq_pool"]


async def init_arq_pool(app: FastAPI) -> None:
    """Create the arq pool and stash it on `app.state.arq_pool`.

    Non-fatal on failure — logs and leaves `app.state.arq_pool = None` so
    app boot never hard-fails for modules that don't need background jobs.
    """
    try:
        settings = get_settings()
        app.state.arq_pool = await create_pool(
            RedisSettings.from_dsn(settings.redis_url)
        )
    except Exception:  # noqa: BLE001 — degrade gracefully, log for ops visibility
        logger.exception("init_arq_pool: failed to connect to Redis at startup")
        app.state.arq_pool = None


async def close_arq_pool(app: FastAPI) -> None:
    """Close the pool on shutdown, if one was created."""
    pool: ArqRedis | None = getattr(app.state, "arq_pool", None)
    if pool is not None:
        await pool.aclose()


def get_arq_pool(request: Request) -> ArqRedis:
    """FastAPI dependency — the shared `ArqRedis` pool for enqueueing jobs."""
    pool: ArqRedis | None = getattr(request.app.state, "arq_pool", None)
    if pool is None:
        raise RuntimeError(
            "arq pool not initialized (app.state.arq_pool is None) — "
            "Redis was unreachable at app startup."
        )
    return pool
