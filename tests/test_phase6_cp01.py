from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_phase6_cp01_runtime_start_sets_event_in_progress(
    api_client: TestClient,
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase6 CP01 Start Client",
        location_name="Phase6 CP01 Start Venue",
        event_name="Phase6 CP01 Start Event",
        days=15,
    )

    response = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={
            "author_type": "coordinator",
            "author_reference": "ops-user-1",
            "message": "Execution started on site",
            "phase_name": "event_runtime",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == event_id
    assert payload["event_status"] == "in_progress"
    assert payload["log_id"]
    assert payload["timing_id"]

    event_after = api_client.get(f"/api/events/{event_id}")
    assert event_after.status_code == 200
    assert event_after.json()["status"] == "in_progress"


def test_phase6_cp01_runtime_checkpoint_logs_resource_position(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase6 CP01 Checkpoint Client",
        location_name="Phase6 CP01 Checkpoint Venue",
        event_name="Phase6 CP01 Checkpoint Event",
        days=16,
    )
    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Checkpoint Driver",
            "role": "driver",
            "home_base_location_id": location_id,
            "cost_per_hour": "55.00",
        },
    )
    assert person.status_code == 201
    person_id = person.json()["person_id"]

    response = api_client.post(
        f"/api/runtime/events/{event_id}/checkpoint",
        json={
            "resource_type": "person",
            "person_id": person_id,
            "checkpoint_type": "arrived",
            "latitude": "52.229700",
            "longitude": "21.012200",
            "author_type": "technician",
            "message": "Driver arrived at venue",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == event_id
    assert payload["checkpoint_id"]
    assert payload["log_id"]


def test_phase6_cp01_runtime_incident_creates_incident_log(
    api_client: TestClient,
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase6 CP01 Incident Client",
        location_name="Phase6 CP01 Incident Venue",
        event_name="Phase6 CP01 Incident Event",
        days=17,
    )

    response = api_client.post(
        f"/api/runtime/events/{event_id}/incident",
        json={
            "incident_type": "equipment_failure",
            "severity": "high",
            "description": "Main audio console failed during soundcheck.",
            "reported_by": "field-tech-2",
            "cost_impact": "1200.00",
            "sla_impact": True,
            "author_type": "technician",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == event_id
    assert payload["incident_id"]
    assert payload["log_id"]


def test_phase6_cp01_runtime_complete_closes_event_and_writes_outcome(
    api_client: TestClient,
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase6 CP01 Complete Client",
        location_name="Phase6 CP01 Complete Venue",
        event_name="Phase6 CP01 Complete Event",
        days=18,
    )
    start_resp = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={"phase_name": "event_runtime"},
    )
    assert start_resp.status_code == 200

    complete_resp = api_client.post(
        f"/api/runtime/events/{event_id}/complete",
        json={
            "finished_on_time": False,
            "total_delay_minutes": 35,
            "actual_cost": "18950.00",
            "overtime_cost": "850.00",
            "transport_cost": "2100.00",
            "sla_breached": True,
            "client_satisfaction_score": "7.5",
            "internal_quality_score": "8.2",
            "margin_estimate": "3200.00",
            "summary_notes": "Completed with delays due to traffic and repair.",
            "author_type": "manager",
        },
    )
    assert complete_resp.status_code == 200
    payload = complete_resp.json()
    assert payload["event_id"] == event_id
    assert payload["event_status"] == "completed"
    assert payload["outcome_event_id"] == event_id
    assert payload["log_id"]
    assert payload["timing_id"]

    event_after = api_client.get(f"/api/events/{event_id}")
    assert event_after.status_code == 200
    assert event_after.json()["status"] == "completed"
