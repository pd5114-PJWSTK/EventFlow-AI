from __future__ import annotations

from fastapi.testclient import TestClient


def test_phase8_frontend_cp03_admin_can_list_users(api_client: TestClient) -> None:
    response = api_client.get("/admin/users")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["username"]
    assert "password" not in payload["items"][0]


def test_phase8_frontend_cp03_non_admin_cannot_list_users(api_client: TestClient) -> None:
    created = api_client.post(
        "/admin/users",
        json={
            "username": "cp03-manager",
            "password": "StrongManager!234",
            "roles": ["manager"],
            "is_superadmin": False,
        },
    )
    assert created.status_code == 201
    login = api_client.post(
        "/auth/login",
        json={"username": "cp03-manager", "password": "StrongManager!234"},
    )
    assert login.status_code == 200

    response = api_client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 403
