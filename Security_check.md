# Security Check - EventFlow AI (VPS Scenario)

Date: 2026-05-03
Scope: full repository audit for planned deployment on public VPS
Method: static code/config review + dynamic local PoC

## Executive summary

Findings confirmed: 6

- P0: 1
- P1: 3
- P2: 2

Main risk theme: application is not ready for direct internet exposure in current form.

---

## [P0] Missing authentication/authorization on business API

### Evidence
- `app/main.py:23-35` includes business routers without auth dependencies.
- RBAC exists but is not connected to routers: `app/middleware/rbac.py:9-25`.
- Example exposed endpoints:
  - `app/api/ai_agents.py:24`, `app/api/ai_agents.py:47`, `app/api/ai_agents.py:72`
  - `app/api/planner.py:42`, `app/api/planner.py:63`, `app/api/planner.py:101`
  - `app/api/resources.py:90` and other CRUD routes.

### Dynamic PoC
- `POST /api/ai-agents/optimize` without `Authorization` returned `HTTP 200`.

### Impact on VPS
Remote unauthenticated actor can execute business operations immediately after exposure.

### Patch plan
1. Add mandatory auth dependency for all `/api/*` routers except health endpoints.
2. Enforce role matrix per endpoint (`manager`, `coordinator`, `technician`).
3. Add automated tests: every mutating endpoint must return `401/403` without valid token/role.
4. Protect websocket/runtime notification surfaces with same token model.

---

## [P1] Path traversal in ML artifact write path

### Evidence
- User input `model_name` accepted from API schemas:
  - `app/schemas/ml_models.py:13`, `:37`, `:58`, `:75`
- Path composed directly from `model_name`:
  - `app/services/ml_training_service.py:1447` (`model_dir = artifact_dir / model_name / model_version`)

### Dynamic PoC
- `_save_model_artifact(..., model_name="..\\poc_escape_dynamic_vps", ...)`
- Resulting file path: `C:\repos\Projekt\poc_escape_dynamic_vps\v_dynamic\model.pkl`
- `outside_models_dir = true`

### Impact on VPS
Attacker can write files outside intended model directory within process permissions.

### Patch plan
1. Validate `model_name` with strict whitelist, e.g. `^[a-zA-Z0-9_-]{1,120}$`.
2. Resolve final path and enforce prefix constraint to `ML_MODELS_DIR`.
3. Reject any path separators, `..`, absolute/UNC paths.
4. Add traversal regression tests (`../`, `..\\`, absolute path, UNC).

---

## [P1] Default credentials and weak default JWT secret

### Evidence
- Defaults in config:
  - `app/config.py:17` (`jwt_secret_key = "dev-only-secret"`)
  - `app/config.py:22-23` (`admin/admin123`)
- Example env template also carries weak defaults:
  - `.env.example:15`, `.env.example:19`, `.env.example:20`

### Dynamic PoC
- `POST /auth/login` with `admin/admin123` returned `HTTP 200` and access token.

### Impact on VPS
If defaults survive deployment, account takeover and token forgery risk is immediate.

### Patch plan
1. Remove insecure defaults from runtime config (fail-fast when missing in non-dev).
2. Enforce minimum JWT secret entropy/length at startup.
3. Disable demo account by default; enable only in explicit local dev mode.
4. Move to real user store with hashed passwords (`argon2`/`bcrypt`) and rotation policy.

---

## [P1] Publicly exposed Postgres/Redis with weak defaults in compose

### Evidence
- Open host mappings:
  - `docker-compose.yml:10` (`5432:5432`)
  - `docker-compose.yml:25` (`6379:6379`)
- Weak default DB password path:
  - `docker-compose.yml:7` (`POSTGRES_PASSWORD` fallback to `eventflow`)

### Impact on VPS
Database and queue become internet-reachable if host firewall/network rules are not strict.

### Patch plan
1. Remove host `ports` for DB/Redis in default deployment profile.
2. Use private Docker network + reverse proxy only for API ingress.
3. Enforce strong secrets in environment/secret manager.
4. Add host firewall rules (deny public access to 5432/6379).

---

## [P2] Test job API exposed in production routing

### Evidence
- Test router included in app startup: `app/main.py:25`.
- Test endpoints:
  - `app/api/test_jobs.py:16` (`POST /api/test/async-job`)
  - `app/api/test_jobs.py:25` (`GET /api/test/async-job/{task_id}`)
- No auth guard in test router.

### Impact on VPS
Public actor can abuse worker queue/test surfaces for noise, cost, or DoS-like pressure.

### Patch plan
1. Disable test router in production (`if app_env != "production"`).
2. If endpoint must exist, require admin role and strict rate limits.
3. Add CI check blocking test/debug routes in production config.

---

## [P2] Deployment hardening gaps for internet-facing VPS

### Evidence
- Backend starts with auto-reload in compose: `docker-compose.yml:51` (`--reload`).
- No app-level host/proxy hardening middleware observed in startup (`app/main.py`).
- API docs exposed by default (`/docs` returned `HTTP 200` in PoC).

### Impact on VPS
Increases attack surface and operational risk in public environment.

### Patch plan
1. Remove `--reload` in production runtime.
2. Put app behind reverse proxy (Nginx/Caddy/Traefik) with TLS and strict upstream policy.
3. Disable `/docs` and `/openapi.json` in production unless explicitly required and protected.
4. Add request rate limiting on `/auth/login`, runtime operations, and heavy AI/ML endpoints.

---

## Dynamic PoC output (2026-05-03)

```json
{
  "unauth_ai_optimize_status": 200,
  "docs_status": 200,
  "default_admin_login_status": 200,
  "default_admin_login_has_token": true,
  "path_traversal_artifact_path": "C:\\repos\\Projekt\\poc_escape_dynamic_vps\\v_dynamic\\model.pkl",
  "path_traversal_outside_models": true
}
```

---

## Recommended remediation order

1. P0 auth/authz enforcement across business API.
2. P1 path traversal fix + tests.
3. P1 secret/credential hardening.
4. P1 private network for Postgres/Redis.
5. P2 remove test routes from production and deploy hardening tasks.
