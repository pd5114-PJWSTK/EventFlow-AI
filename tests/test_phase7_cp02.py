from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from tests.helpers import future_window


def _seed_training_event(
    api_client: TestClient,
    *,
    suffix: str,
    attendee_count: int,
    duration_minutes: int,
) -> str:
    client = api_client.post(
        "/api/clients",
        json={"name": f"Phase7 CP02 Client {suffix}", "priority": "medium"},
    )
    location = api_client.post(
        "/api/locations",
        json={
            "name": f"Phase7 CP02 Venue {suffix}",
            "city": "Warsaw",
            "setup_complexity_score": 4,
            "access_difficulty": 3,
            "parking_difficulty": 2,
        },
    )
    assert client.status_code == 201
    assert location.status_code == 201

    planned_start, planned_end = future_window(hours=5, days=31)
    event = api_client.post(
        "/api/events",
        json={
            "client_id": client.json()["client_id"],
            "location_id": location.json()["location_id"],
            "event_name": f"Phase7 CP02 Event {suffix}",
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

    start_at = datetime(2026, 1, 10, 8, 0, 0) + timedelta(
        minutes=10 * len(suffix)
    )
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


def test_phase7_cp02_trains_baseline_duration_model_and_registers_it(
    api_client: TestClient,
) -> None:
    _seed_training_event(
        api_client, suffix="A", attendee_count=120, duration_minutes=180
    )
    _seed_training_event(
        api_client, suffix="BB", attendee_count=250, duration_minutes=240
    )
    _seed_training_event(
        api_client, suffix="CCC", attendee_count=60, duration_minutes=140
    )

    response = api_client.post(
        "/api/ml/models/train-baseline",
        json={
            "prediction_type": "duration_estimate",
            "model_name": "event_duration_baseline",
            "activate_model": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["trained_samples"] >= 3
    assert payload["backend"] in {
        "sklearn_linear_regression",
        "heuristic_mean_regressor",
    }
    assert payload["artifact_path"] is not None
    assert payload["artifact_path"].endswith("model.pkl")

    model = payload["model"]
    assert model["model_id"]
    assert model["model_name"] == "event_duration_baseline"
    assert model["prediction_type"] == "duration_estimate"
    assert model["status"] == "active"
    assert model["metrics"]["sample_count"] >= 3
    assert "mae_minutes" in model["metrics"]
    assert "artifact_path" in model["metrics"]

    listed = api_client.get("/api/ml/models?prediction_type=duration_estimate")
    assert listed.status_code == 200
    listed_payload = listed.json()
    assert listed_payload["total"] >= 1
    assert any(
        item["model_id"] == model["model_id"] for item in listed_payload["items"]
    )


def test_phase7_cp02_training_requires_samples(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/ml/models/train-baseline",
        json={"prediction_type": "duration_estimate"},
    )
    assert response.status_code == 400
    assert "No training samples found" in response.json()["detail"]


def test_phase7_cp02_unsupported_prediction_type_returns_400(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/ml/models/train-baseline",
        json={"prediction_type": "delay_risk"},
    )
    assert response.status_code == 400
    assert "Only duration_estimate baseline training is supported" in response.json()[
        "detail"
    ]
