from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.helpers import create_event_context
from tests.test_phase7_cp04 import _seed_training_data


def _seed_person(
    api_client: TestClient,
    *,
    location_id: str,
    full_name: str,
    role: str,
    planned_start: str,
    planned_end: str,
    cost: str = "80.00",
) -> str:
    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": full_name,
            "role": role,
            "home_base_location_id": location_id,
            "cost_per_hour": cost,
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
    return person_id


def test_phase8_cp09_planner_fallback_assigns_available_resource_when_exact_match_is_missing(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP09 Fallback Client",
        location_name="Phase8 CP09 Fallback Venue",
        event_name="Phase8 CP09 Fallback Event",
        hours=4,
        days=45,
    )
    requirement = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "technician_audio",
            "quantity": "1",
        },
    )
    assert requirement.status_code == 201
    fallback_person_id = _seed_person(
        api_client,
        location_id=location_id,
        full_name="CP09 Fallback Coordinator",
        role="coordinator",
        planned_start=planned_start,
        planned_end=planned_end,
    )

    plan = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": event_id, "commit_to_assignments": False},
    )
    assert plan.status_code == 200
    assignment = plan.json()["assignments"][0]
    assert assignment["resource_ids"] == [fallback_person_id]
    assert assignment["unassigned_count"] == 0


def test_phase8_cp09_replan_operator_actions_affect_cost_and_create_manual_assignment(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase8 CP09 Replan Client",
        location_name="Phase8 CP09 Replan Venue",
        event_name="Phase8 CP09 Replan Event",
        hours=5,
        days=46,
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
    _seed_person(
        api_client,
        location_id=location_id,
        full_name="CP09 Lead Coordinator",
        role="coordinator",
        planned_start=planned_start,
        planned_end=planned_end,
        cost="70.00",
    )
    backup_person_id = _seed_person(
        api_client,
        location_id=location_id,
        full_name="CP09 Backup Technician",
        role="technician_audio",
        planned_start=planned_start,
        planned_end=planned_end,
        cost="120.00",
    )

    baseline = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": event_id, "commit_to_assignments": True},
    )
    assert baseline.status_code == 200

    replan = api_client.post(
        f"/api/planner/replan/{event_id}",
        json={
            "incident_summary": "Audio failure requires backup technician.",
            "commit_to_assignments": True,
            "idempotency_key": "cp09-replan-action-0001",
            "operator_actions": [
                {
                    "action_type": "add_resource",
                    "label": "Add backup audio technician for replacement setup.",
                    "owner": "Audio lead",
                    "status": "pending",
                    "resource_type": "person",
                    "resource_id": backup_person_id,
                }
            ],
        },
    )
    assert replan.status_code == 200
    payload = replan.json()
    assert payload["operator_actions"][0]["resource_id"] == backup_person_id
    assert payload["comparison"]["cost_delta"] is not None
    assert "Operator actions included" in payload["comparison"]["decision_note"]

    assignments = api_client.get(f"/api/events/{event_id}/assignments?limit=20")
    assert assignments.status_code == 200
    assert any(
        item["person_id"] == backup_person_id and "operator_action" in (item["assignment_role"] or "")
        for item in assignments.json()["items"]
    )


def test_phase8_cp09_force_retrain_promotes_active_model_even_when_thresholds_would_archive(
    api_client: TestClient,
) -> None:
    _seed_training_data(api_client)
    baseline = api_client.post(
        "/api/ml/models/train-baseline",
        json={"prediction_type": "duration_estimate", "activate_model": True},
    )
    assert baseline.status_code == 200
    baseline_model_id = baseline.json()["model"]["model_id"]

    retrain = api_client.post(
        "/api/ml/models/retrain-duration",
        json={
            "min_samples_required": 1,
            "min_r2_improvement": 2.0,
            "max_mae_ratio": 1.0,
            "force_activate": True,
        },
    )
    assert retrain.status_code == 200
    payload = retrain.json()
    assert payload["activated"] is True
    assert payload["model"]["status"] == "active"
    assert payload["previous_active_model_id"] == baseline_model_id
    assert "Activated by admin training request" in payload["decision_reason"]

    listed = api_client.get("/api/ml/models?prediction_type=duration_estimate")
    assert listed.status_code == 200
    active_models = [item for item in listed.json()["items"] if item["status"] == "active"]
    assert any(item["model_id"] == payload["model"]["model_id"] for item in active_models)


def test_phase8_cp09_frontend_contract_contains_structured_operator_actions_and_assigned_only_view() -> None:
    runtime = Path("frontend/src/pages/RuntimePage.tsx").read_text(encoding="utf-8")
    details = Path("frontend/src/components/EventDetailsCard.tsx").read_text(encoding="utf-8")
    schema = Path("app/schemas/planner.py").read_text(encoding="utf-8")

    assert "operator_actions" in runtime
    assert "Resource type" in runtime
    assert "Resource" in runtime
    assert "Timing actions update the replan comparison" in runtime
    assert "assignmentSummary.length > 0" not in details
    assert "class ReplanOperatorAction" in schema
