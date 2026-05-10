from __future__ import annotations

from pathlib import Path


def test_phase8_frontend_cp06_security_report_moved_to_docs_reports() -> None:
    assert not Path("Security_check.md").exists()
    assert Path("docs/reports/Security_check.md").exists()


def test_phase8_frontend_cp06_operational_seed_keeps_database_state_and_adds_company_resources() -> None:
    patch = Path("scripts/sql/production_upgrade.sql").read_text(encoding="utf-8")
    cp06_section = patch.split("-- Source: scripts\\sql\\cp06_operational_company_seed.sql", 1)[1]

    assert "Safe to re-run" in cp06_section
    assert "operational_seed_cp06" in cp06_section
    assert "resources_people" in cp06_section
    assert "core.equipment" in cp06_section
    assert "core.vehicles" in cp06_section
    assert "OP-001" in cp06_section
    assert "TRAIN-" not in cp06_section
    assert "DROP TABLE" not in cp06_section.upper()
    assert "TRUNCATE" not in cp06_section.upper()
