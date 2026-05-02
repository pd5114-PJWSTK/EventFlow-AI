from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import future_window


def test_phase7_cp01_generates_event_feature_snapshot(api_client: TestClient) -> None:
    client = api_client.post(
        "/api/clients",
        json={"name": "Phase7 CP01 Client", "priority": "high"},
    )
    assert client.status_code == 201

    location = api_client.post(
        "/api/locations",
        json={
            "name": "Phase7 CP01 Venue",
            "city": "Warsaw",
            "location_type": "conference_center",
            "setup_complexity_score": 7,
            "access_difficulty": 4,
            "parking_difficulty": 3,
        },
    )
    assert location.status_code == 201

    planned_start, planned_end = future_window(hours=6, days=30)
    event = api_client.post(
        "/api/events",
        json={
            "client_id": client.json()["client_id"],
            "location_id": location.json()["location_id"],
            "event_name": "Phase7 CP01 Feature Event",
            "event_type": "conference",
            "event_subtype": "product-launch",
            "attendee_count": 240,
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

    skill = api_client.post("/api/resources/skills", json={"skill_name": "Mixing"})
    assert skill.status_code == 201

    equipment_type = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": "Line Array"},
    )
    assert equipment_type.status_code == 201

    requirement_person = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": "2",
        },
    )
    assert requirement_person.status_code == 201

    requirement_equipment = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "equipment_type",
            "equipment_type_id": equipment_type.json()["equipment_type_id"],
            "quantity": "3",
        },
    )
    assert requirement_equipment.status_code == 201

    requirement_vehicle = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "vehicle_type",
            "vehicle_type_required": "van",
            "quantity": "1",
        },
    )
    assert requirement_vehicle.status_code == 201

    generation = api_client.post(
        "/api/ml/features/generate",
        json={"event_id": event_id, "include_resource_features": False},
    )
    assert generation.status_code == 200
    payload = generation.json()
    assert payload["resource_features_generated"] == 0
    assert payload["event_feature"]["event_id"] == event_id
    assert payload["event_feature"]["feature_attendee_bucket"] == "large"
    assert payload["event_feature"]["feature_required_person_count"] == 2
    assert payload["event_feature"]["feature_required_equipment_count"] == 3
    assert payload["event_feature"]["feature_required_vehicle_count"] == 1
    assert payload["event_feature"]["feature_client_priority"] == "high"
    assert payload["event_feature"]["feature_location_type"] == "conference_center"

    by_id = api_client.get(f"/api/ml/features/events/{event_id}")
    assert by_id.status_code == 200
    from_store = by_id.json()
    assert from_store["event_id"] == event_id
    assert from_store["feature_event_subtype"] == "product-launch"


def test_phase7_cp01_generates_resource_features_for_people_equipment_and_vehicle(
    api_client: TestClient,
) -> None:
    client = api_client.post("/api/clients", json={"name": "Phase7 CP01 Resource Client"})
    location = api_client.post(
        "/api/locations",
        json={"name": "Phase7 CP01 Resource Hub", "city": "Warsaw"},
    )
    assert client.status_code == 201
    assert location.status_code == 201
    location_id = location.json()["location_id"]

    equipment_type = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": "Audio Rack"},
    )
    assert equipment_type.status_code == 201

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Phase7 CP01 Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "80.00",
        },
    )
    assert person.status_code == 201

    equipment = api_client.post(
        "/api/resources/equipment",
        json={
            "equipment_type_id": equipment_type.json()["equipment_type_id"],
            "warehouse_location_id": location_id,
            "hourly_cost_estimate": "50.00",
        },
    )
    assert equipment.status_code == 201

    vehicle = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "Phase7 Van",
            "vehicle_type": "van",
            "home_location_id": location_id,
            "cost_per_hour": "120.00",
            "cost_per_km": "1.20",
        },
    )
    assert vehicle.status_code == 201

    generation = api_client.post(
        "/api/ml/features/generate",
        json={"include_event_feature": False, "include_resource_features": True},
    )
    assert generation.status_code == 200
    payload = generation.json()
    assert payload["event_feature"] is None
    assert payload["resource_features_generated"] == 3
    assert len(payload["resource_features"]) == 3

    resource_types = {item["resource_type"] for item in payload["resource_features"]}
    assert resource_types == {"person", "equipment", "vehicle"}

    for item in payload["resource_features"]:
        reliability = Decimal(item["reliability_score"])
        utilization = Decimal(item["utilization_rate_last_30d"])
        fatigue = Decimal(item["fatigue_score"])
        assert Decimal("0") <= reliability <= Decimal("1")
        assert Decimal("0") <= utilization <= Decimal("1")
        assert Decimal("0") <= fatigue <= Decimal("1")

    listed = api_client.get("/api/ml/features/resources/latest?limit=10")
    assert listed.status_code == 200
    listed_payload = listed.json()
    assert listed_payload["total"] >= 3


def test_phase7_cp01_returns_404_for_unknown_event_snapshot_generation(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/ml/features/generate",
        json={
            "event_id": "00000000-0000-0000-0000-000000000000",
            "include_event_feature": True,
            "include_resource_features": False,
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"
