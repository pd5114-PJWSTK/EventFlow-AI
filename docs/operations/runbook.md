# Production Runbook

## Basic Triage

```bash
docker compose -f docker-compose.vps.yml ps
docker compose -f docker-compose.vps.yml logs --tail=200 backend
docker compose -f docker-compose.vps.yml logs --tail=200 celery-worker
curl http://127.0.0.1/health
curl http://127.0.0.1/ready
```

Use `GET /api/ops/monitoring` from an admin session for database, Redis and Celery status.

## LLM Problems

- If event parsing falls back to heuristic mode, check `AI_AZURE_LLM_ENABLED`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` and `AZURE_DEPLOYMENT_LLM`.
- If Azure limits are reached, keep the app running in fallback mode and retry later.
- Never commit Azure keys; rotate leaked keys in Azure before redeploying.

## Planner Or Replan Errors

- Check backend logs for the failing `event_id`.
- Verify the event has requirements and available resources.
- Re-run with `commit_to_assignments=false` first if assignment state is unclear.
- If only one event is affected, correct its requirements/resources from the admin UI and retry.

## Database Problems

- Check `docker compose -f docker-compose.vps.yml logs postgres`.
- Verify disk space with `df -h`.
- Restore from the latest tested dump only after stopping traffic.

## Rollback

- Use the release checklist in `docs/operations/release_rollback.md`.
- Restore the previous image/commit and then restore DB only if the release included incompatible data changes.
