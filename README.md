# EventFlow AI

EventFlow AI is a production-oriented event operations application. It combines a FastAPI backend, PostgreSQL, Redis, Celery, a React admin frontend, Azure OpenAI assisted intake, planner/replanner workflows and ML model retraining.

## Canonical Rule

Use Docker Compose for runtime, tests and VPS validation. Do not rely on local Python, `.venv`, global `pytest`, global Node or local `npm` as the project standard. Local tools may be useful for development, but the committed workflow below is the source of truth.

## Production Shape

Runtime services:

- `backend`: FastAPI API.
- `frontend`: React build served by Nginx.
- `postgres`: persistent business data.
- `redis`: broker/cache for Celery and rate limits.
- `celery-worker`: async jobs.
- `celery-beat`: scheduled retraining and background jobs.

Main production entrypoint: `docker-compose.vps.yml`.

Non-production history, old checkpoint artifacts and legacy UI code are kept under `non_production/` and are excluded from Docker builds.

Container names are fixed in local and VPS Compose files:

- `eventflow-backend`
- `eventflow-frontend`
- `eventflow-postgres`
- `eventflow-redis`
- `eventflow-celery-worker`
- `eventflow-celery-beat`

Temporary `frontend-check` containers are used only by the quality gate and are cleaned by `scripts/run-quality-gates.ps1`.

## Local One-Command Start

Run from the repository root on Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local-test-env.ps1
```

The script starts the full application through Docker Compose, waits for `/ready`, applies `scripts/sql/production_upgrade.sql` and serves the frontend at:

```text
http://127.0.0.1:5173
```

Useful option:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local-test-env.ps1 -SkipBuild
```

Health checks:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/ready
```

Swagger is available only in development when `APP_ENV=development` and `API_DOCS_ENABLED=true`:

```text
http://127.0.0.1:8000/docs
```

## Quality Gates

Run the full backend/frontend/Docker validation through one command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-quality-gates.ps1
```

This command runs:

- `docker compose config`
- `docker compose -f docker-compose.vps.yml config`
- backend `python -m pytest -q` inside the backend Docker image
- frontend `npm ci`, `typecheck`, `lint`, `test` and `build` inside a Node Docker container

No local `.venv`, global Python or global Node is required.

## Login

For local development, set a bootstrap admin in `.env`:

```env
AUTH_BOOTSTRAP_ADMIN_USERNAME=admin
AUTH_BOOTSTRAP_ADMIN_PASSWORD=replace-with-strong-password
```

The app creates the bootstrap admin at backend startup if the user does not already exist.

## Azure LLM

Without Azure credentials the parser intentionally falls back to deterministic heuristics and the UI shows fallback mode. To use LLM parsing for event intake, live incidents and post-event logs, set:

```env
AI_AZURE_LLM_ENABLED=true
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_DEPLOYMENT_LLM=your-deployment
OPENAI_API_VERSION=2024-08-01-preview
```

Keep these values only in `.env` / `.env.production` on the machine or in your secret manager. Do not commit them.

## VPS Deployment

On the VPS:

```bash
cp .env.production.example .env.production
cp .env.production .env
nano .env

docker compose -f docker-compose.vps.yml up --build -d
docker compose -f docker-compose.vps.yml cp scripts/sql/production_upgrade.sql postgres:/tmp/production_upgrade.sql
docker compose -f docker-compose.vps.yml exec -T postgres psql -U eventflow -d eventflow -v ON_ERROR_STOP=1 -f /tmp/production_upgrade.sql
```

Verify:

```bash
curl http://127.0.0.1/health
curl http://127.0.0.1/ready
docker compose -f docker-compose.vps.yml ps
```

Full VPS instructions: `docs/operations/vps_deployment.md`.

## Operations

- Workflows and API map: `docs/architecture/workflows.md`.
- VPS deployment: `docs/operations/vps_deployment.md`.
- Backup and restore: `docs/operations/backup_restore.md`.
- Runbook: `docs/operations/runbook.md`.
- Release and rollback: `docs/operations/release_rollback.md`.
- Developer onboarding: `docs/operations/developer_onboarding.md`.

Backup command on VPS:

```bash
BACKUP_DIR=/opt/eventflow/backups scripts/ops/backup-postgres.sh
```

Restore command on VPS:

```bash
scripts/ops/restore-postgres.sh /opt/eventflow/backups/eventflow_YYYYMMDDTHHMMSSZ.dump
```

## Repository Layout

- `app/`: FastAPI backend.
- `frontend/`: React frontend.
- `docker/`: PostgreSQL schema and seed.
- `scripts/`: production scripts only.
- `scripts/sql/production_upgrade.sql`: consolidated DB upgrade patch.
- `scripts/ops/`: backup and restore scripts.
- `tests/`: active production regression tests.
- `docs/`: current documentation.
- `non_production/`: archived checkpoint and legacy artifacts, not deployed.
