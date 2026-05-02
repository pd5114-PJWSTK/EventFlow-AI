from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import future_window


def _seed_real_training_events(api_client: TestClient, *, count: int) -> None:
    client = api_client.post(
        "/api/clients",
        json={"name": "Phase7 CP08 Training Client", "priority": "medium"},
    )
    location = api_client.post(
        "/api/locations",
        json={
            "name": "Phase7 CP08 Training Venue",
            "city": "Warsaw",
            "setup_complexity_score": 6,
            "access_difficulty": 3,
            "parking_difficulty": 3,
        },
    )
    equipment_type = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": "Phase7 CP08 Training Rack"},
    )
    assert client.status_code == 201
    assert location.status_code == 201
    assert equipment_type.status_code == 201
    client_id = client.json()["client_id"]
    location_id = location.json()["location_id"]
    equipment_type_id = equipment_type.json()["equipment_type_id"]

    for idx in range(count):
        planned_start, planned_end = future_window(hours=4 + (idx % 3), days=200 + idx)
        attendee_count = 70 + (idx * 8)
        event = api_client.post(
            "/api/events",
            json={
                "client_id": client_id,
                "location_id": location_id,
                "event_name": f"Phase7 CP08 Train Event {idx}",
                "event_type": "conference",
                "event_subtype": "touring",
                "attendee_count": attendee_count,
                "planned_start": planned_start,
                "planned_end": planned_end,
                "priority": ["low", "medium", "high", "critical"][idx % 4],
                "requires_transport": idx % 2 == 0,
                "requires_setup": True,
                "requires_teardown": idx % 3 != 0,
            },
        )
        assert event.status_code == 201
        event_id = event.json()["event_id"]

        person_req = api_client.post(
            f"/api/events/{event_id}/requirements",
            json={
                "requirement_type": "person_role",
                "role_required": "coordinator",
                "quantity": str(1 + (idx % 3)),
            },
        )
        assert person_req.status_code == 201

        if (idx % 3) > 0:
            equipment_req = api_client.post(
                f"/api/events/{event_id}/requirements",
                json={
                    "requirement_type": "equipment_type",
                    "equipment_type_id": equipment_type_id,
                    "quantity": str(idx % 3),
                },
            )
            assert equipment_req.status_code == 201

        if (idx % 2) > 0:
            vehicle_req = api_client.post(
                f"/api/events/{event_id}/requirements",
                json={
                    "requirement_type": "vehicle_type",
                    "vehicle_type_required": "van",
                    "quantity": str(idx % 2),
                },
            )
            assert vehicle_req.status_code == 201

        features = api_client.post(
            "/api/ml/features/generate",
            json={"event_id": event_id, "include_resource_features": False},
        )
        assert features.status_code == 200

        duration_minutes = int(
            80
            + attendee_count * 0.22
            + (idx % 5) * 13
            + (idx % 4) * 7
            + (idx % 3) * 6
            + (idx % 2) * 22
        )
        start_at = datetime(2026, 8, 1, 8, 0, 0) + timedelta(hours=idx * 2)
        complete_at = start_at + timedelta(minutes=duration_minutes)
        start = api_client.post(
            f"/api/runtime/events/{event_id}/start",
            json={"started_at": start_at.isoformat(), "phase_name": "event_runtime"},
        )
        complete = api_client.post(
            f"/api/runtime/events/{event_id}/complete",
            json={"completed_at": complete_at.isoformat(), "phase_name": "event_runtime"},
        )
        assert start.status_code == 200
        assert complete.status_code == 200


def _train_models_for_cp08(api_client: TestClient) -> tuple[str, str]:
    _seed_real_training_events(api_client, count=60)
    duration_model = api_client.post(
        "/api/ml/models/harden-duration",
        json={
            "model_name": "event_duration_hardened_cp08",
            "required_real_samples": 60,
            "train_samples": 50,
            "test_samples": 10,
            "random_seed": 42,
        },
    )
    assert duration_model.status_code == 200

    evaluator = api_client.post(
        "/api/ml/models/train-plan-evaluator",
        json={"required_real_samples": 60},
    )
    assert evaluator.status_code == 200
    return duration_model.json()["model"]["model_id"], evaluator.json()["model"]["model_id"]


def _ensure_event_resources(api_client: TestClient, *, event_id: str) -> None:
    event = api_client.get(f"/api/events/{event_id}")
    assert event.status_code == 200
    event_payload = event.json()
    planned_start = event_payload["planned_start"]
    planned_end = event_payload["planned_end"]
    location_id = event_payload["location_id"]

    people_payloads = (
        {
            "full_name": "CP08 Coordinator A",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "90.00",
            "reliability_notes": "high reliability",
        },
        {
            "full_name": "CP08 Coordinator B",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "72.00",
            "reliability_notes": "medium reliability",
        },
        {
            "full_name": "CP08 Driver",
            "role": "driver",
            "home_base_location_id": location_id,
            "cost_per_hour": "65.00",
            "reliability_notes": "high reliability",
        },
    )
    person_ids: list[str] = []
    for payload in people_payloads:
        person = api_client.post("/api/resources/people", json=payload)
        assert person.status_code == 201
        person_ids.append(person.json()["person_id"])

    equipment_types = api_client.get("/api/resources/equipment-types?limit=100")
    assert equipment_types.status_code == 200
    generic = next(
        (
            item
            for item in equipment_types.json()["items"]
            if str(item["type_name"]).strip().lower() == "generic"
        ),
        None,
    )
    if generic is None:
        created = api_client.post(
            "/api/resources/equipment-types",
            json={"type_name": "Generic"},
        )
        assert created.status_code == 201
        equipment_type_id = created.json()["equipment_type_id"]
    else:
        equipment_type_id = generic["equipment_type_id"]

    equipment = api_client.post(
        "/api/resources/equipment",
        json={
            "equipment_type_id": equipment_type_id,
            "warehouse_location_id": location_id,
            "hourly_cost_estimate": "55.00",
        },
    )
    assert equipment.status_code == 201
    equipment_id = equipment.json()["equipment_id"]

    vehicle = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "CP08 Van",
            "vehicle_type": "van",
            "home_location_id": location_id,
            "cost_per_hour": "85.00",
            "cost_per_km": "1.20",
        },
    )
    assert vehicle.status_code == 201
    vehicle_id = vehicle.json()["vehicle_id"]

    for person_id in person_ids:
        availability = api_client.post(
            f"/api/resources/people/{person_id}/availability",
            json={
                "available_from": planned_start,
                "available_to": planned_end,
                "is_available": True,
            },
        )
        assert availability.status_code == 201

    equipment_availability = api_client.post(
        f"/api/resources/equipment/{equipment_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert equipment_availability.status_code == 201

    vehicle_availability = api_client.post(
        f"/api/resources/vehicles/{vehicle_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert vehicle_availability.status_code == 201


def _start_and_complete_event(api_client: TestClient, *, event_id: str, note: str) -> None:
    started_at = datetime.utcnow().replace(microsecond=0)
    completed_at = started_at + timedelta(hours=7, minutes=20)

    start = api_client.post(
        f"/api/runtime/events/{event_id}/start",
        json={"started_at": started_at.isoformat(), "phase_name": "event_runtime"},
    )
    assert start.status_code == 200

    complete = api_client.post(
        f"/api/runtime/events/{event_id}/complete",
        json={
            "completed_at": completed_at.isoformat(),
            "phase_name": "event_runtime",
            "finished_on_time": True,
            "total_delay_minutes": 0,
            "actual_cost": "21500.00",
            "transport_cost": "2200.00",
            "sla_breached": False,
            "summary_notes": note,
        },
    )
    assert complete.status_code == 200


def _ingest_event(api_client: TestClient, *, raw_input: str) -> str:
    response = api_client.post(
        "/api/ai-agents/ingest-event",
        json={
            "raw_input": raw_input,
            "initiated_by": "pytest-cp08",
            "prefer_langgraph": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"]
    assert payload["parser_mode"] in {"hybrid_llm", "deterministic_fallback", "deterministic"}
    return payload["event_id"]


def test_phase7_cp08_two_realistic_scenarios_end_to_end(api_client: TestClient) -> None:
    duration_model_id, plan_evaluator_model_id = _train_models_for_cp08(api_client)

    # Scenario 1: New event ingest -> planner -> optimize -> accept best -> completion log.
    event_id_1 = _ingest_event(
        api_client,
        raw_input=(
            "client_name: BrightWave Events\n"
            "client_priority: high\n"
            "location_name: Expo Arena\n"
            "city: Warsaw\n"
            "location_type: conference_center\n"
            "setup_complexity: 7\n"
            "access_difficulty: 3\n"
            "parking_difficulty: 2\n"
            "event_name: Product Launch 2026\n"
            "event_type: conference\n"
            "event_subtype: touring\n"
            "attendee_count: 420\n"
            "planned_start: 2026-11-15 09:00\n"
            "planned_end: 2026-11-15 18:00\n"
            "event_priority: high\n"
            "budget_estimate: 85000\n"
            "requires_transport: true\n"
            "requires_setup: true\n"
            "requires_teardown: true\n"
            "requirement_person_coordinator: 2\n"
            "requirement_person_driver: 1\n"
            "requirement_vehicle_van: 1\n"
            "requirement_equipment_generic: 1"
        ),
    )
    _ensure_event_resources(api_client, event_id=event_id_1)

    features_1 = api_client.post(
        "/api/ml/features/generate",
        json={"event_id": event_id_1, "include_resource_features": False},
    )
    assert features_1.status_code == 200

    recommended_1 = api_client.post(
        "/api/planner/recommend-best-plan",
        json={
            "event_id": event_id_1,
            "commit_to_assignments": True,
            "duration_model_id": duration_model_id,
            "plan_evaluator_model_id": plan_evaluator_model_id,
            "initiated_by": "pytest-cp08-s1",
        },
    )
    assert recommended_1.status_code == 200
    recommendation_payload_1 = recommended_1.json()
    assert recommendation_payload_1["selected_candidate_name"]
    assert recommendation_payload_1["selected_explanation"]
    assert len(recommendation_payload_1["candidates"]) == 4

    _start_and_complete_event(
        api_client,
        event_id=event_id_1,
        note="Scenario 1 complete: accepted best plan and finished without SLA breach.",
    )
    event_after_s1 = api_client.get(f"/api/events/{event_id_1}")
    assert event_after_s1.status_code == 200
    assert event_after_s1.json()["status"] == "completed"

    notifications_1 = api_client.get(f"/api/runtime/events/{event_id_1}/notifications")
    assert notifications_1.status_code == 200
    notification_types_1 = [item["notification_type"] for item in notifications_1.json()["items"]]
    assert "event_completed" in notification_types_1

    # Scenario 2: Live incident log -> replan with optimization -> choose changed plan -> completion.
    event_id_2 = _ingest_event(
        api_client,
        raw_input=(
            "client_name: NovaStage\n"
            "client_priority: critical\n"
            "location_name: Arena North\n"
            "city: Gdansk\n"
            "location_type: conference_center\n"
            "setup_complexity: 8\n"
            "access_difficulty: 4\n"
            "parking_difficulty: 4\n"
            "event_name: Winter Expo 2026\n"
            "event_type: conference\n"
            "event_subtype: festival\n"
            "attendee_count: 650\n"
            "planned_start: 2026-12-04 08:30\n"
            "planned_end: 2026-12-04 20:30\n"
            "event_priority: critical\n"
            "budget_estimate: 120000\n"
            "requires_transport: true\n"
            "requires_setup: true\n"
            "requires_teardown: true\n"
            "requirement_person_coordinator: 2\n"
            "requirement_person_driver: 1\n"
            "requirement_vehicle_van: 1\n"
            "requirement_equipment_generic: 1"
        ),
    )
    _ensure_event_resources(api_client, event_id=event_id_2)

    features_2 = api_client.post(
        "/api/ml/features/generate",
        json={"event_id": event_id_2, "include_resource_features": False},
    )
    assert features_2.status_code == 200

    baseline_2 = api_client.post(
        "/api/planner/recommend-best-plan",
        json={
            "event_id": event_id_2,
            "commit_to_assignments": True,
            "duration_model_id": duration_model_id,
            "plan_evaluator_model_id": plan_evaluator_model_id,
            "initiated_by": "pytest-cp08-s2-baseline",
        },
    )
    assert baseline_2.status_code == 200

    start_2 = api_client.post(
        f"/api/runtime/events/{event_id_2}/start",
        json={"started_at": datetime.utcnow().replace(microsecond=0).isoformat()},
    )
    assert start_2.status_code == 200

    incident_2 = api_client.post(
        f"/api/runtime/events/{event_id_2}/incident/parse",
        json={
            "raw_log": (
                "Awaria audio console przy scenie glownej. "
                "reported by: koordynator Anna. "
                "powod: uszkodzone zasilanie. "
                "krytyczne opoznienie i ryzyko SLA, koszt 3500 PLN."
            ),
            "prefer_llm": False,
            "author_type": "coordinator",
            "author_reference": "anna.k",
        },
    )
    assert incident_2.status_code == 200
    incident_payload = incident_2.json()
    assert incident_payload["incident_id"]
    assert incident_payload["parser_mode"] == "heuristic"

    replan_2 = api_client.post(
        f"/api/planner/replan/{event_id_2}",
        json={
            "incident_id": incident_payload["incident_id"],
            "incident_summary": "Awaria audio console - wymagany alternatywny plan.",
            "initiated_by": "pytest-cp08-s2",
            "commit_to_assignments": True,
        },
    )
    assert replan_2.status_code == 200
    replan_payload = replan_2.json()
    assert replan_payload["generated_plan"]["event_id"] == event_id_2
    assert replan_payload["comparison"]["decision_note"]

    complete_2 = api_client.post(
        f"/api/runtime/events/{event_id_2}/complete",
        json={
            "completed_at": (datetime.utcnow() + timedelta(hours=10)).replace(
                microsecond=0
            ).isoformat(),
            "phase_name": "event_runtime",
            "finished_on_time": False,
            "total_delay_minutes": 35,
            "actual_cost": "31200.00",
            "transport_cost": "3450.00",
            "sla_breached": False,
            "summary_notes": "Scenario 2 complete: incident handled and replanned plan executed.",
        },
    )
    assert complete_2.status_code == 200

    event_after_s2 = api_client.get(f"/api/events/{event_id_2}")
    assert event_after_s2.status_code == 200
    assert event_after_s2.json()["status"] == "completed"

    notifications_2 = api_client.get(f"/api/runtime/events/{event_id_2}/notifications")
    assert notifications_2.status_code == 200
    notification_types_2 = [item["notification_type"] for item in notifications_2.json()["items"]]
    assert "incident_reported" in notification_types_2
    assert "replan_completed" in notification_types_2
    assert "event_completed" in notification_types_2
