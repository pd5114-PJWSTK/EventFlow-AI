from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_phase6_cp04_runtime_notifications_feed_contains_start_event(
    api_client: TestClient,
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase6 CP04 Notify Client",
        location_name="Phase6 CP04 Notify Venue",
        event_name="Phase6 CP04 Notify Event",
        days=24,
    )

    start_response = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={"author_type": "coordinator", "phase_name": "event_runtime"},
    )
    assert start_response.status_code == 200

    feed = api_client.get(f"/api/runtime/events/{event_id}/notifications?limit=20")
    assert feed.status_code == 200
    payload = feed.json()
    assert payload["event_id"] == event_id
    assert payload["total"] >= 1
    assert any(item["notification_type"] == "event_started" for item in payload["items"])


def test_phase6_cp04_runtime_notifications_include_replan_completed(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase6 CP04 Replan Notify Client",
        location_name="Phase6 CP04 Replan Notify Venue",
        event_name="Phase6 CP04 Replan Notify Event",
        hours=3,
        days=25,
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
            "full_name": "CP04 Replan Notify Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "70.00",
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

    baseline = api_client.post("/api/planner/generate-plan", json={"event_id": event_id})
    assert baseline.status_code == 200

    incident = api_client.post(
        f"/api/runtime/events/{event_id}/incident",
        json={
            "incident_type": "delay",
            "severity": "high",
            "description": "Traffic disruption affected crew arrival.",
            "author_type": "coordinator",
        },
    )
    assert incident.status_code == 200

    replan = api_client.post(
        f"/api/planner/replan/{event_id}",
        json={
            "incident_id": incident.json()["incident_id"],
            "incident_summary": "Traffic issue in city center",
        },
    )
    assert replan.status_code == 200

    feed = api_client.get(f"/api/runtime/events/{event_id}/notifications?limit=50")
    assert feed.status_code == 200
    payload = feed.json()
    types = [item["notification_type"] for item in payload["items"]]
    assert "incident_reported" in types
    assert "replan_completed" in types


def test_phase6_cp04_runtime_websocket_emits_notifications(
    api_client: TestClient,
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase6 CP04 WS Client",
        location_name="Phase6 CP04 WS Venue",
        event_name="Phase6 CP04 WS Event",
        days=26,
    )

    start_response = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={"author_type": "coordinator", "phase_name": "event_runtime"},
    )
    assert start_response.status_code == 200

    with api_client.websocket_connect(
        f"/api/runtime/ws/events/{event_id}/notifications",
        headers={"Authorization": api_client.headers.get("Authorization", "")},
    ) as ws:
        message = ws.receive_json()
        assert message["event_id"] == event_id
        assert message["total"] >= 1
        assert any(item["notification_type"] == "event_started" for item in message["items"])
