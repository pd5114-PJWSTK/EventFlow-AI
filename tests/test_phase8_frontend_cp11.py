from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.helpers import future_window


def test_cp11_ai_intake_commit_creates_validated_event(api_client: TestClient) -> None:
    preview = api_client.post(
        "/api/ai-agents/ingest-event/preview",
        json={
            "raw_input": """
            event_name: CP11 Validated Intake Event
            city: Krakow
            requirement_person_coordinator: 1
            """,
            "prefer_langgraph": False,
        },
    )
    assert preview.status_code == 200

    commit = api_client.post(
        "/api/ai-agents/ingest-event/commit",
        json={
            "draft": preview.json()["draft"],
            "assumptions": preview.json().get("assumptions", []),
            "parser_mode": preview.json().get("parser_mode", "deterministic"),
            "used_fallback": preview.json().get("used_fallback", False),
        },
    )
    assert commit.status_code == 200

    event = api_client.get(f"/api/events/{commit.json()['event_id']}")
    assert event.status_code == 200
    assert event.json()["status"] == "validated"


def test_cp11_planner_metrics_slots_and_optimized_resource_difference(api_client: TestClient) -> None:
    client = api_client.post("/api/clients", json={"name": "CP11 Planner Client", "priority": "high"})
    location = api_client.post(
        "/api/locations",
        json={
            "name": "CP11 Planner Venue",
            "city": "Krakow",
            "location_type": "conference_center",
            "setup_complexity_score": 8,
            "access_difficulty": 4,
            "parking_difficulty": 4,
        },
    )
    assert client.status_code == 201
    assert location.status_code == 201
    planned_start, planned_end = future_window(hours=9, days=90)
    event = api_client.post(
        "/api/events",
        json={
            "client_id": client.json()["client_id"],
            "location_id": location.json()["location_id"],
            "event_name": "CP11 Planner Difference Event",
            "event_type": "concert",
            "attendee_count": 850,
            "planned_start": planned_start,
            "planned_end": planned_end,
            "priority": "high",
            "status": "validated",
            "budget_estimate": "68000.00",
        },
    )
    assert event.status_code == 201
    event_id = event.json()["event_id"]

    requirement = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={"requirement_type": "person_role", "role_required": "technician_audio", "quantity": "3"},
    )
    assert requirement.status_code == 201

    people: list[tuple[str, str]] = []
    for name, cost, reliability in (
        ("CP11 Cheap Audio One", "30.00", "standard demo option"),
        ("CP11 Cheap Audio Two", "35.00", "standard demo option"),
        ("CP11 Cheap Audio Three", "40.00", "standard demo option"),
        ("CP11 Reliable Audio One", "70.00", "high reliability senior engineer"),
        ("CP11 Reliable Audio Two", "75.00", "high reliability RF specialist"),
        ("CP11 Reliable Audio Three", "80.00", "high reliability failover specialist"),
    ):
        person = api_client.post(
            "/api/resources/people",
            json={
                "full_name": name,
                "role": "technician_audio",
                "home_base_location_id": location.json()["location_id"],
                "cost_per_hour": cost,
                "reliability_notes": reliability,
                "max_daily_hours": "10.00",
                "max_weekly_hours": "44.00",
            },
        )
        assert person.status_code == 201
        people.append((person.json()["person_id"], name))
        availability = api_client.post(
            f"/api/resources/people/{person.json()['person_id']}/availability",
            json={"available_from": planned_start, "available_to": planned_end, "is_available": True},
        )
        assert availability.status_code == 201

    baseline = api_client.post("/api/planner/generate-plan", json={"event_id": event_id, "commit_to_assignments": False})
    assert baseline.status_code == 200
    recommended = api_client.post("/api/planner/recommend-best-plan", json={"event_id": event_id, "commit_to_assignments": False})
    assert recommended.status_code == 200

    baseline_payload = baseline.json()
    recommended_payload = recommended.json()
    assert set(baseline_payload["metrics"].keys()) == set(recommended_payload["optimized_metrics"].keys())
    for key in ("event_budget", "resource_cost_to_budget_ratio", "reliability_score", "backup_coverage_ratio"):
        assert key in baseline_payload["metrics"]
        assert key in recommended_payload["optimized_metrics"]
    assert len(recommended_payload["selected_plan"]["assignment_slots"]) == 3
    assert len(baseline_payload["stage_breakdown"]) == 5
    assert len(recommended_payload["selected_plan"]["stage_breakdown"]) == 5
    assert recommended_payload["business_explanation"]["summary"]
    assert recommended_payload["business_explanation"]["metric_explanations"]
    assert recommended_payload["business_explanation"]["resource_impact_summary"]
    for slot in recommended_payload["selected_plan"]["assignment_slots"]:
        selected_option = next(
            option
            for option in slot["candidate_options"]
            if option["resource_id"] == slot["selected_resource_id"]
        )
        assert slot["estimated_cost"] == selected_option["estimated_cost"]
        assert "distance_to_event_km" in selected_option
        assert "travel_time_minutes" in selected_option
        assert "logistics_cost" in selected_option
    assert recommended_payload["metric_deltas"] is not None
    assert "reliability_score" in recommended_payload["metric_deltas"]
    assert "backup_coverage_ratio" in recommended_payload["metric_deltas"]

    baseline_ids = set(baseline_payload["assignments"][0]["resource_ids"])
    optimized_ids = set(recommended_payload["selected_plan"]["assignments"][0]["resource_ids"])
    assert baseline_ids != optimized_ids

    commit = api_client.post(
        "/api/planner/recommend-best-plan",
        json={
            "event_id": event_id,
            "commit_to_assignments": True,
            "assignment_overrides": [
                {
                    "requirement_id": requirement.json()["requirement_id"],
                    "resource_type": "person",
                    "resource_ids": list(optimized_ids),
                }
            ],
        },
    )
    assert commit.status_code == 200
    event_read = api_client.get(f"/api/events/{event_id}")
    assert event_read.json()["status"] == "planned"


def test_cp11_production_upgrade_contains_demo_plan_event() -> None:
    patch = Path("scripts/sql/production_upgrade.sql").read_text(encoding="utf-8")
    assert "Demo-plan-event" in patch
    assert "source_channel" in patch
    assert "demo_cp11" in patch
    assert "current_location_id" in patch
    assert "demo_cp13" in patch
    assert "'validated'::core.event_status" in patch


def test_cp12_plan_evaluator_features_and_calibrated_seed() -> None:
    training_service = Path("app/services/ml_training_service.py").read_text(encoding="utf-8")
    planner_service = Path("app/services/planner_generation_service.py").read_text(encoding="utf-8")
    upgrade = Path("scripts/sql/production_upgrade.sql").read_text(encoding="utf-8")

    for feature_name in ("reliability_score", "backup_coverage_ratio", "resource_cost_to_budget_ratio"):
        assert feature_name in training_service
        assert feature_name in planner_service

    assert "CP-12 realistic planning calibration" in upgrade
    assert "operational_seed_cp12" in upgrade
    assert "planner cost covers assignable" in upgrade.lower()
    assert "52000.00" in upgrade
