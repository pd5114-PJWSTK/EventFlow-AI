from fastapi.testclient import TestClient


def test_async_job_eager_mode_returns_result(api_client: TestClient) -> None:
    response = api_client.post("/api/test/async-job", json={"a": 2, "b": 3})
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] in {"SUCCESS", "PENDING"}
    if "result" in payload:
        assert payload["result"] == 5

