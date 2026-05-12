from __future__ import annotations

from pathlib import Path


def test_phase8_frontend_cp08_sql_uses_business_names_and_unplanned_future_statuses() -> None:
    production_patch = Path("scripts/sql/production_upgrade.sql").read_text(encoding="utf-8")
    patch = production_patch.split("-- Source: scripts\\sql\\cp08_business_event_names_and_planning_state.sql", 1)[1]
    script = Path("scripts/start-local-test-env.ps1").read_text(encoding="utf-8")

    assert "Krakow Music Night" in patch
    assert "cp08_business_event_names_and_planning_state.sql" in production_patch
    assert "'submitted'::core.event_status" in patch
    assert "'validated'::core.event_status" in patch
    assert "OP-" not in patch
    assert "production_upgrade.sql" in script


def test_phase8_frontend_cp08_frontend_hides_resource_ids_in_operational_views() -> None:
    planner = Path("frontend/src/pages/PlannerPage.tsx").read_text(encoding="utf-8")
    details = Path("frontend/src/components/EventDetailsCard.tsx").read_text(encoding="utf-8")
    intake = Path("frontend/src/pages/IntakePage.tsx").read_text(encoding="utf-8")

    assert "Baseline planning draft" in planner
    assert "Optimized plan" in planner
    assert "requirement_id.slice" not in planner
    assert "equipment type ${String" not in details
    assert "skill ${String" not in details
    assert 'label="Equipment type"' in intake and "equipmentTypes.map" in intake
    assert 'label="Skill"' in intake and "skills.map" in intake


def test_phase8_frontend_cp08_ml_retrain_can_promote_admin_training_result() -> None:
    schema = Path("app/schemas/ml_models.py").read_text(encoding="utf-8")
    api = Path("app/api/ml_models.py").read_text(encoding="utf-8")
    service = Path("app/services/ml_training_service.py").read_text(encoding="utf-8")
    me_page = Path("frontend/src/pages/MePage.tsx").read_text(encoding="utf-8")

    assert "force_activate" in schema
    assert "force_activate=payload.force_activate" in api
    assert "Activated by admin training request" in service
    assert "model.status === \"active\"" in me_page
    assert "force_activate: true" in me_page


def test_phase8_frontend_cp08_planner_scores_are_not_flattened_to_technical_ties() -> None:
    service = Path("app/services/planner_generation_service.py").read_text(encoding="utf-8")

    assert "CP-08 compares baseline" in service
    assert "profile_duration_multiplier" in service
    assert "coverage_ratio - Decimal(\"0.90\")" in service
    assert "coverage_ratio * Decimal(\"8\")" not in service
