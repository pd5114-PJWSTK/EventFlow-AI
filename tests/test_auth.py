from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_login_success_and_refresh() -> None:
    login_response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert login_response.status_code == 200

    tokens = login_response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    refresh_response = client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert refresh_response.status_code == 200
    refreshed_tokens = refresh_response.json()
    assert "access_token" in refreshed_tokens


def test_login_invalid_credentials() -> None:
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401
