from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_validate_endpoint_returns_requirement_lists(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP04 Client",
        location_name="Phase3 CP04 Venue",
        event_name="Phase3 CP04 Event",
        budget=Decimal("8000.00"),
        hours=4,
        days=7,
    )

    role_req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    missing_req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "driver",
            "quantity": 2,
        },
    )
    assert role_req.status_code == 201
    assert missing_req.status_code == 201

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Planner Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "100.00",
        },
    )
    assert person.status_code == 201

    person_id = person.json()["person_id"]
    avail = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert avail.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()

    assert "supportable_requirements" in payload
    assert "unsupported_requirements" in payload
    assert role_req.json()["requirement_id"] in payload["supportable_requirements"]
    assert missing_req.json()["requirement_id"] in payload["unsupported_requirements"]


def test_validate_endpoint_keeps_error_mapping(api_client: TestClient) -> None:
    missing_event_resp = api_client.post(
        "/api/planner/validate-constraints",
        json={"event_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert missing_event_resp.status_code == 404
