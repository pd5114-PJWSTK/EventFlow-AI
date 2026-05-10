from __future__ import annotations

from pathlib import Path


def test_phase8_frontend_cp07_cleanup_patch_preserves_db_state_and_adds_live_events() -> None:
    patch = Path("scripts/sql/production_upgrade.sql").read_text(encoding="utf-8")

    assert "safe to re-run" in patch.lower()
    assert "'in_progress'::core.event_status" in patch
    assert "'planned'::core.event_status" in patch
    assert "'completed'::core.event_status" in patch
    assert "DROP TABLE" not in patch.upper()
    assert "TRUNCATE" not in patch.upper()


def test_phase8_frontend_cp07_start_script_applies_cleanup_patch() -> None:
    script = Path("scripts/start-local-test-env.ps1").read_text(encoding="utf-8")

    assert "production_upgrade.sql" in script


def test_phase8_frontend_cp07_planner_contract_accepts_assignment_overrides() -> None:
    schema = Path("app/schemas/planner.py").read_text(encoding="utf-8")
    api = Path("app/api/planner.py").read_text(encoding="utf-8")
    service = Path("app/services/planner_generation_service.py").read_text(encoding="utf-8")

    assert "class AssignmentOverride" in schema
    assert "assignment_overrides" in api
    assert "_apply_assignment_overrides" in service
