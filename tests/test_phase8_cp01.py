from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def _seed_replan_context(api_client: TestClient) -> tuple[str, str, str, str]:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP01 Replan Client",
        location_name="Phase8 CP01 Replan Venue",
        event_name="Phase8 CP01 Replan Event",
        hours=5,
        days=40,
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
            "full_name": "CP01 Tomek",
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
            "full_name": "CP01 Jan",
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

    return event_id, requirement_id, tomek_id, jan_id


def test_phase8_cp01_runtime_start_is_idempotent(api_client: TestClient) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase8 CP01 Idem Client",
        location_name="Phase8 CP01 Idem Venue",
        event_name="Phase8 CP01 Idem Event",
        days=35,
    )
    payload = {
        "author_type": "coordinator",
        "phase_name": "event_runtime",
        "idempotency_key": "runtime-start-idem-0001",
    }
    first = api_client.post(f"/api/runtime/events/{event_id}/start", json=payload)
    assert first.status_code == 200

    second = api_client.post(f"/api/runtime/events/{event_id}/start", json=payload)
    assert second.status_code == 200
    assert second.headers.get("x-idempotency-replayed") == "true"
    assert first.json()["log_id"] == second.json()["log_id"]
    assert first.json()["timing_id"] == second.json()["timing_id"]


def test_phase8_cp01_runtime_start_idempotency_conflict(api_client: TestClient) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase8 CP01 Idem Conflict Client",
        location_name="Phase8 CP01 Idem Conflict Venue",
        event_name="Phase8 CP01 Idem Conflict Event",
        days=36,
    )
    key = "runtime-start-idem-0002"
    first = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={
            "author_type": "coordinator",
            "phase_name": "event_runtime",
            "idempotency_key": key,
        },
    )
    assert first.status_code == 200

    second = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={
            "author_type": "manager",
            "phase_name": "event_runtime",
            "idempotency_key": key,
        },
    )
    assert second.status_code == 409
    assert second.headers.get("x-error-code") == "IDEMPOTENCY_CONFLICT"


def test_phase8_cp01_replan_is_idempotent_and_preserves_consumed_resources(
    api_client: TestClient,
) -> None:
    event_id, requirement_id, tomek_id, jan_id = _seed_replan_context(api_client)

    baseline = api_client.post("/api/planner/generate-plan", json={"event_id": event_id})
    assert baseline.status_code == 200
    baseline_assignment_id = baseline.json()["assignment_ids"][0]

    started = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={"author_type": "coordinator", "phase_name": "event_runtime"},
    )
    assert started.status_code == 200

    checkpoint = api_client.post(
        f"/api/runtime/events/{event_id}/checkpoint",
        json={
            "assignment_id": baseline_assignment_id,
            "resource_type": "person",
            "person_id": tomek_id,
            "checkpoint_type": "setup_started",
            "author_type": "coordinator",
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
            "description": "Need extra support after incident.",
            "author_type": "coordinator",
        },
    )
    assert incident.status_code == 200
    incident_id = incident.json()["incident_id"]

    replan_payload = {
        "incident_id": incident_id,
        "incident_summary": "Add one more coordinator, keep active one on site.",
        "commit_to_assignments": True,
        "idempotency_key": "planner-replan-idem-0001",
    }
    first = api_client.post(f"/api/planner/replan/{event_id}", json=replan_payload)
    assert first.status_code == 200
    first_payload = first.json()

    assignment = next(
        item
        for item in first_payload["generated_plan"]["assignments"]
        if item["requirement_id"] == requirement_id
    )
    assert tomek_id in assignment["resource_ids"]
    assert jan_id in assignment["resource_ids"]
    assert assignment["unassigned_count"] == 0

    second = api_client.post(f"/api/planner/replan/{event_id}", json=replan_payload)
    assert second.status_code == 200
    assert second.headers.get("x-idempotency-replayed") == "true"
    assert (
        first_payload["planner_run_id"] == second.json()["planner_run_id"]
    )


def test_phase8_cp01_runtime_complete_handles_mixed_timezones(api_client: TestClient) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase8 CP01 TZ Client",
        location_name="Phase8 CP01 TZ Venue",
        event_name="Phase8 CP01 TZ Event",
        days=38,
    )

    started = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={
            "started_at": "2026-05-02T10:00:00+02:00",
            "phase_name": "event_runtime",
            "idempotency_key": "runtime-start-tz-0001",
        },
    )
    assert started.status_code == 200

    completed = api_client.post(
        f"/api/runtime/events/{event_id}/complete",
        json={
            "completed_at": "2026-05-02T13:30:00Z",
            "phase_name": "event_runtime",
            "idempotency_key": "runtime-complete-tz-0001",
        },
    )
    assert completed.status_code == 200


def test_phase8_cp01_generate_plan_performance_smoke(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP01 Perf Client",
        location_name="Phase8 CP01 Perf Venue",
        event_name="Phase8 CP01 Perf Event",
        hours=4,
        days=39,
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

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "CP01 Perf Coordinator",
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

    started = perf_counter()
    response = api_client.post("/api/planner/generate-plan", json={"event_id": event_id})
    elapsed = perf_counter() - started
    assert response.status_code == 200
    assert elapsed < 2.5


def test_phase8_cp01_replan_rejects_stale_event_version(api_client: TestClient) -> None:
    event_id, _, _, _ = _seed_replan_context(api_client)

    event = api_client.get(f"/api/events/{event_id}")
    assert event.status_code == 200
    stale_updated_at = event.json()["updated_at"]

    update = api_client.patch(
        f"/api/events/{event_id}",
        json={"notes": f"touch-{datetime.now(UTC).isoformat()}"},
    )
    assert update.status_code == 200

    response = api_client.post(
        f"/api/planner/replan/{event_id}",
        json={
            "incident_summary": "stale check",
            "expected_event_updated_at": stale_updated_at,
            "idempotency_key": "planner-replan-stale-0001",
        },
    )
    assert response.status_code == 400
    assert "concurrently" in response.json()["detail"]
