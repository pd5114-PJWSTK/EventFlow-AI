from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import future_window


def _seed_realistic_training_event(
    api_client: TestClient,
    *,
    idx: int,
    attendee_count: int,
    setup_complexity: int,
    access_difficulty: int,
    parking_difficulty: int,
    person_qty: int,
    equipment_qty: int,
    vehicle_qty: int,
    requires_transport: bool,
    requires_setup: bool,
    requires_teardown: bool,
) -> str:
    priorities = ["low", "medium", "high", "critical"]
    priority = priorities[idx % len(priorities)]

    client = api_client.post(
        "/api/clients",
        json={"name": f"Phase7 CP05 Client {idx}", "priority": priority},
    )
    location = api_client.post(
        "/api/locations",
        json={
            "name": f"Phase7 CP05 Venue {idx}",
            "city": "Warsaw" if idx % 2 == 0 else "Gdansk",
            "setup_complexity_score": setup_complexity,
            "access_difficulty": access_difficulty,
            "parking_difficulty": parking_difficulty,
        },
    )
    assert client.status_code == 201
    assert location.status_code == 201

    planned_start, planned_end = future_window(hours=5 + (idx % 4), days=45 + idx)
    event = api_client.post(
        "/api/events",
        json={
            "client_id": client.json()["client_id"],
            "location_id": location.json()["location_id"],
            "event_name": f"Phase7 CP05 Training Event {idx}",
            "event_type": "conference",
            "event_subtype": "touring",
            "attendee_count": attendee_count,
            "planned_start": planned_start,
            "planned_end": planned_end,
            "priority": priority,
            "requires_transport": requires_transport,
            "requires_setup": requires_setup,
            "requires_teardown": requires_teardown,
        },
    )
    assert event.status_code == 201
    event_id = event.json()["event_id"]

    equipment_type = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": f"Phase7 CP05 Rack {idx}"},
    )
    assert equipment_type.status_code == 201

    if person_qty > 0:
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
                "equipment_type_id": equipment_type.json()["equipment_type_id"],
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
        80
        + attendee_count * 0.28
        + setup_complexity * 11
        + access_difficulty * 6
        + parking_difficulty * 4
        + person_qty * 14
        + equipment_qty * 9
        + vehicle_qty * 15
        + (30 if requires_transport else 0)
        + (35 if requires_setup else 0)
        + (18 if requires_teardown else 0)
    )
    duration_minutes = max(duration_minutes, 45)

    start_at = datetime(2026, 4, 1, 8, 0, 0) + timedelta(days=idx, hours=idx % 5)
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
    return event_id


def _seed_inference_event(api_client: TestClient, *, suffix: str) -> str:
    client = api_client.post(
        "/api/clients",
        json={"name": f"Phase7 CP05 Inference Client {suffix}", "priority": "high"},
    )
    location = api_client.post(
        "/api/locations",
        json={
            "name": f"Phase7 CP05 Inference Venue {suffix}",
            "city": "Warsaw",
            "setup_complexity_score": 7,
            "access_difficulty": 4,
            "parking_difficulty": 3,
        },
    )
    assert client.status_code == 201
    assert location.status_code == 201

    planned_start, planned_end = future_window(hours=6, days=90)
    event = api_client.post(
        "/api/events",
        json={
            "client_id": client.json()["client_id"],
            "location_id": location.json()["location_id"],
            "event_name": f"Phase7 CP05 Inference Event {suffix}",
            "event_type": "conference",
            "event_subtype": "festival",
            "attendee_count": 260,
            "planned_start": planned_start,
            "planned_end": planned_end,
            "priority": "high",
            "requires_transport": True,
            "requires_setup": True,
            "requires_teardown": True,
        },
    )
    assert event.status_code == 201
    event_id = event.json()["event_id"]

    equipment_type = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": f"Phase7 CP05 Inference Rack {suffix}"},
    )
    assert equipment_type.status_code == 201

    requirement_person = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": "3",
        },
    )
    requirement_equipment = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "equipment_type",
            "equipment_type_id": equipment_type.json()["equipment_type_id"],
            "quantity": "4",
        },
    )
    requirement_vehicle = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "vehicle_type",
            "vehicle_type_required": "van",
            "quantity": "1",
        },
    )
    assert requirement_person.status_code == 201
    assert requirement_equipment.status_code == 201
    assert requirement_vehicle.status_code == 201

    features = api_client.post(
        "/api/ml/features/generate",
        json={"event_id": event_id, "include_resource_features": False},
    )
    assert features.status_code == 200
    return event_id


def test_phase7_cp05_training_uses_holdout_split_and_algorithm_selection(
    api_client: TestClient,
) -> None:
    configs = [
        (0, 80, 3, 2, 2, 1, 1, 0, True, True, True),
        (1, 120, 4, 3, 2, 2, 1, 1, True, True, True),
        (2, 160, 5, 3, 3, 2, 2, 1, True, True, True),
        (3, 240, 6, 4, 4, 3, 2, 1, True, True, True),
        (4, 300, 7, 5, 4, 3, 3, 1, True, True, True),
        (5, 110, 4, 2, 2, 1, 1, 0, False, True, True),
        (6, 190, 6, 4, 3, 2, 2, 1, True, True, False),
        (7, 260, 8, 5, 4, 3, 3, 1, True, True, True),
        (8, 140, 5, 3, 2, 2, 2, 0, False, True, True),
        (9, 220, 7, 4, 4, 3, 2, 1, True, False, True),
        (10, 360, 9, 5, 5, 4, 4, 2, True, True, True),
        (11, 180, 5, 3, 3, 2, 2, 1, True, True, True),
    ]
    for config in configs:
        _seed_realistic_training_event(
            api_client,
            idx=config[0],
            attendee_count=config[1],
            setup_complexity=config[2],
            access_difficulty=config[3],
            parking_difficulty=config[4],
            person_qty=config[5],
            equipment_qty=config[6],
            vehicle_qty=config[7],
            requires_transport=config[8],
            requires_setup=config[9],
            requires_teardown=config[10],
        )

    train_response = api_client.post(
        "/api/ml/models/train-baseline",
        json={"prediction_type": "duration_estimate", "model_name": "event_duration_baseline"},
    )
    assert train_response.status_code == 200
    payload = train_response.json()
    assert payload["backend"] == "sklearn_multi_algorithm_selector"
    assert payload["trained_samples"] >= 12

    metrics = payload["model"]["metrics"]
    dataset = metrics["dataset"]
    assert dataset["real_samples"] >= 12
    assert dataset["augmented_samples"] > 0
    assert dataset["total_samples"] > dataset["real_samples"]

    selection = metrics["model_selection"]
    assert selection["selected_algorithm"] in {
        "linear_regression",
        "ridge_regression",
        "random_forest",
        "gradient_boosting",
    }
    assert selection["train_samples"] >= 2
    assert selection["test_samples"] >= 2
    assert len(selection["leaderboard"]) >= 4
    assert selection["leaderboard"][0]["algorithm"] == selection["selected_algorithm"]

    sorted_by_mae = sorted(
        item["test_metrics"]["mae_minutes"] for item in selection["leaderboard"]
    )
    leaderboard_mae = [item["test_metrics"]["mae_minutes"] for item in selection["leaderboard"]]
    assert leaderboard_mae == sorted_by_mae


def test_phase7_cp05_inference_works_with_selected_estimator_artifact(
    api_client: TestClient,
) -> None:
    for idx in range(8):
        _seed_realistic_training_event(
            api_client,
            idx=100 + idx,
            attendee_count=100 + (idx * 35),
            setup_complexity=4 + (idx % 5),
            access_difficulty=2 + (idx % 4),
            parking_difficulty=2 + (idx % 3),
            person_qty=1 + (idx % 3),
            equipment_qty=1 + (idx % 4),
            vehicle_qty=idx % 2,
            requires_transport=idx % 2 == 0,
            requires_setup=True,
            requires_teardown=idx % 3 != 0,
        )

    train_response = api_client.post(
        "/api/ml/models/train-baseline",
        json={"prediction_type": "duration_estimate"},
    )
    assert train_response.status_code == 200
    train_payload = train_response.json()
    assert train_payload["backend"] == "sklearn_multi_algorithm_selector"
    model_id = train_payload["model"]["model_id"]

    event_id = _seed_inference_event(api_client, suffix="A")
    prediction_response = api_client.post(
        "/api/ml/predictions",
        json={
            "event_id": event_id,
            "prediction_type": "duration_estimate",
            "model_id": model_id,
        },
    )
    assert prediction_response.status_code == 200
    prediction = prediction_response.json()["prediction"]
    assert prediction["model_id"] == model_id
    assert Decimal(prediction["predicted_value"]) > Decimal("0")
    assert Decimal(prediction["confidence_score"]) >= Decimal("0.05")
