# EventFlow Workflows

This document is the production handoff map for the business flows exposed by the API and frontend.

## API Surface

- Development Swagger: `http://127.0.0.1:8000/docs` when `APP_ENV=development` and `API_DOCS_ENABLED=true`.
- Production health: `GET /health`.
- Production readiness: `GET /ready`.
- Admin monitoring: `GET /api/ops/monitoring`.

## Auth And Sessions

- Login uses `POST /auth/login` and returns access and refresh tokens.
- The frontend refreshes sessions through `POST /auth/refresh`.
- `GET /auth/me` is the source of the current user, roles and account status.
- Production must keep `API_DOCS_ENABLED=false`, `API_TEST_JOBS_ENABLED=false` and `DEMO_ADMIN_ENABLED=false`.

## Event Intake

- Admin enters a natural language event description.
- Frontend calls `POST /api/ai-agents/ingest-event/preview`.
- The returned sheet is validated by the operator; missing business fields stay editable.
- Commit uses `POST /api/ai-agents/ingest-event/commit`.
- LLM mode is enabled only when `AI_AZURE_LLM_ENABLED=true` and Azure credentials are present.

## Planning

- Future unplanned events are loaded from `GET /api/events`.
- Baseline plan is generated with `POST /api/planner/generate-plan`.
- Optimized plan is generated with `POST /api/planner/recommend-best-plan`.
- Operator assignment overrides are submitted with the selected plan, so the final event has explicit resources.

## Live Replanning

- Operator chooses a live or future event.
- Incident text is parsed through `POST /api/runtime/events/{event_id}/incident/parse`.
- Replanning uses `POST /api/planner/replan/{event_id}`.
- Operator actions can add, swap or annotate resources; committed actions affect assignments and cost comparison.

## Post-Event Log

- Completed events are selected from `GET /api/events`.
- Summary text is parsed through `POST /api/runtime/events/{event_id}/post-event/parse`.
- Validated completion is committed through `POST /api/runtime/events/{event_id}/post-event/commit`.
- Completion data feeds future ML training.

## ML Retrain

- Admin starts retraining from My Account.
- Backend uses current database records and configured train/test split.
- `POST /api/ml/models/retrain-duration` promotes the new model only when guardrails pass, unless an admin forced activation.
