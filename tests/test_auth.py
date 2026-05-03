from fastapi.testclient import TestClient


def test_login_success_and_refresh(api_client: TestClient) -> None:
    login_response = api_client.post(
        "/auth/login",
        json={"username": "test-admin", "password": "StrongPass!234"},
    )
    assert login_response.status_code == 200

    tokens = login_response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    refresh_response = api_client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert refresh_response.status_code == 200
    refreshed_tokens = refresh_response.json()
    assert "access_token" in refreshed_tokens


def test_login_invalid_credentials(api_client: TestClient) -> None:
    response = api_client.post(
        "/auth/login",
        json={"username": "test-admin", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_lockout_after_repeated_failures(api_client: TestClient) -> None:
    for _ in range(5):
        response = api_client.post(
            "/auth/login",
            json={"username": "test-admin", "password": "wrong-password"},
        )
        assert response.status_code == 401

    blocked = api_client.post(
        "/auth/login",
        json={"username": "test-admin", "password": "wrong-password"},
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") is not None


def test_refresh_lockout_after_repeated_failures(api_client: TestClient) -> None:
    for _ in range(10):
        response = api_client.post(
            "/auth/refresh",
            headers={"Authorization": "Bearer invalid-refresh-token"},
        )
        assert response.status_code == 401

    blocked = api_client.post(
        "/auth/refresh",
        headers={"Authorization": "Bearer invalid-refresh-token"},
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") is not None

