from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

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
        json={"name": f"Phase7 CP03 Client {suffix}", "priority": "medium"},
    )
    location = api_client.post(
        "/api/locations",
        json={
            "name": f"Phase7 CP03 Venue {suffix}",
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
            "event_name": f"Phase7 CP03 Event {suffix}",
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

    start_at = datetime(2026, 2, 1, 8, 0, 0) + timedelta(minutes=20 * day_offset)
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


def _prepare_active_duration_model(api_client: TestClient) -> str:
    _seed_training_event(
        api_client,
        suffix="TrainA",
        attendee_count=80,
        duration_minutes=130,
        day_offset=32,
    )
    _seed_training_event(
        api_client,
        suffix="TrainB",
        attendee_count=220,
        duration_minutes=210,
        day_offset=33,
    )
    _seed_training_event(
        api_client,
        suffix="TrainC",
        attendee_count=140,
        duration_minutes=170,
        day_offset=34,
    )

    train = api_client.post(
        "/api/ml/models/train-baseline",
        json={"prediction_type": "duration_estimate"},
    )
    assert train.status_code == 200
    return train.json()["model"]["model_id"]


def test_phase7_cp03_generates_prediction_and_persists_it(
    api_client: TestClient,
) -> None:
    model_id = _prepare_active_duration_model(api_client)
    event_id = _seed_training_event(
        api_client,
        suffix="Infer1",
        attendee_count=160,
        duration_minutes=180,
        day_offset=35,
    )

    prediction_response = api_client.post(
        "/api/ml/predictions",
        json={
            "event_id": event_id,
            "prediction_type": "duration_estimate",
            "model_id": model_id,
        },
    )
    assert prediction_response.status_code == 200
    payload = prediction_response.json()
    prediction = payload["prediction"]
    assert prediction["event_id"] == event_id
    assert prediction["model_id"] == model_id
    assert prediction["prediction_type"] == "duration_estimate"
    assert Decimal(prediction["predicted_value"]) >= Decimal("0")
    assert Decimal(prediction["confidence_score"]) > Decimal("0")

    listed = api_client.get(
        f"/api/ml/predictions?event_id={event_id}&prediction_type=duration_estimate"
    )
    assert listed.status_code == 200
    listed_payload = listed.json()
    assert listed_payload["total"] >= 1
    assert any(
        item["prediction_id"] == prediction["prediction_id"]
        for item in listed_payload["items"]
    )


def test_phase7_cp03_evaluates_prediction_with_manual_ground_truth(
    api_client: TestClient,
) -> None:
    _prepare_active_duration_model(api_client)
    event_id = _seed_training_event(
        api_client,
        suffix="EvalManual",
        attendee_count=110,
        duration_minutes=150,
        day_offset=36,
    )

    prediction_response = api_client.post(
        "/api/ml/predictions",
        json={"event_id": event_id, "prediction_type": "duration_estimate"},
    )
    assert prediction_response.status_code == 200
    prediction = prediction_response.json()["prediction"]
    prediction_id = prediction["prediction_id"]

    evaluate = api_client.post(
        f"/api/ml/predictions/{prediction_id}/evaluate",
        json={"actual_numeric_value": "155.0", "notes": "manual entry"},
    )
    assert evaluate.status_code == 200
    outcome = evaluate.json()["outcome"]
    assert outcome["prediction_id"] == prediction_id
    assert Decimal(outcome["actual_numeric_value"]) == Decimal("155.0")
    assert Decimal(outcome["error_value"]) >= Decimal("0")
    assert outcome["notes"] == "manual entry"


def test_phase7_cp03_evaluates_prediction_with_auto_runtime_ground_truth(
    api_client: TestClient,
) -> None:
    _prepare_active_duration_model(api_client)
    event_id = _seed_training_event(
        api_client,
        suffix="EvalAuto",
        attendee_count=95,
        duration_minutes=165,
        day_offset=37,
    )

    prediction_response = api_client.post(
        "/api/ml/predictions",
        json={"event_id": event_id, "prediction_type": "duration_estimate"},
    )
    assert prediction_response.status_code == 200
    prediction_id = prediction_response.json()["prediction"]["prediction_id"]

    evaluate = api_client.post(
        f"/api/ml/predictions/{prediction_id}/evaluate",
        json={"auto_resolve_actual": True},
    )
    assert evaluate.status_code == 200
    outcome = evaluate.json()["outcome"]
    assert Decimal(outcome["actual_numeric_value"]) == Decimal("165.0000")
    assert Decimal(outcome["error_value"]) >= Decimal("0")
    assert outcome["notes"] == "Auto-resolved from ops.actual_timings."
