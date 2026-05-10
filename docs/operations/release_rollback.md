# Release And Rollback Checklist

## Release

- Confirm `git status` is clean.
- Run the canonical quality gate: `powershell -ExecutionPolicy Bypass -File .\scripts\run-quality-gates.ps1`.
- Build VPS images: `docker compose -f docker-compose.vps.yml build`.
- Create a database backup.
- Deploy: `docker compose -f docker-compose.vps.yml up -d --build`.
- Apply `scripts/sql/production_upgrade.sql`.
- Verify `/health`, `/ready`, login, event intake, planning, live replan and post-event log.

## Rollback

- Identify the previous Git tag or commit.
- Create a database backup of the failed state for investigation.
- Checkout the previous release.
- Rebuild and restart: `docker compose -f docker-compose.vps.yml up -d --build`.
- Restore the previous database dump only if the failed release applied incompatible DB changes.
- Verify `/ready` and the core UI workflow before reopening traffic.
