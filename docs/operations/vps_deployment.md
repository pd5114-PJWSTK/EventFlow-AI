# VPS Deployment

## Required Files

Deploy the repository root excluding local artifacts ignored by `.dockerignore`. The production runtime needs:

- `app/`
- `frontend/`
- `docker/`
- `scripts/sql/production_upgrade.sql`
- `scripts/ops/`
- `Dockerfile`
- `docker-compose.vps.yml`
- `.env.production` created on the VPS

Do not deploy `non_production/`, `node_modules`, `.venv`, caches, local `.env` files or backups.

## Container Names

`docker-compose.vps.yml` uses fixed production container names:

- `eventflow-backend`
- `eventflow-frontend`
- `eventflow-postgres`
- `eventflow-redis`
- `eventflow-celery-worker`
- `eventflow-celery-beat`

The fixed names make VPS operations independent from the directory name chosen by Docker Compose.

## Environment

Create `.env.production` on the VPS and pass it as `.env` for Docker Compose:

```bash
cp .env.production.example .env.production
cp .env.production .env
```

Set at minimum:

```bash
POSTGRES_PASSWORD=change-this
DATABASE_URL=postgresql+psycopg://eventflow:change-this@postgres:5432/eventflow
REDIS_URL=redis://redis:6379/0
JWT_SECRET_KEY=replace-with-at-least-32-random-characters
APP_ENV=production
API_DOCS_ENABLED=false
API_TEST_JOBS_ENABLED=false
DEMO_ADMIN_ENABLED=false
AUTH_BOOTSTRAP_ADMIN_USERNAME=admin
AUTH_BOOTSTRAP_ADMIN_PASSWORD=replace-with-strong-password
```

Azure LLM is optional:

```bash
AI_AZURE_LLM_ENABLED=true
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_DEPLOYMENT_LLM=your-deployment
OPENAI_API_VERSION=2024-08-01-preview
```

## Start

```bash
docker compose -f docker-compose.vps.yml up --build -d
docker compose -f docker-compose.vps.yml cp scripts/sql/production_upgrade.sql postgres:/tmp/production_upgrade.sql
docker compose -f docker-compose.vps.yml exec -T postgres psql -U eventflow -d eventflow -v ON_ERROR_STOP=1 -f /tmp/production_upgrade.sql
```

## Verify

```bash
curl http://127.0.0.1/health
curl http://127.0.0.1/ready
docker compose -f docker-compose.vps.yml ps
docker compose -f docker-compose.vps.yml logs --tail=100 backend
```
