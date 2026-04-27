from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_phase3_full_validation_flow(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP05 Flow Client",
        location_name="Phase3 CP05 Flow Venue",
        event_name="Phase3 CP05 Flow Event",
        budget=Decimal("12000.00"),
        hours=5,
        days=8,
    )

    skill_resp = api_client.post(
        "/api/resources/skills",
        json={"skill_name": "phase3_cp05_skill", "skill_category": "technical"},
    )
    assert skill_resp.status_code == 201
    skill_id = skill_resp.json()["skill_id"]

    eq_type_resp = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": "phase3_cp05_eq_type"},
    )
    assert eq_type_resp.status_code == 201
    eq_type_id = eq_type_resp.json()["equipment_type_id"]

    req_role = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    req_skill = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={"requirement_type": "person_skill", "skill_id": skill_id, "quantity": 1},
    )
    req_eq = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "equipment_type",
            "equipment_type_id": eq_type_id,
            "quantity": 1,
        },
    )
    req_vehicle = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "vehicle_type",
            "vehicle_type_required": "van",
            "quantity": 1,
        },
    )
    assert req_role.status_code == 201
    assert req_skill.status_code == 201
    assert req_eq.status_code == 201
    assert req_vehicle.status_code == 201

    person_resp = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Phase3 Flow Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "150.00",
            "reliability_notes": "high reliability",
        },
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["person_id"]

    assign_skill = api_client.post(
        f"/api/resources/people/{person_id}/skills",
        json={"skill_id": skill_id, "skill_level": 4, "certified": True},
    )
    assert assign_skill.status_code == 200

    equipment_resp = api_client.post(
        "/api/resources/equipment",
        json={
            "equipment_type_id": eq_type_id,
            "asset_tag": "PH3-CP05-EQ-1",
            "warehouse_location_id": location_id,
            "hourly_cost_estimate": "60.00",
        },
    )
    assert equipment_resp.status_code == 201
    equipment_id = equipment_resp.json()["equipment_id"]

    vehicle_resp = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "Phase3 Flow Van",
            "vehicle_type": "van",
            "home_location_id": location_id,
            "cost_per_hour": "90.00",
        },
    )
    assert vehicle_resp.status_code == 201
    vehicle_id = vehicle_resp.json()["vehicle_id"]

    person_avail = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    equipment_avail = api_client.post(
        f"/api/resources/equipment/{equipment_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    vehicle_avail = api_client.post(
        f"/api/resources/vehicles/{vehicle_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert person_avail.status_code == 201
    assert equipment_avail.status_code == 201
    assert vehicle_avail.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()

    assert payload["is_supportable"] is True
    assert payload["budget_exceeded"] is False
    assert payload["unsupported_requirements"] == []
    assert len(payload["supportable_requirements"]) == 4
    assert Decimal(payload["cost_breakdown"]["total_cost"]) == Decimal(
        payload["estimated_cost"]
    )


def test_phase3_smoke_missing_event(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/planner/validate-constraints",
        json={"event_id": "ffffffff-ffff-ffff-ffff-ffffffffffff"},
    )
    assert response.status_code == 404
