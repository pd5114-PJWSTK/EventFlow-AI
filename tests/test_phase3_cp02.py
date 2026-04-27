from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_max_hours_exceeded_gap_for_mandatory_requirement(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP02 Client",
        location_name="Phase3 CP02 Venue",
        event_name="Phase3 CP02 Event",
        budget=Decimal("5000.00"),
        hours=6,
        days=5,
    )

    req_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    assert req_resp.status_code == 201

    person_resp = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Low Hours Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "max_daily_hours": "2.0",
            "cost_per_hour": "120.00",
        },
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["person_id"]

    avail_resp = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert avail_resp.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()

    assert payload["is_supportable"] is False
    assert any(gap["code"] == "MAX_HOURS_EXCEEDED" for gap in payload["gaps"])


def test_max_hours_exceeded_warning_for_optional_requirement(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP02 Optional Client",
        location_name="Phase3 CP02 Optional Venue",
        event_name="Phase3 CP02 Optional Event",
        budget=Decimal("5000.00"),
        hours=5,
        days=5,
    )

    req_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
            "mandatory": False,
        },
    )
    assert req_resp.status_code == 201

    person_resp = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Low Hours Optional",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "max_daily_hours": "1.0",
            "cost_per_hour": "100.00",
        },
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["person_id"]

    avail_resp = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert avail_resp.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()

    assert payload["is_supportable"] is True
    assert any(
        gap["code"] == "MAX_HOURS_EXCEEDED" and gap["severity"] == "warning"
        for gap in payload["gaps"]
    )


def test_cost_breakdown_people_equipment_vehicle(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP02 Cost Client",
        location_name="Phase3 CP02 Cost Venue",
        event_name="Phase3 CP02 Cost Event",
        budget=Decimal("10000.00"),
        hours=4,
        days=5,
    )

    eq_type_resp = api_client.post(
        "/api/resources/equipment-types", json={"type_name": "cp02_case_type"}
    )
    assert eq_type_resp.status_code == 201
    equipment_type_id = eq_type_resp.json()["equipment_type_id"]

    role_req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    eq_req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "equipment_type",
            "equipment_type_id": equipment_type_id,
            "quantity": 1,
        },
    )
    vehicle_req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "vehicle_type",
            "vehicle_type_required": "van",
            "quantity": 1,
        },
    )
    assert role_req.status_code == 201
    assert eq_req.status_code == 201
    assert vehicle_req.status_code == 201

    person_resp = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Cost Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "100.00",
        },
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["person_id"]

    equipment_resp = api_client.post(
        "/api/resources/equipment",
        json={
            "equipment_type_id": equipment_type_id,
            "asset_tag": "CP02-EQ-1",
            "warehouse_location_id": location_id,
            "hourly_cost_estimate": "50.00",
        },
    )
    assert equipment_resp.status_code == 201
    equipment_id = equipment_resp.json()["equipment_id"]

    vehicle_resp = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "Cost Van",
            "vehicle_type": "van",
            "home_location_id": location_id,
            "cost_per_hour": "80.00",
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
    breakdown = payload["cost_breakdown"]
    assert Decimal(breakdown["people_cost"]) > 0
    assert Decimal(breakdown["equipment_cost"]) > 0
    assert Decimal(breakdown["vehicles_cost"]) > 0
    assert Decimal(breakdown["total_cost"]) == Decimal(payload["estimated_cost"])
