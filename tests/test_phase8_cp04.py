from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.schemas.ml_models import TrainBaselineModelRequest


def test_phase8_cp04_auth_me_logout_flow(api_client: TestClient) -> None:
    login = api_client.post(
        "/auth/login",
        json={"username": "test-admin", "password": "StrongPass!234"},
    )
    assert login.status_code == 200
    tokens = login.json()

    me = api_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    me_payload = me.json()
    assert me_payload["username"] == "test-admin"
    assert "admin" in me_payload["roles"]

    logout = api_client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert logout.status_code == 200

    refresh_after_logout = api_client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert refresh_after_logout.status_code == 401


def test_phase8_cp04_protected_api_requires_token(api_client: TestClient) -> None:
    saved = api_client.headers.pop("Authorization", None)
    try:
        response = api_client.get("/api/clients")
    finally:
        if saved is not None:
            api_client.headers["Authorization"] = saved
    assert response.status_code == 401


def test_phase8_cp04_admin_endpoint_forbidden_for_non_admin(api_client: TestClient) -> None:
    create_user_response = api_client.post(
        "/admin/users",
        json={
            "username": "manager-user",
            "password": "StrongManager!234",
            "roles": ["manager"],
            "is_superadmin": False,
        },
    )
    assert create_user_response.status_code == 201

    login = api_client.post(
        "/auth/login",
        json={"username": "manager-user", "password": "StrongManager!234"},
    )
    assert login.status_code == 200
    manager_access = login.json()["access_token"]

    forbidden = api_client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {manager_access}"},
        json={
            "username": "should-fail",
            "password": "StrongPass!234",
            "roles": ["manager"],
        },
    )
    assert forbidden.status_code == 403


def test_phase8_cp04_ws_requires_auth_and_accepts_valid_token(api_client: TestClient) -> None:
    saved = api_client.headers.pop("Authorization", None)
    try:
        with pytest.raises(WebSocketDisconnect):
            with api_client.websocket_connect("/api/runtime/ws/events/unknown/notifications"):
                pass
    finally:
        if saved is not None:
            api_client.headers["Authorization"] = saved

    with api_client.websocket_connect(
        "/api/runtime/ws/events/unknown/notifications",
        headers={"Authorization": api_client.headers["Authorization"]},
    ):
        pass


def test_phase8_cp04_model_name_path_traversal_blocked() -> None:
    with pytest.raises(ValidationError):
        TrainBaselineModelRequest(model_name="..\\evil")
    with pytest.raises(ValidationError):
        TrainBaselineModelRequest(model_name="../evil")
    valid = TrainBaselineModelRequest(model_name="event_duration_baseline_cp04")
    assert valid.model_name == "event_duration_baseline_cp04"


def test_phase8_cp04_settings_fail_fast_outside_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "change-me-in-production")
    monkeypatch.setenv("DEMO_ADMIN_ENABLED", "false")
    with pytest.raises(ValidationError):
        Settings()
