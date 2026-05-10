#!/usr/bin/env sh
set -eu

if [ "${1:-}" = "" ]; then
  echo "Usage: scripts/ops/restore-postgres.sh ./backups/eventflow_YYYYMMDDTHHMMSSZ.dump" >&2
  exit 2
fi

BACKUP_FILE="$1"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.vps.yml}"
DB_SERVICE="${DB_SERVICE:-postgres}"
DB_USER="${POSTGRES_USER:-eventflow}"
DB_NAME="${POSTGRES_DB:-eventflow}"
CONTAINER_FILE="/tmp/eventflow_restore.dump"

docker compose -f "$COMPOSE_FILE" cp "$BACKUP_FILE" "${DB_SERVICE}:${CONTAINER_FILE}"
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
  pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner "$CONTAINER_FILE"

echo "Restore completed from $BACKUP_FILE"
