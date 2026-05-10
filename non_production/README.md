# Non-Production Archive

This directory is intentionally kept in GitHub but excluded from Docker builds and default test discovery.

Contents:

- `legacy_frontend_json_console/`: old technical JSON console replaced by the operational frontend.
- `checkpoint_sql/`: original CP-03 to CP-08 SQL patches consolidated into `scripts/sql/production_upgrade.sql`.
- `checkpoint_tests/`: historical checkpoint tests archived after production test consolidation.
- `helper_scripts/`: one-off maintenance scripts that are not needed for VPS runtime.
