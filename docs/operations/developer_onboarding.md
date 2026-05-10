# Developer Onboarding

## Canonical Local Runtime

Use Docker Compose only. The project standard does not require local Python, `.venv`, global `pytest`, global Node or local `npm`.

Local runtime containers are intentionally named:

- `eventflow-backend`
- `eventflow-frontend`
- `eventflow-postgres`
- `eventflow-redis`
- `eventflow-celery-worker`
- `eventflow-celery-beat`

The quality gate may create temporary `frontend-check` containers. If a test process is interrupted, `scripts/run-quality-gates.ps1` removes stale `frontend-check` containers before and after the frontend checks.

From the repository root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local-test-env.ps1
```

The script starts the full application, waits for readiness, applies `scripts/sql/production_upgrade.sql` and serves the frontend on `http://127.0.0.1:5173`.

## Canonical Quality Gates

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-quality-gates.ps1
```

The script runs backend tests in the backend Docker image and frontend checks in a Node Docker container. It also validates local and VPS Compose files.

## Optional Manual Debugging

Manual local Python or Node commands are allowed only for debugging. They are not the project standard and should not be used as release evidence.

## Archived History

Historical checkpoint tests and SQL are archived under `non_production/` and are not part of the default production validation path.
