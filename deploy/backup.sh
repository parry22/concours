#!/usr/bin/env bash
# Nightly backup: a Postgres dump and the workspace (encrypted uploads, protected splits, model files).
# The data key is NOT in the archive on purpose: keep it in your password manager or secret store.
#   deploy/backup.sh /backups        (cron: 15 2 * * * /opt/concours/deploy/backup.sh /backups)
# Restore: docs/DEPLOY.md, "Restore".
set -euo pipefail
DEST="${1:-/backups}"
HERE="$(cd "$(dirname "$0")" && pwd)"
set -a; . "$HERE/.env"; set +a
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DEST"
docker compose -f "$HERE/docker-compose.yml" --env-file "$HERE/.env" exec -T db pg_dump -U concours -d concours --format=custom > "$DEST/concours-db-$STAMP.dump"
tar -C "$CONCOURS_DATA_ROOT" -czf "$DEST/concours-workspace-$STAMP.tgz" workspace
find "$DEST" -name 'concours-*' -mtime +14 -delete
echo "backup written to $DEST ($STAMP)"
