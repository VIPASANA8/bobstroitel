#!/bin/sh
# Pull the deployed branch and restart what changed.
#
# The deploy key is read-only, so this host can only ever move forward to what
# is already on the remote. A dirty working tree is not a merge to resolve here:
# reset is deliberate, the server is not where anybody edits.
set -e
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
curl -fsS -o /dev/null -w 'ready:%{http_code}\n' http://127.0.0.1:8000/health/ready
