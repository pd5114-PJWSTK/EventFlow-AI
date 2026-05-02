from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def _as_utc(dt_text: str) -> datetime:
    parsed = datetime.fromisoformat(dt_text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def test_phase8_cp03_preview_gaps_contract(api_client: TestClient) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase8 CP03 Preview Client",
        location_name="Phase8 CP03 Preview Venue",
        event_name="Phase8 CP03 Preview Event",
        days=56,
    )
    req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": "2",
        },
    )
    assert req.status_code == 201

    preview = api_client.post(
        f"/api/planner/preview-gaps/{event_id}",
        json={"initiated_by": "cp03-preview"},
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["event_id"] == event_id
    assert payload["contract_version"] == "cp03.v1"
    assert payload["generated_plan"]["gap_resolution"] is not None
    assert payload["generated_plan"]["gap_resolution"]["has_gaps"] is True


def test_phase8_cp03_resolve_gaps_idempotent_replay(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP03 Resolve Idem Client",
        location_name="Phase8 CP03 Resolve Idem Venue",
        event_name="Phase8 CP03 Resolve Idem Event",
        days=57,
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

    payload = {
        "strategy": "augment_resources",
        "add_people": [
            {
                "full_name": "CP03 Temp Coordinator",
                "role": "coordinator",
                "home_base_location_id": location_id,
                "available_from": planned_start,
                "available_to": planned_end,
            }
        ],
        "idempotency_key": "cp03-resolve-idem-0001",
    }
    first = api_client.post(f"/api/planner/resolve-gaps/{event_id}", json=payload)
    assert first.status_code == 200
    second = api_client.post(f"/api/planner/resolve-gaps/{event_id}", json=payload)
    assert second.status_code == 200
    assert second.headers.get("x-idempotency-replayed") == "true"
    assert first.json()["generated_plan"]["planner_run_id"] == second.json()["generated_plan"]["planner_run_id"]


def test_phase8_cp03_resolve_reschedule_updates_window(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP03 Reschedule Client",
        location_name="Phase8 CP03 Reschedule Venue",
        event_name="Phase8 CP03 Reschedule Event",
        days=58,
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
            "full_name": "CP03 Reschedule Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "55.00",
        },
    )
    assert person.status_code == 201

    old_start = datetime.fromisoformat(planned_start)
    old_end = datetime.fromisoformat(planned_end)
    new_start = old_start + timedelta(days=3)
    new_end = old_end + timedelta(days=3)

    availability = api_client.post(
        f"/api/resources/people/{person.json()['person_id']}/availability",
        json={
            "available_from": new_start.isoformat(),
            "available_to": new_end.isoformat(),
            "is_available": True,
        },
    )
    assert availability.status_code == 201

    resolved = api_client.post(
        f"/api/planner/resolve-gaps/{event_id}",
        json={
            "strategy": "reschedule_event",
            "new_planned_start": new_start.isoformat(),
            "new_planned_end": new_end.isoformat(),
            "idempotency_key": "cp03-reschedule-0001",
        },
    )
    assert resolved.status_code == 200
    payload = resolved.json()
    assert payload["updated_event_window_start"] is not None
    assert payload["updated_event_window_end"] is not None
    assert payload["decision_summary"] != ""
    assert payload["generated_plan"]["is_fully_assigned"] is True

    event = api_client.get(f"/api/events/{event_id}")
    assert event.status_code == 200
    event_start = _as_utc(event.json()["planned_start"])
    event_end = _as_utc(event.json()["planned_end"])
    payload_start = _as_utc(payload["updated_event_window_start"])
    payload_end = _as_utc(payload["updated_event_window_end"])
    assert event_start == payload_start
    assert event_end == payload_end
