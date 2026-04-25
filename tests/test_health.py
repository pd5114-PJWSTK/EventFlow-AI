from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_skips_externals_by_default() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "skipped"
    assert payload["checks"]["redis"] == "skipped"
