#!/usr/bin/env bash
set -euo pipefail

DATE="$(date +%F)"
BACKUP_DIR="/opt/backups/transcript-app"
mkdir -p "$BACKUP_DIR"

if [[ -f /opt/transcript-app/data/transcript.db ]]; then
  sqlite3 /opt/transcript-app/data/transcript.db ".dump" >"$BACKUP_DIR/db-$DATE.sql"
fi
tar -czf "$BACKUP_DIR/outputs-$DATE.tar.gz" -C /opt/transcript-app/data outputs
find "$BACKUP_DIR" -type f -mtime +7 -delete

if [[ -n "${BACKUP_REMOTE:-}" ]]; then
  rsync -az "$BACKUP_DIR/" "$BACKUP_REMOTE"
fi
echo "Backup complete: $BACKUP_DIR"

