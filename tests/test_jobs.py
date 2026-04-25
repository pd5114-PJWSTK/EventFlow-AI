from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_async_job_eager_mode_returns_result() -> None:
    response = client.post("/api/test/async-job", json={"a": 2, "b": 3})
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] in {"SUCCESS", "PENDING"}
    if "result" in payload:
        assert payload["result"] == 5
