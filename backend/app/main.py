"""VAIC FastAPI application entrypoint.

Story 1.1: skeleton only — exposes `GET /health` for liveness checks.
Story 1.2: adds `GET /ready` for DB-readiness checks (DB-free `/health`
preserved per AR-1 anti-pattern #1).
Story 1.3: adds AuthMiddleware + tenant module routes (login, refresh, me).
Story 1.4: registers error envelope exception handlers.
Story 3.2: wires an arq pool onto `app.state` (lifespan) so
`POST /workflows/{id}/runs` can enqueue `run_workflow` (AD-10).
Domain routes for other modules arrive in Stories 1.5–1.12 and Epics 2–7.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.arq_pool import close_arq_pool, init_arq_pool
from app.core.auth import AuthMiddleware
from app.core.db import SessionLocal
from app.core.errors import register_error_handlers
from app.core.miniapp_cors import MiniAppNullOriginCORSMiddleware
from app.core.settings import get_settings
from app.modules.agent_builder.kb_routes import router as kb_documents_router
from app.modules.agent_builder.routes import router as agents_router
from app.modules.audit.routes import router as audit_router
from app.modules.mini_app.routes import mini_app_rows_router, mini_apps_router
from app.modules.orchestrator.routes import router as workflows_router
from app.modules.tenant.routes import departments_router
from app.modules.tenant.routes import router as tenant_router


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Story 3.2: create the arq pool at startup, close it at shutdown.

    Non-fatal if Redis is unreachable (see `app/core/arq_pool.py`) — other
    modules' tests boot the app via `TestClient` without needing Redis.
    """
    await init_arq_pool(app)
    yield
    await close_arq_pool(app)


app = FastAPI(
    title="VAIC",
    description="Vietnamese banking AI-agent platform",
    version="0.1.0",
    lifespan=_lifespan,
)

# Story 1.3 — auth + tenant context middleware.
app.add_middleware(AuthMiddleware)

# CORS — added AFTER AuthMiddleware so it wraps outermost (Starlette runs the
# last-added middleware first). This lets browser preflight `OPTIONS` requests
# resolve before AuthMiddleware, and allows the Vite dev server (or a separate
# production origin) to call the API directly via `VITE_API_BASE`.
_cors_origins = [
    o.strip() for o in get_settings().cors_origins.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Final review fix — the sandboxed Mini-App iframe (`sandbox="allow-scripts
# allow-forms"`, no `allow-same-origin`) has an OPAQUE origin, so its fetches
# to `/apps/{app_id}/rows*` send `Origin: null`, which the fixed allow-list
# above never matches. Added LAST so it wraps OUTERMOST (runs first), ahead
# of AuthMiddleware and the global CORSMiddleware — see
# `app/core/miniapp_cors.py` for the full rationale and scoping. It only
# touches `Origin: null` requests to mini-app row routes; everything else
# passes through unchanged.
app.add_middleware(MiniAppNullOriginCORSMiddleware)

# Story 1.3 — tenant module routes (login, refresh, me, users).
app.include_router(tenant_router)

# Story 2.8 (carried item #2) — tenant-scoped Department listing.
app.include_router(departments_router)

# Story 2.1 — Agent Builder CRUD routes.
app.include_router(agents_router)

# Sub-project A (Task 4) — tenant-wide KB store + owner/grants ACL routes.
app.include_router(kb_documents_router)

# Story 3.1 — Orchestrator Workflow CRUD routes.
app.include_router(workflows_router)

# Epic 6 (FR-22) — Trace Dashboard read API (/audit).
app.include_router(audit_router)

# Epic 4 (Stories 4-2/4-4) — Mini-App catalog + generic row CRUD routes.
app.include_router(mini_apps_router)
app.include_router(mini_app_rows_router)

# Story 4-5 — serve built Mini-App bundles (sandbox runtime plane). Each
# `build_mini_app` job writes `{bundle_root}/{app_id}/{index.html,bundle.js}`;
# `html=True` serves `index.html` for a directory request. The dir is created
# here (not just by the worker) so a fresh checkout with zero builds yet still
# boots — `StaticFiles` raises at mount time if `directory` doesn't exist.
_mini_app_bundle_root = Path(get_settings().mini_app_bundle_root)
_mini_app_bundle_root.mkdir(parents=True, exist_ok=True)
app.mount(
    "/mini-app-runtime",
    StaticFiles(directory=str(_mini_app_bundle_root), html=True),
    name="mini-app-runtime",
)

# Story 1.4 — wire the error envelope exception handlers.
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
