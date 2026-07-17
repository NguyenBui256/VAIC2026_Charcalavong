"""AC10 — `/ready` DB-readiness endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_ready_returns_200_when_db_reachable() -> None:
    """With Postgres up, /ready returns 200 + {"status": "ready"}."""
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_health_still_returns_ok() -> None:
    """Story 1.1 /health regression — DB-free liveness still works."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
