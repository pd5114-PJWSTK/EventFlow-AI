from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_availability_window_mismatch_creates_gap(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP01 Client",
        location_name="Phase3 CP01 Venue",
        event_name="Phase3 CP01 Event",
        hours=4,
        days=4,
    )

    requirement_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    assert requirement_resp.status_code == 201

    person_resp = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Window Mismatch Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
        },
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["person_id"]

    event_end = datetime.fromisoformat(planned_end)
    late_start = (event_end + timedelta(hours=1)).isoformat()
    late_end = (event_end + timedelta(hours=5)).isoformat()

    availability_resp = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": late_start,
            "available_to": late_end,
            "is_available": True,
        },
    )
    assert availability_resp.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200

    payload = validate_resp.json()
    assert payload["is_supportable"] is False
    assert any(gap["code"] == "AVAILABILITY_WINDOW_MISMATCH" for gap in payload["gaps"])


def test_optional_requirement_availability_gap_is_warning(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP01 Optional Client",
        location_name="Phase3 CP01 Optional Venue",
        event_name="Phase3 CP01 Optional Event",
        hours=3,
        days=4,
    )

    requirement_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
            "mandatory": False,
        },
    )
    assert requirement_resp.status_code == 201

    person_resp = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Optional Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
        },
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["person_id"]

    event_start = datetime.fromisoformat(planned_start)
    early_start = (event_start - timedelta(hours=5)).isoformat()
    early_end = (event_start - timedelta(hours=1)).isoformat()

    availability_resp = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": early_start,
            "available_to": early_end,
            "is_available": True,
        },
    )
    assert availability_resp.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200

    payload = validate_resp.json()
    assert payload["is_supportable"] is True
    assert any(
        gap["code"] == "AVAILABILITY_WINDOW_MISMATCH" and gap["severity"] == "warning"
        for gap in payload["gaps"]
    )
