from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_phase6_cp05_replan_preserves_consumed_assignments_and_adds_only_missing(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase6 CP05 Client",
        location_name="Phase6 CP05 Venue",
        event_name="Phase6 CP05 Event",
        hours=5,
        days=32,
    )

    requirement = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": "1",
        },
    )
    assert requirement.status_code == 201
    requirement_id = requirement.json()["requirement_id"]

    tomek = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Tomek Operator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "55.00",
            "reliability_notes": "high reliability",
        },
    )
    assert tomek.status_code == 201
    tomek_id = tomek.json()["person_id"]

    jan = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Jan Backup",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "70.00",
            "reliability_notes": "medium reliability",
        },
    )
    assert jan.status_code == 201
    jan_id = jan.json()["person_id"]

    for person_id in (tomek_id, jan_id):
        availability = api_client.post(
            f"/api/resources/people/{person_id}/availability",
            json={
                "available_from": planned_start,
                "available_to": planned_end,
                "is_available": True,
            },
        )
        assert availability.status_code == 201

    baseline = api_client.post("/api/planner/generate-plan", json={"event_id": event_id})
    assert baseline.status_code == 200
    baseline_payload = baseline.json()
    assert baseline_payload["is_fully_assigned"] is True
    assert len(baseline_payload["assignment_ids"]) == 1
    assert baseline_payload["assignments"][0]["resource_ids"] == [tomek_id]

    started = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={"author_type": "coordinator", "phase_name": "event_runtime"},
    )
    assert started.status_code == 200

    checkpoint = api_client.post(
        f"/api/runtime/events/{event_id}/checkpoint",
        json={
            "assignment_id": baseline_payload["assignment_ids"][0],
            "resource_type": "person",
            "person_id": tomek_id,
            "checkpoint_type": "setup_started",
            "author_type": "coordinator",
            "message": "Tomek started setup on site.",
        },
    )
    assert checkpoint.status_code == 200

    requirement_update = api_client.patch(
        f"/api/events/{event_id}/requirements/{requirement_id}",
        json={"quantity": "2"},
    )
    assert requirement_update.status_code == 200

    incident = api_client.post(
        f"/api/runtime/events/{event_id}/incident",
        json={
            "incident_type": "equipment_failure",
            "severity": "high",
            "description": "Need additional on-site coordination support.",
            "author_type": "coordinator",
        },
    )
    assert incident.status_code == 200

    replan = api_client.post(
        f"/api/planner/replan/{event_id}",
        json={
            "incident_id": incident.json()["incident_id"],
            "incident_summary": "Expand coordinator coverage without replacing active staff.",
            "commit_to_assignments": True,
            "preserve_consumed_resources": True,
        },
    )
    assert replan.status_code == 200
    payload = replan.json()

    assignment = next(
        item
        for item in payload["generated_plan"]["assignments"]
        if item["requirement_id"] == requirement_id
    )
    assert tomek_id in assignment["resource_ids"]
    assert len(assignment["resource_ids"]) == 2
    assert jan_id in assignment["resource_ids"]
    assert assignment["unassigned_count"] == 0
    assert baseline_payload["assignment_ids"][0] in payload["generated_plan"]["assignment_ids"]
