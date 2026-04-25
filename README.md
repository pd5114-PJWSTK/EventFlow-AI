# EventFlow AI

Phase-based implementation of EventFlow AI with Git checkpoints per phase.

## Branch model

- `main` for stable, releasable states.
- `phase/*` for phase integration work.
- `feature/*` for incremental tasks merged into a phase branch.

## Checkpoint tags

Each phase uses this format:

- `phase-N-start`
- `phase-N-cp-XX-description`
- `phase-N-complete`

## Phase 1 scope

- Git bootstrap and tagging strategy.
- Docker services: FastAPI, PostgreSQL, Redis, Celery worker, Celery beat.
- PostgreSQL schema and seed initialization.
- FastAPI scaffold with `health` and `ready`.
- Auth baseline: login, refresh, RBAC dependency.
- Celery test task exposed by API.

## Local setup

1. Copy environment file:

   ```bash
   cp .env.example .env
   ```

2. Build and run stack:

   ```bash
   docker compose up --build
   ```

3. Verify API:

   - `GET http://localhost:8000/health`
   - `GET http://localhost:8000/ready`
   - `POST http://localhost:8000/auth/login`

## Local tests

```bash
pytest -q
```
