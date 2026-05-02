from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.celery_app import celery_app
from app.config import get_settings
from tests.helpers import future_window


def _seed_training_event(
    api_client: TestClient,
    *,
    suffix: str,
    attendee_count: int,
    duration_minutes: int,
    day_offset: int,
) -> str:
    client = api_client.post(
        "/api/clients",
        json={"name": f"Phase7 CP04 Client {suffix}", "priority": "medium"},
    )
    location = api_client.post(
        "/api/locations",
        json={
            "name": f"Phase7 CP04 Venue {suffix}",
            "city": "Warsaw",
            "setup_complexity_score": 5,
            "access_difficulty": 3,
            "parking_difficulty": 2,
        },
    )
    assert client.status_code == 201
    assert location.status_code == 201

    planned_start, planned_end = future_window(hours=4, days=day_offset)
    event = api_client.post(
        "/api/events",
        json={
            "client_id": client.json()["client_id"],
            "location_id": location.json()["location_id"],
            "event_name": f"Phase7 CP04 Event {suffix}",
            "event_type": "conference",
            "attendee_count": attendee_count,
            "planned_start": planned_start,
            "planned_end": planned_end,
            "priority": "medium",
            "requires_transport": True,
            "requires_setup": True,
            "requires_teardown": True,
        },
    )
    assert event.status_code == 201
    event_id = event.json()["event_id"]

    requirement = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": "1",
        },
    )
    assert requirement.status_code == 201

    features = api_client.post(
        "/api/ml/features/generate",
        json={"event_id": event_id, "include_resource_features": False},
    )
    assert features.status_code == 200

    start_at = datetime(2026, 3, 1, 8, 0, 0) + timedelta(minutes=20 * day_offset)
    complete_at = start_at + timedelta(minutes=duration_minutes)
    start = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={"started_at": start_at.isoformat(), "phase_name": "event_runtime"},
    )
    assert start.status_code == 200
    complete = api_client.post(
        f"/api/runtime/events/{event_id}/complete",
        json={"completed_at": complete_at.isoformat(), "phase_name": "event_runtime"},
    )
    assert complete.status_code == 200
    return event_id


def _seed_training_data(api_client: TestClient) -> None:
    _seed_training_event(
        api_client,
        suffix="A",
        attendee_count=90,
        duration_minutes=140,
        day_offset=38,
    )
    _seed_training_event(
        api_client,
        suffix="B",
        attendee_count=200,
        duration_minutes=220,
        day_offset=39,
    )
    _seed_training_event(
        api_client,
        suffix="C",
        attendee_count=130,
        duration_minutes=175,
        day_offset=40,
    )


def test_phase7_cp04_retrain_endpoint_activates_candidate_without_baseline(
    api_client: TestClient,
) -> None:
    _seed_training_data(api_client)

    response = api_client.post("/api/ml/models/retrain-duration", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["activated"] is True
    assert payload["decision_reason"] == "activated_no_baseline"
    assert payload["model"]["status"] == "active"
    assert payload["trained_samples"] >= 3


def test_phase7_cp04_retrain_endpoint_respects_activation_thresholds(
    api_client: TestClient,
) -> None:
    _seed_training_data(api_client)
    baseline = api_client.post(
        "/api/ml/models/train-baseline",
        json={"prediction_type": "duration_estimate", "activate_model": True},
    )
    assert baseline.status_code == 200
    baseline_model_id = baseline.json()["model"]["model_id"]

    retrain = api_client.post(
        "/api/ml/models/retrain-duration",
        json={
            "min_samples_required": 1,
            "min_r2_improvement": 2.0,
            "max_mae_ratio": 1.0,
        },
    )
    assert retrain.status_code == 200
    payload = retrain.json()
    assert payload["activated"] is False
    assert payload["decision_reason"] == "r2_below_threshold"
    assert payload["model"]["status"] == "deprecated"
    assert payload["previous_active_model_id"] == baseline_model_id

    listed = api_client.get("/api/ml/models?prediction_type=duration_estimate")
    assert listed.status_code == 200
    active_models = [item for item in listed.json()["items"] if item["status"] == "active"]
    assert any(item["model_id"] == baseline_model_id for item in active_models)


def test_phase7_cp04_celery_schedule_contains_retraining_task() -> None:
    settings = get_settings()
    assert "app.workers.ml_tasks" in tuple(celery_app.conf.imports)
    if settings.ml_retrain_enabled:
        beat_schedule = getattr(celery_app.conf, "beat_schedule", {}) or {}
        assert "ml-retrain-duration-model" in beat_schedule
        schedule = beat_schedule["ml-retrain-duration-model"]["schedule"]
        assert int(schedule.total_seconds()) == settings.ml_retrain_schedule_minutes * 60
