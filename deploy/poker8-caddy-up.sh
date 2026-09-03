#!/bin/sh
# Put Caddy in front of the pilot, but only once the domain actually points here.
#
# Firing the ACME challenge at a hostname that resolves somewhere else burns
# Let's Encrypt failure budget for nothing, so the DNS check is a gate, not a
# warning.
set -e
DOMAIN=${1:-donbass.win}
HERE=$(curl -fsS --max-time 10 https://api.ipify.org)
THERE=$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1)

echo "$DOMAIN -> ${THERE:-<no A record>}; this server -> $HERE"
if [ "$THERE" != "$HERE" ]; then
    echo "REFUSING: $DOMAIN does not point at this server. Caddy not started."
    exit 1
fi

cd /opt/poker8
docker compose -f compose.pilot.yaml -f deploy/compose.caddy.yaml up -d
sleep 20
docker compose -f compose.pilot.yaml -f deploy/compose.caddy.yaml logs caddy 2>&1 | tail -5
curl -fsS -o /dev/null -w "https ready:%{http_code}\n" "https://$DOMAIN/health/ready"
