from fastapi.testclient import TestClient


def test_phase9_ops_monitoring_reports_core_dependencies(api_client: TestClient) -> None:
    response = api_client.get("/api/ops/monitoring")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["redis"] == "skipped"
    assert payload["checks"]["celery"] == "eager"
    assert payload["celery_workers"] == ["eager-local"]
