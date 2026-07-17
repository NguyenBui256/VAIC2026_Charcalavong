"""Integration test for `GET /health` (AC5).

Story 1.1: skeleton liveness probe — DB-free.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200_with_ok_status() -> None:
    """When a client calls GET /health, it returns 200 and the ok envelope."""
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
