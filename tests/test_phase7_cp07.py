from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from tests.helpers import future_window


def _seed_real_training_events(api_client: TestClient, *, count: int) -> None:
    client = api_client.post(
        "/api/clients",
        json={"name": "Phase7 CP07 Training Client", "priority": "medium"},
    )
    location = api_client.post(
        "/api/locations",
        json={
            "name": "Phase7 CP07 Training Venue",
            "city": "Warsaw",
            "setup_complexity_score": 6,
            "access_difficulty": 3,
            "parking_difficulty": 3,
        },
    )
    equipment_type = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": "Phase7 CP07 Training Rack"},
    )
    assert client.status_code == 201
    assert location.status_code == 201
    assert equipment_type.status_code == 201
    client_id = client.json()["client_id"]
    location_id = location.json()["location_id"]
    equipment_type_id = equipment_type.json()["equipment_type_id"]

    for idx in range(count):
        planned_start, planned_end = future_window(hours=4 + (idx % 3), days=160 + idx)
        attendee_count = 60 + (idx * 8)
        event = api_client.post(
            "/api/events",
            json={
                "client_id": client_id,
                "location_id": location_id,
                "event_name": f"Phase7 CP07 Train Event {idx}",
                "event_type": "conference",
                "event_subtype": "touring",
                "attendee_count": attendee_count,
                "planned_start": planned_start,
                "planned_end": planned_end,
                "priority": ["low", "medium", "high", "critical"][idx % 4],
                "requires_transport": idx % 2 == 0,
                "requires_setup": True,
                "requires_teardown": idx % 3 != 0,
            },
        )
        assert event.status_code == 201
        event_id = event.json()["event_id"]

        person_req = api_client.post(
            f"/api/events/{event_id}/requirements",
            json={
                "requirement_type": "person_role",
                "role_required": "coordinator",
                "quantity": str(1 + (idx % 3)),
            },
        )
        equipment_req = None
        if (idx % 3) > 0:
            equipment_req = api_client.post(
                f"/api/events/{event_id}/requirements",
                json={
                    "requirement_type": "equipment_type",
                    "equipment_type_id": equipment_type_id,
                    "quantity": str(idx % 3),
                },
            )
        vehicle_req = None
        if (idx % 2) > 0:
            vehicle_req = api_client.post(
                f"/api/events/{event_id}/requirements",
                json={
                    "requirement_type": "vehicle_type",
                    "vehicle_type_required": "van",
                    "quantity": str(idx % 2),
                },
            )
        assert person_req.status_code == 201
        if equipment_req is not None:
            assert equipment_req.status_code == 201
        if vehicle_req is not None:
            assert vehicle_req.status_code == 201

        features = api_client.post(
            "/api/ml/features/generate",
            json={"event_id": event_id, "include_resource_features": False},
        )
        assert features.status_code == 200

        duration_minutes = int(
            90
            + attendee_count * 0.24
            + (idx % 5) * 13
            + (idx % 4) * 7
            + (idx % 3) * 6
            + (idx % 2) * 24
        )
        start_at = datetime(2026, 6, 1, 7, 0, 0) + timedelta(hours=idx * 2)
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


def _seed_target_planning_event(api_client: TestClient) -> tuple[str, str, str]:
    client = api_client.post(
        "/api/clients",
        json={"name": "Phase7 CP07 Target Client", "priority": "high"},
    )
    location = api_client.post(
        "/api/locations",
        json={
            "name": "Phase7 CP07 Target Venue",
            "city": "Warsaw",
            "setup_complexity_score": 8,
            "access_difficulty": 4,
            "parking_difficulty": 3,
        },
    )
    equipment_type = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": "Phase7 CP07 Target Rack"},
    )
    assert client.status_code == 201
    assert location.status_code == 201
    assert equipment_type.status_code == 201

    planned_start, planned_end = future_window(hours=6, days=240)
    event = api_client.post(
        "/api/events",
        json={
            "client_id": client.json()["client_id"],
            "location_id": location.json()["location_id"],
            "event_name": "Phase7 CP07 Target Event",
            "event_type": "conference",
            "event_subtype": "festival",
            "attendee_count": 320,
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

    for payload in (
        {
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": "2",
        },
        {
            "requirement_type": "equipment_type",
            "equipment_type_id": equipment_type.json()["equipment_type_id"],
            "quantity": "1",
        },
        {
            "requirement_type": "vehicle_type",
            "vehicle_type_required": "van",
            "quantity": "1",
        },
    ):
        req = api_client.post(f"/api/events/{event_id}/requirements", json=payload)
        assert req.status_code == 201

    person_high = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "CP07 High Reliability Coordinator",
            "role": "coordinator",
            "home_base_location_id": location.json()["location_id"],
            "cost_per_hour": "95.00",
            "reliability_notes": "high reliability",
        },
    )
    person_low = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "CP07 Budget Coordinator",
            "role": "coordinator",
            "home_base_location_id": location.json()["location_id"],
            "cost_per_hour": "55.00",
            "reliability_notes": "medium reliability",
        },
    )
    equipment_a = api_client.post(
        "/api/resources/equipment",
        json={
            "equipment_type_id": equipment_type.json()["equipment_type_id"],
            "warehouse_location_id": location.json()["location_id"],
            "hourly_cost_estimate": "40.00",
        },
    )
    equipment_b = api_client.post(
        "/api/resources/equipment",
        json={
            "equipment_type_id": equipment_type.json()["equipment_type_id"],
            "warehouse_location_id": location.json()["location_id"],
            "hourly_cost_estimate": "60.00",
        },
    )
    vehicle_a = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "CP07 Budget Van",
            "vehicle_type": "van",
            "home_location_id": location.json()["location_id"],
            "cost_per_hour": "70.00",
            "cost_per_km": "1.10",
        },
    )
    vehicle_b = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "CP07 Premium Van",
            "vehicle_type": "van",
            "home_location_id": location.json()["location_id"],
            "cost_per_hour": "120.00",
            "cost_per_km": "1.70",
        },
    )
    assert person_high.status_code == 201
    assert person_low.status_code == 201
    assert equipment_a.status_code == 201
    assert equipment_b.status_code == 201
    assert vehicle_a.status_code == 201
    assert vehicle_b.status_code == 201

    for person_id in (person_high.json()["person_id"], person_low.json()["person_id"]):
        availability = api_client.post(
            f"/api/resources/people/{person_id}/availability",
            json={
                "available_from": planned_start,
                "available_to": planned_end,
                "is_available": True,
            },
        )
        assert availability.status_code == 201

    for equipment_id in (equipment_a.json()["equipment_id"], equipment_b.json()["equipment_id"]):
        availability = api_client.post(
            f"/api/resources/equipment/{equipment_id}/availability",
            json={
                "available_from": planned_start,
                "available_to": planned_end,
                "is_available": True,
            },
        )
        assert availability.status_code == 201

    for vehicle_id in (vehicle_a.json()["vehicle_id"], vehicle_b.json()["vehicle_id"]):
        availability = api_client.post(
            f"/api/resources/vehicles/{vehicle_id}/availability",
            json={
                "available_from": planned_start,
                "available_to": planned_end,
                "is_available": True,
            },
        )
        assert availability.status_code == 201

    features = api_client.post(
        "/api/ml/features/generate",
        json={"event_id": event_id, "include_resource_features": False},
    )
    assert features.status_code == 200

    return event_id, planned_start, planned_end


def test_phase7_cp07_plan_evaluator_training_requires_real_samples(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/ml/models/train-plan-evaluator",
        json={"required_real_samples": 60},
    )
    assert response.status_code == 400
    assert "Insufficient real samples for plan evaluator training" in response.json()["detail"]


def test_phase7_cp07_ml_recommends_best_candidate_and_commits_plan(
    api_client: TestClient,
) -> None:
    _seed_real_training_events(api_client, count=60)

    duration_model = api_client.post(
        "/api/ml/models/harden-duration",
        json={
            "model_name": "event_duration_hardened",
            "required_real_samples": 60,
            "train_samples": 50,
            "test_samples": 10,
        },
    )
    assert duration_model.status_code == 200

    evaluator = api_client.post(
        "/api/ml/models/train-plan-evaluator",
        json={"required_real_samples": 60},
    )
    assert evaluator.status_code == 200
    evaluator_payload = evaluator.json()
    assert evaluator_payload["real_samples_used"] == 60
    assert evaluator_payload["candidate_samples"] == 240

    event_id, _, _ = _seed_target_planning_event(api_client)
    response = api_client.post(
        "/api/planner/recommend-best-plan",
        json={
            "event_id": event_id,
            "commit_to_assignments": True,
            "duration_model_id": duration_model.json()["model"]["model_id"],
            "plan_evaluator_model_id": evaluator_payload["model"]["model_id"],
            "initiated_by": "pytest-cp07",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == event_id
    assert payload["planner_run_id"]
    assert payload["recommendation_id"]
    assert payload["selected_candidate_name"]
    assert len(payload["candidates"]) == 4

    scores = [float(item["ml_quality_score"]) for item in payload["candidates"]]
    assert scores == sorted(scores, reverse=True)
    assert float(payload["selected_quality_score"]) == scores[0]
    assert payload["selected_plan"]["event_id"] == event_id
    assert payload["selected_plan"]["is_fully_assigned"] is True
    assert len(payload["selected_plan"]["assignment_ids"]) >= 3

    event = api_client.get(f"/api/events/{event_id}")
    assert event.status_code == 200
    assert event.json()["status"] == "planned"
