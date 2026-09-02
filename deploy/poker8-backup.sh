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
