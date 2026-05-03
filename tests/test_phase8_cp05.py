from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.schemas.ml_models import TrainBaselineModelRequest
from app.services.ml_training_service import ModelTrainingError, _resolve_model_artifact_dir


def _create_user_and_login(
    api_client: TestClient,
    *,
    username: str,
    password: str,
    roles: list[str],
) -> str:
    response = api_client.post(
        "/admin/users",
        json={
            "username": username,
            "password": password,
            "roles": roles,
            "is_superadmin": False,
        },
    )
    assert response.status_code == 201
    login = api_client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


@pytest.mark.parametrize(
    ("method", "path", "json_payload"),
    [
        ("post", "/api/clients", {"name": "NoAuth Client"}),
        ("patch", "/api/clients/unknown", {"name": "NoAuth Client v2"}),
        ("delete", "/api/clients/unknown", None),
        ("post", "/api/planner/generate-plan", {"event_id": "unknown-event"}),
        ("post", "/api/runtime/events/unknown/start", {"phase_name": "event_runtime"}),
        ("post", "/api/ml/models/train-baseline", {"model_name": "event_duration_baseline_cp05"}),
        (
            "post",
            "/api/ai-agents/optimize",
            {"raw_input": "event setup", "planner_snapshot": "", "prefer_langgraph": False},
        ),
    ],
)
def test_phase8_cp05_mutating_endpoints_require_authentication(
    api_client: TestClient,
    method: str,
    path: str,
    json_payload: dict | None,
) -> None:
    saved = api_client.headers.pop("Authorization", None)
    try:
        response = api_client.request(method=method, url=path, json=json_payload)
    finally:
        if saved is not None:
            api_client.headers["Authorization"] = saved
    assert response.status_code == 401


def test_phase8_cp05_role_matrix_forbidden_and_allowed(api_client: TestClient) -> None:
    technician_token = _create_user_and_login(
        api_client,
        username="tech-cp05",
        password="StrongTech!234",
        roles=["technician"],
    )
    coordinator_token = _create_user_and_login(
        api_client,
        username="coord-cp05",
        password="StrongCoord!234",
        roles=["coordinator"],
    )
    manager_token = _create_user_and_login(
        api_client,
        username="manager-cp05",
        password="StrongManager!234",
        roles=["manager"],
    )
    admin_only_token = _create_user_and_login(
        api_client,
        username="adminonly-cp05",
        password="StrongAdmin!234",
        roles=["admin"],
    )

    technician_forbidden = api_client.post(
        "/api/clients",
        headers={"Authorization": f"Bearer {technician_token}"},
        json={"name": "forbidden-tech"},
    )
    assert technician_forbidden.status_code == 403

    coordinator_forbidden_ml = api_client.post(
        "/api/ml/models/train-baseline",
        headers={"Authorization": f"Bearer {coordinator_token}"},
        json={"model_name": "event_duration_baseline_cp05_coordinator"},
    )
    assert coordinator_forbidden_ml.status_code == 403

    admin_only_forbidden = api_client.post(
        "/api/clients",
        headers={"Authorization": f"Bearer {admin_only_token}"},
        json={"name": "forbidden-admin-only"},
    )
    assert admin_only_forbidden.status_code == 403

    manager_allowed = api_client.post(
        "/api/ml/models/train-baseline",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"model_name": "event_duration_baseline_cp05_manager"},
    )
    assert manager_allowed.status_code != 403
    assert manager_allowed.status_code != 401

    technician_runtime_allowed = api_client.post(
        "/api/runtime/events/unknown/start",
        headers={"Authorization": f"Bearer {technician_token}"},
        json={"phase_name": "event_runtime"},
    )
    assert technician_runtime_allowed.status_code != 403
    assert technician_runtime_allowed.status_code != 401


def test_phase8_cp05_websocket_role_enforcement(api_client: TestClient) -> None:
    admin_only_token = _create_user_and_login(
        api_client,
        username="adminonly-ws-cp05",
        password="StrongAdminWs!234",
        roles=["admin"],
    )
    technician_token = _create_user_and_login(
        api_client,
        username="tech-ws-cp05",
        password="StrongTechWs!234",
        roles=["technician"],
    )

    with pytest.raises(WebSocketDisconnect):
        with api_client.websocket_connect(
            "/api/runtime/ws/events/unknown/notifications",
            headers={"Authorization": f"Bearer {admin_only_token}"},
        ):
            pass

    with api_client.websocket_connect(
        "/api/runtime/ws/events/unknown/notifications",
        headers={"Authorization": f"Bearer {technician_token}"},
    ):
        pass


def test_phase8_cp05_path_traversal_absolute_and_unc_rejected() -> None:
    for invalid_name in ("..\\evil", "../evil", "C:\\evil", "/tmp/evil", "\\\\server\\share\\evil"):
        with pytest.raises(ValidationError):
            TrainBaselineModelRequest(model_name=invalid_name)

    with pytest.raises(ModelTrainingError):
        _resolve_model_artifact_dir(
            artifact_dir=Path("C:/repo/models").resolve(),
            model_name="..\\escape",
            model_version="v1",
        )
    with pytest.raises(ModelTrainingError):
        _resolve_model_artifact_dir(
            artifact_dir=Path("C:/repo/models").resolve(),
            model_name="\\\\server\\share\\escape",
            model_version="v1",
        )


def test_phase8_cp05_settings_fail_fast_for_demo_and_test_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "this-is-a-very-strong-secret-key-with-entropy-123")
    monkeypatch.setenv("DEMO_ADMIN_ENABLED", "false")
    monkeypatch.setenv("API_TEST_JOBS_ENABLED", "true")
    with pytest.raises(ValidationError):
        Settings()

    monkeypatch.setenv("API_TEST_JOBS_ENABLED", "false")
    monkeypatch.setenv("API_DOCS_ENABLED", "true")
    with pytest.raises(ValidationError):
        Settings()

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEMO_ADMIN_ENABLED", "true")
    monkeypatch.setenv("DEMO_ADMIN_USERNAME", "")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "")
    with pytest.raises(ValidationError):
        Settings()


def test_phase8_cp05_docs_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "this-is-a-very-strong-secret-key-with-entropy-123")
    monkeypatch.setenv("DEMO_ADMIN_ENABLED", "false")
    monkeypatch.setenv("API_TEST_JOBS_ENABLED", "false")
    monkeypatch.setenv("API_DOCS_ENABLED", "false")

    from app.config import get_settings
    get_settings.cache_clear()

    import app.main as app_main_module

    app_main_module = importlib.reload(app_main_module)
    app_main_module.app.router.on_startup.clear()

    with TestClient(app_main_module.app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
