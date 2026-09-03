#!/bin/sh
# Daily dump of the pilot database, kept for a week.
#
# A dump nobody restores is a hope, not a backup: prove restores with
# tools/cash_backup_restore_check.py against a test host, not against this one.
set -e
cd /opt/poker8
docker compose -f compose.pilot.yaml exec -T postgres \
    pg_dump -U poker8 poker8 | gzip > "/var/backups/poker8/poker8-$(date -u +%F-%H%M).sql.gz"
find /var/backups/poker8 -name 'poker8-*.sql.gz' -mtime +7 -delete

# A backup on the machine it protects is not a backup: the host dies and takes
# it along. Set POKER8_BACKUP_DEST to an scp target (user@host:/path) with a
# key this host may use, and the newest dump goes off the box as well. Left
# unset, the dump stays local and the script says so once a day in the log.
if [ -n "${POKER8_BACKUP_DEST:-}" ]; then
    newest=$(ls -1t /var/backups/poker8/poker8-*.sql.gz | head -1)
    scp -o BatchMode=yes -q "$newest" "$POKER8_BACKUP_DEST"         && echo "$(date -u +%FT%TZ) copied $(basename "$newest") off the host"
else
    echo "$(date -u +%FT%TZ) WARNING: POKER8_BACKUP_DEST is unset, the backup never leaves this host"
fi
