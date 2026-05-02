from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def _future_iso(days: int, hours: int = 4) -> tuple[str, str]:
    start = datetime.now(timezone.utc) + timedelta(days=days)
    end = start + timedelta(hours=hours)
    return start.isoformat(), end.isoformat()


def test_phase8_cp02_older_event_priority_blocks_newer_event_resource_conflict(
    api_client: TestClient,
) -> None:
    _, location_id, older_event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP02 Older Client",
        location_name="Phase8 CP02 Priority Venue",
        event_name="Phase8 CP02 Older Event",
        days=50,
    )
    newer_start, newer_end = _future_iso(days=50)
    newer_client = api_client.post("/api/clients", json={"name": "Phase8 CP02 Newer Client"})
    assert newer_client.status_code == 201

    newer_event = api_client.post(
        "/api/events",
        json={
            "client_id": newer_client.json()["client_id"],
            "location_id": location_id,
            "event_name": "Phase8 CP02 Newer Event",
            "event_type": "conference",
            "planned_start": newer_start,
            "planned_end": newer_end,
        },
    )
    assert newer_event.status_code == 201
    newer_event_id = newer_event.json()["event_id"]

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "CP02 Priority Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "65.00",
            "reliability_notes": "high reliability",
        },
    )
    assert person.status_code == 201
    person_id = person.json()["person_id"]

    availability = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert availability.status_code == 201

    for event_id in (older_event_id, newer_event_id):
        req = api_client.post(
            f"/api/events/{event_id}/requirements",
            json={
                "requirement_type": "person_role",
                "role_required": "coordinator",
                "quantity": "1",
            },
        )
        assert req.status_code == 201

    older_plan = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": older_event_id, "commit_to_assignments": True},
    )
    assert older_plan.status_code == 200
    assert older_plan.json()["is_fully_assigned"] is True
    assert older_plan.json()["assignments"][0]["resource_ids"] == [person_id]

    newer_plan = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": newer_event_id, "commit_to_assignments": True},
    )
    assert newer_plan.status_code == 200
    payload = newer_plan.json()
    assert payload["is_fully_assigned"] is False
    assert payload["assignments"][0]["resource_ids"] == []
    assert payload["assignments"][0]["unassigned_count"] == 1
    assert payload["gap_resolution"] is not None


def test_phase8_cp02_generate_plan_with_gaps_returns_user_resolution_options(
    api_client: TestClient,
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase8 CP02 Gaps Client",
        location_name="Phase8 CP02 Gaps Venue",
        event_name="Phase8 CP02 Gaps Event",
        days=51,
    )
    req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "technician_audio",
            "quantity": "2",
        },
    )
    assert req.status_code == 201

    response = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": event_id, "commit_to_assignments": False},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_fully_assigned"] is False
    assert payload["gap_resolution"] is not None
    assert payload["gap_resolution"]["has_gaps"] is True
    assert len(payload["gap_resolution"]["requirement_gaps"]) >= 1
    option_types = {item["option_type"] for item in payload["gap_resolution"]["options"]}
    assert "augment_resources" in option_types
    assert "reschedule_event" in option_types
