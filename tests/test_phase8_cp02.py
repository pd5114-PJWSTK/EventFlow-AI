from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def _future_iso(days: int, hours: int = 4) -> tuple[str, str]:
    start = datetime.now(timezone.utc) + timedelta(days=days)
    end = start + timedelta(hours=hours)
    return start.isoformat(), end.isoformat()


def _advance_event_to_confirmed(api_client: TestClient, event_id: str) -> None:
    for status in ("submitted", "validated", "planned", "confirmed"):
        response = api_client.patch(f"/api/events/{event_id}", json={"status": status})
        assert response.status_code == 200


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
    assert len(payload["gap_resolution"]["suggested_reschedule_windows"]) >= 1


def test_phase8_cp02_accepted_event_can_preempt_older_not_accepted_event(
    api_client: TestClient,
) -> None:
    _, location_id, older_event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP02 Older Not Accepted Client",
        location_name="Phase8 CP02 Accepted Priority Venue",
        event_name="Phase8 CP02 Older Not Accepted Event",
        days=52,
    )
    newer_client = api_client.post(
        "/api/clients", json={"name": "Phase8 CP02 Newer Accepted Client"}
    )
    assert newer_client.status_code == 201
    newer_event = api_client.post(
        "/api/events",
        json={
            "client_id": newer_client.json()["client_id"],
            "location_id": location_id,
            "event_name": "Phase8 CP02 Newer Accepted Event",
            "event_type": "conference",
            "planned_start": planned_start,
            "planned_end": planned_end,
        },
    )
    assert newer_event.status_code == 201
    newer_event_id = newer_event.json()["event_id"]

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "CP02 Accepted Priority Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "66.00",
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
    assert older_plan.json()["assignments"][0]["resource_ids"] == [person_id]

    _advance_event_to_confirmed(api_client, newer_event_id)
    newer_plan = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": newer_event_id, "commit_to_assignments": True},
    )
    assert newer_plan.status_code == 200
    assert newer_plan.json()["assignments"][0]["resource_ids"] == [person_id]


def test_phase8_cp02_resolve_gaps_augment_resources_reruns_planner(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP02 Resolve Augment Client",
        location_name="Phase8 CP02 Resolve Augment Venue",
        event_name="Phase8 CP02 Resolve Augment Event",
        days=53,
    )
    req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": "1",
        },
    )
    assert req.status_code == 201

    before = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": event_id, "commit_to_assignments": False},
    )
    assert before.status_code == 200
    assert before.json()["is_fully_assigned"] is False

    resolved = api_client.post(
        f"/api/planner/resolve-gaps/{event_id}",
        json={
            "strategy": "augment_resources",
            "commit_to_assignments": True,
            "add_people": [
                {
                    "full_name": "CP02 Temp Coordinator",
                    "role": "coordinator",
                    "home_base_location_id": location_id,
                    "cost_per_hour": "72.00",
                    "available_from": planned_start,
                    "available_to": planned_end,
                }
            ],
            "idempotency_key": "cp02-resolve-augment-0001",
        },
    )
    assert resolved.status_code == 200
    payload = resolved.json()
    assert len(payload["created_people_ids"]) == 1
    assert payload["generated_plan"]["is_fully_assigned"] is True


def test_phase8_cp02_resolve_gaps_reschedule_reruns_planner(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP02 Resolve Reschedule Client",
        location_name="Phase8 CP02 Resolve Reschedule Venue",
        event_name="Phase8 CP02 Resolve Reschedule Event",
        days=54,
    )
    req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": "1",
        },
    )
    assert req.status_code == 201

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "CP02 Reschedule Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "58.00",
        },
    )
    assert person.status_code == 201

    old_start_dt = datetime.fromisoformat(planned_start)
    old_end_dt = datetime.fromisoformat(planned_end)
    new_start_dt = old_start_dt + timedelta(days=2)
    new_end_dt = old_end_dt + timedelta(days=2)
    availability = api_client.post(
        f"/api/resources/people/{person.json()['person_id']}/availability",
        json={
            "available_from": new_start_dt.isoformat(),
            "available_to": new_end_dt.isoformat(),
            "is_available": True,
        },
    )
    assert availability.status_code == 201

    before = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": event_id, "commit_to_assignments": False},
    )
    assert before.status_code == 200
    assert before.json()["is_fully_assigned"] is False

    resolved = api_client.post(
        f"/api/planner/resolve-gaps/{event_id}",
        json={
            "strategy": "reschedule_event",
            "new_planned_start": new_start_dt.isoformat(),
            "new_planned_end": new_end_dt.isoformat(),
            "commit_to_assignments": True,
            "idempotency_key": "cp02-resolve-reschedule-0001",
        },
    )
    assert resolved.status_code == 200
    payload = resolved.json()
    assert payload["updated_event_window_start"] is not None
    assert payload["updated_event_window_end"] is not None
    assert payload["generated_plan"]["is_fully_assigned"] is True


def test_phase8_cp02_replan_preserves_only_consumed_transport_legs(
    api_client: TestClient,
) -> None:
    _, event_location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP02 Transport Freeze Client",
        location_name="Phase8 CP02 Event Venue",
        event_name="Phase8 CP02 Transport Freeze Event",
        days=55,
    )
    warehouse = api_client.post(
        "/api/locations",
        json={"name": "Phase8 CP02 Warehouse", "city": "Warsaw"},
    )
    assert warehouse.status_code == 201
    warehouse_id = warehouse.json()["location_id"]

    requirement = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "vehicle_type",
            "vehicle_type_required": "van",
            "quantity": "2",
        },
    )
    assert requirement.status_code == 201
    requirement_id = requirement.json()["requirement_id"]

    vehicle_1 = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "CP02 Freeze Van 1",
            "vehicle_type": "van",
            "home_location_id": warehouse_id,
            "cost_per_hour": "120.00",
        },
    )
    vehicle_2 = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "CP02 Freeze Van 2",
            "vehicle_type": "van",
            "home_location_id": warehouse_id,
            "cost_per_hour": "60.00",
        },
    )
    assert vehicle_1.status_code == 201
    assert vehicle_2.status_code == 201
    v1_id = vehicle_1.json()["vehicle_id"]
    v2_id = vehicle_2.json()["vehicle_id"]

    for vehicle_id in (v1_id, v2_id):
        availability = api_client.post(
            f"/api/resources/vehicles/{vehicle_id}/availability",
            json={
                "available_from": planned_start,
                "available_to": planned_end,
                "is_available": True,
            },
        )
        assert availability.status_code == 201

    baseline = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": event_id, "commit_to_assignments": True},
    )
    assert baseline.status_code == 200
    baseline_payload = baseline.json()
    assert len(baseline_payload["transport_leg_ids"]) == 2

    checkpoint = api_client.post(
        f"/api/runtime/events/{event_id}/checkpoint",
        json={
            "resource_type": "vehicle",
            "vehicle_id": v1_id,
            "checkpoint_type": "transport_started",
            "author_type": "coordinator",
        },
    )
    assert checkpoint.status_code == 200

    req_patch = api_client.patch(
        f"/api/events/{event_id}/requirements/{requirement_id}",
        json={"quantity": "1"},
    )
    assert req_patch.status_code == 200

    replan = api_client.post(
        f"/api/planner/replan/{event_id}",
        json={
            "incident_summary": "Keep consumed vehicle leg only.",
            "commit_to_assignments": True,
            "preserve_consumed_resources": True,
        },
    )
    assert replan.status_code == 200
    replan_payload = replan.json()
    assignment = next(
        item
        for item in replan_payload["generated_plan"]["assignments"]
        if item["requirement_id"] == requirement_id
    )
    assert v1_id in assignment["resource_ids"]
    assert len(replan_payload["generated_plan"]["transport_leg_ids"]) == 1
