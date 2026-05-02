from fastapi.testclient import TestClient


def test_health_ok(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_skips_externals_by_default(api_client: TestClient) -> None:
    response = api_client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "skipped"
    assert payload["checks"]["redis"] == "skipped"

