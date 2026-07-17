"""VAIC FastAPI application entrypoint.

Story 1.1: skeleton only -- exposes `GET /health` for liveness checks.
Story 1.2: adds `GET /ready` for DB-readiness checks (DB-free `/health`
preserved per AR-1 anti-pattern #1).
Story 1.4: registers error envelope exception handlers.
Domain routes, full middleware, and auth arrive in Stories 1.3-1.12.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.errors import register_error_handlers

app = FastAPI(
    title="VAIC",
    description="Vietnamese banking AI-agent platform",
    version="0.1.0",
)

# Story 1.4: wire the error envelope exception handlers.
register_error_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Intentionally DB-free; do NOT add DB calls here."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness probe — DB reachability check.

    Returns 200 when the DB accepts a trivial round-trip; 503 otherwise.
    Container orchestrators should use this for traffic-readiness gating
    and `/health` (DB-free) for liveness — that way Postgres restarts don't
    get the backend killed by a liveness probe.
    """
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — surface any DB failure as 503
        raise HTTPException(status_code=503, detail="database unreachable") from exc
    return {"status": "ready"}
