# Backup And Restore

## Backup

Run on the VPS from the repository root:

```bash
BACKUP_DIR=/opt/eventflow/backups scripts/ops/backup-postgres.sh
```

The script writes a compressed PostgreSQL custom dump named `eventflow_YYYYMMDDTHHMMSSZ.dump`.

## Restore

Stop traffic to the application first. Then run:

```bash
scripts/ops/restore-postgres.sh /opt/eventflow/backups/eventflow_YYYYMMDDTHHMMSSZ.dump
```

After restore:

```bash
docker compose -f docker-compose.vps.yml restart backend celery-worker celery-beat
curl http://127.0.0.1/ready
```

## Policy

- Keep at least seven daily backups and four weekly backups.
- Copy backups off the VPS after every release.
- Test restore on a staging VM before relying on a backup policy.
