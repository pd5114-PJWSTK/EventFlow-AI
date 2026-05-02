from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import future_window


def _seed_hardening_dataset(api_client: TestClient, *, total_samples: int) -> list[str]:
    clients: list[str] = []
    for idx in range(3):
        client = api_client.post(
            "/api/clients",
            json={
                "name": f"Phase7 CP06 Client {idx}",
                "priority": ["low", "medium", "high"][idx],
            },
        )
        assert client.status_code == 201
        clients.append(client.json()["client_id"])

    locations: list[str] = []
    location_configs = [
        ("Warsaw", 4, 2, 2),
        ("Gdansk", 6, 3, 3),
        ("Poznan", 8, 4, 4),
    ]
    for idx, config in enumerate(location_configs):
        location = api_client.post(
            "/api/locations",
            json={
                "name": f"Phase7 CP06 Venue {idx}",
                "city": config[0],
                "setup_complexity_score": config[1],
                "access_difficulty": config[2],
                "parking_difficulty": config[3],
            },
        )
        assert location.status_code == 201
        locations.append(location.json()["location_id"])

    equipment_type = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": "Phase7 CP06 Rack"},
    )
    assert equipment_type.status_code == 201
    equipment_type_id = equipment_type.json()["equipment_type_id"]

    seeded_event_ids: list[str] = []
    for idx in range(total_samples):
        attendee_count = 70 + (idx * 9)
        person_qty = 1 + (idx % 4)
        equipment_qty = idx % 4
        vehicle_qty = idx % 2
        requires_transport = idx % 2 == 0
        requires_setup = True
        requires_teardown = idx % 3 != 0

        planned_start, planned_end = future_window(hours=4 + (idx % 3), days=120 + idx)
        event = api_client.post(
            "/api/events",
            json={
                "client_id": clients[idx % len(clients)],
                "location_id": locations[idx % len(locations)],
                "event_name": f"Phase7 CP06 Hardening Event {idx}",
                "event_type": "conference",
                "event_subtype": "touring",
                "attendee_count": attendee_count,
                "planned_start": planned_start,
                "planned_end": planned_end,
                "priority": ["low", "medium", "high", "critical"][idx % 4],
                "requires_transport": requires_transport,
                "requires_setup": requires_setup,
                "requires_teardown": requires_teardown,
            },
        )
        assert event.status_code == 201
        event_id = event.json()["event_id"]
        seeded_event_ids.append(event_id)

        requirement_person = api_client.post(
            f"/api/events/{event_id}/requirements",
            json={
                "requirement_type": "person_role",
                "role_required": "coordinator",
                "quantity": str(person_qty),
            },
        )
        assert requirement_person.status_code == 201

        if equipment_qty > 0:
            requirement_equipment = api_client.post(
                f"/api/events/{event_id}/requirements",
                json={
                    "requirement_type": "equipment_type",
                    "equipment_type_id": equipment_type_id,
                    "quantity": str(equipment_qty),
                },
            )
            assert requirement_equipment.status_code == 201

        if vehicle_qty > 0:
            requirement_vehicle = api_client.post(
                f"/api/events/{event_id}/requirements",
                json={
                    "requirement_type": "vehicle_type",
                    "vehicle_type_required": "van",
                    "quantity": str(vehicle_qty),
                },
            )
            assert requirement_vehicle.status_code == 201

        features = api_client.post(
            "/api/ml/features/generate",
            json={"event_id": event_id, "include_resource_features": False},
        )
        assert features.status_code == 200

        duration_minutes = int(
            75
            + attendee_count * 0.23
            + (idx % 3 + 4) * 10
            + (idx % 3 + 2) * 6
            + (idx % 3 + 2) * 3
            + person_qty * 13
            + equipment_qty * 10
            + vehicle_qty * 14
            + (30 if requires_transport else 0)
            + (35 if requires_setup else 0)
            + (18 if requires_teardown else 0)
        )
        duration_minutes = max(duration_minutes, 45)
        start_at = datetime(2026, 5, 1, 7, 0, 0) + timedelta(hours=idx * 2)
        complete_at = start_at + timedelta(minutes=duration_minutes)
        start = api_client.post(
            f"/api/runtime/events/{event_id}/start",
            json={"started_at": start_at.isoformat(), "phase_name": "event_runtime"},
        )
        complete = api_client.post(
            f"/api/runtime/events/{event_id}/complete",
            json={"completed_at": complete_at.isoformat(), "phase_name": "event_runtime"},
        )
        assert start.status_code == 200
        assert complete.status_code == 200

    return seeded_event_ids


def test_phase7_cp06_hardening_requires_60_real_samples(api_client: TestClient) -> None:
    _seed_hardening_dataset(api_client, total_samples=30)

    response = api_client.post("/api/ml/models/harden-duration", json={})
    assert response.status_code == 400
    assert "Insufficient real samples for hardening" in response.json()["detail"]


def test_phase7_cp06_hardening_uses_60_real_samples_and_tunes_best_model(
    api_client: TestClient,
) -> None:
    event_ids = _seed_hardening_dataset(api_client, total_samples=60)

    response = api_client.post(
        "/api/ml/models/harden-duration",
        json={
            "model_name": "event_duration_hardened",
            "activate_model": True,
            "required_real_samples": 60,
            "train_samples": 50,
            "test_samples": 10,
            "random_seed": 42,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["backend"] == "sklearn_hardened_duration_model"
    assert payload["trained_samples"] == 60
    assert payload["real_samples_used"] == 60
    assert payload["train_samples"] == 50
    assert payload["test_samples"] == 10
    assert payload["selected_algorithm"] in {
        "linear_regression",
        "ridge_regression",
        "random_forest",
        "gradient_boosting",
    }
    assert payload["validation_summary"]["is_valid"] is True
    assert payload["validation_summary"]["issues"] == []

    metrics = payload["model"]["metrics"]
    assert metrics["dataset"]["real_samples"] == 60
    assert metrics["dataset"]["train_samples"] == 50
    assert metrics["dataset"]["test_samples"] == 10
    assert metrics["dataset_validation"]["is_valid"] is True
    assert metrics["model_selection"]["selected_algorithm"] == payload["selected_algorithm"]
    tuning = metrics["hyperparameter_tuning"]
    assert tuning["algorithm"] == payload["selected_algorithm"]
    assert len(tuning["trials"]) >= 1
    assert "winning_params" in tuning

    predict = api_client.post(
        "/api/ml/predictions",
        json={
            "event_id": event_ids[-1],
            "prediction_type": "duration_estimate",
            "model_id": payload["model"]["model_id"],
        },
    )
    assert predict.status_code == 200
    prediction = predict.json()["prediction"]
    assert Decimal(prediction["predicted_value"]) > Decimal("0")
