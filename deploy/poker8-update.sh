#!/bin/sh
# Pull the deployed branch and restart what changed.
#
# The deploy key is read-only, so this host can only ever move forward to what
# is already on the remote. A dirty working tree is not a merge to resolve here:
# reset is deliberate, the server is not where anybody edits.
set -e
DOMAIN=${1:-donbass.win}
BRANCH=$(git -C /opt/poker8 rev-parse --abbrev-ref HEAD)
cd /opt/poker8
git fetch --depth 1 -q origin
BEFORE=$(git rev-parse HEAD)
git reset --hard -q "origin/$BRANCH"
AFTER=$(git rev-parse HEAD)
echo "$BEFORE -> $AFTER"
[ "$BEFORE" = "$AFTER" ] && echo "nothing new" || true
docker compose -f compose.pilot.yaml -f deploy/compose.caddy.yaml up -d --build
sleep 15
# app публикует 8000 только внутрь сети compose — проверка идёт через Caddy
curl -fsS -o /dev/null -w 'ready:%{http_code}\n' "https://$DOMAIN/health/ready"
