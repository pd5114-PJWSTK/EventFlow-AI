from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_generate_plan_reports_fallback_policy(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase4 CP04 Client",
        location_name="Phase4 CP04 Venue",
        event_name="Phase4 CP04 Event",
        hours=2,
        days=11,
    )

    requirement = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    assert requirement.status_code == 201

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "CP04 Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "50.00",
        },
    )
    assert person.status_code == 201

    availability = api_client.post(
        f"/api/resources/people/{person.json()['person_id']}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert availability.status_code == 201

    response = api_client.post(
        "/api/planner/generate-plan",
        json={
            "event_id": event_id,
            "solver_timeout_seconds": 5.0,
            "fallback_enabled": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["solver"] == "fallback"
    assert payload["fallback_reason"] == "ortools_unavailable"
    assert payload["fallback_enabled"] is True
    assert payload["solver_timeout_seconds"] == 5.0
    assert payload["solver_duration_ms"] >= 0
    assert payload["is_fully_assigned"] is True


def test_generate_plan_rejects_disabled_fallback_when_ortools_missing(
    api_client: TestClient,
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase4 CP04 No Fallback Client",
        location_name="Phase4 CP04 No Fallback Venue",
        event_name="Phase4 CP04 No Fallback Event",
        hours=2,
        days=12,
    )

    response = api_client.post(
        "/api/planner/generate-plan",
        json={
            "event_id": event_id,
            "solver_timeout_seconds": 5.0,
            "fallback_enabled": False,
        },
    )

    assert response.status_code == 400
    assert "Fallback disabled" in response.json()["detail"]
