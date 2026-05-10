#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.vps.yml}"
DB_SERVICE="${DB_SERVICE:-postgres}"
DB_USER="${POSTGRES_USER:-eventflow}"
DB_NAME="${POSTGRES_DB:-eventflow}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${BACKUP_DIR}/eventflow_${STAMP}.dump"

mkdir -p "$BACKUP_DIR"
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$OUT_FILE"

echo "Backup written to $OUT_FILE"
