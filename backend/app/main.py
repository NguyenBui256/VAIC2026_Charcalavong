"""VAIC FastAPI application entrypoint.

Story 1.1: skeleton only — exposes `GET /health` for liveness checks.
Domain routes, DB wiring, and middleware arrive in Stories 1.2–1.12.
"""

from fastapi import FastAPI

app = FastAPI(
    title="VAIC",
    description="Vietnamese banking AI-agent platform",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Intentionally DB-free; do NOT add DB calls here.

    Story 1.2 may add `GET /ready` for DB-readiness if needed.
    """
    return {"status": "ok"}
