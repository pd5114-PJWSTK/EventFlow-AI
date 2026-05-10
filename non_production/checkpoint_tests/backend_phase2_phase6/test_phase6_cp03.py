from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_phase6_cp03_replan_after_incident_compares_previous_and_new_plan(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase6 CP03 Replan Client",
        location_name="Phase6 CP03 Replan Venue",
        event_name="Phase6 CP03 Replan Event",
        hours=4,
        days=22,
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
            "full_name": "CP03 Replan Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "60.00",
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

    baseline = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": event_id, "trigger_reason": "manual"},
    )
    assert baseline.status_code == 200
    baseline_payload = baseline.json()

    incident = api_client.post(
        f"/api/runtime/events/{event_id}/incident",
        json={
            "incident_type": "delay",
            "severity": "high",
            "description": "Crew arrival delayed due to road closure.",
            "sla_impact": True,
            "author_type": "coordinator",
        },
    )
    assert incident.status_code == 200
    incident_id = incident.json()["incident_id"]

    replan = api_client.post(
        f"/api/planner/replan/{event_id}",
        json={
            "incident_id": incident_id,
            "incident_summary": "Road closure delay during loadout",
            "initiated_by": "ops-coordinator",
            "solver_timeout_seconds": 8.0,
            "fallback_enabled": True,
        },
    )

    assert replan.status_code == 200
    payload = replan.json()
    assert payload["event_id"] == event_id
    assert payload["planner_run_trigger_reason"] == "incident"
    assert payload["baseline_recommendation_id"] == baseline_payload["recommendation_id"]
    assert payload["incident_id"] == incident_id
    assert payload["comparison"]["new_cost"] == payload["generated_plan"]["estimated_cost"]
    assert payload["generated_plan"]["planner_run_id"] == payload["planner_run_id"]
    assert payload["generated_plan"]["is_fully_assigned"] is True
    assert payload["generated_plan"]["assignments"][0]["requirement_id"] == requirement.json()[
        "requirement_id"
    ]


def test_phase6_cp03_replan_without_baseline_returns_empty_comparison_baseline(
    api_client: TestClient,
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase6 CP03 First Replan Client",
        location_name="Phase6 CP03 First Replan Venue",
        event_name="Phase6 CP03 First Replan Event",
        hours=2,
        days=23,
    )

    response = api_client.post(
        f"/api/planner/replan/{event_id}",
        json={
            "incident_summary": "Initial incident-triggered planning run.",
            "fallback_enabled": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == event_id
    assert payload["planner_run_trigger_reason"] == "incident"
    assert payload["baseline_recommendation_id"] is None
    assert payload["comparison"]["is_improved"] is None
