from __future__ import annotations

from pathlib import Path


def test_phase8_frontend_cp06_security_report_moved_to_docs_reports() -> None:
    assert not Path("Security_check.md").exists()
    assert Path("docs/reports/Security_check.md").exists()


def test_phase8_frontend_cp06_operational_seed_keeps_database_state_and_adds_company_resources() -> None:
    patch = Path("scripts/sql/cp06_operational_company_seed.sql").read_text(encoding="utf-8")

    assert "Safe to re-run" in patch
    assert "operational_seed_cp06" in patch
    assert "resources_people" in patch
    assert "core.equipment" in patch
    assert "core.vehicles" in patch
    assert "OP-001" in patch
    assert "TRAIN-" not in patch
    assert "DROP TABLE" not in patch.upper()
    assert "TRUNCATE" not in patch.upper()
