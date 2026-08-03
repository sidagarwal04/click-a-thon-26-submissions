#!/usr/bin/env bash
# Route the DEPLOYED engine's telemetry into ClickStack on mercury.
#
#   bash scripts/enable_clickstack_mercury.sh            # enable + verify
#   bash scripts/enable_clickstack_mercury.sh --off      # disable again
#   bash scripts/enable_clickstack_mercury.sh --status   # report, change nothing
#
# ClickStack is OFF by default in the engine (integrations/otel.py: no-op tracer unless
# CLICKSTACK_ENABLED=1), so deploying the code is not enough — the service needs the flag.
# This writes a systemd drop-in rather than editing the unit, so it is reversible and does
# not fight the next deploy.
#
# PRECONDITION: run scripts/deploy_mercury.sh from current main first. The engine cannot
# emit a span if integrations/otel.py is not on the box.
#
# GUARDRAIL: the collector must be ClickStack's OWN bundled ClickHouse. This script never
# passes CLICKHOUSE_* to it, and refuses to point the engine anywhere but the VM's own
# loopback — sending OTLP at the graded competition service would create otel_* tables in
# the judged database.
set -euo pipefail

HOST="${MERCURY_SSH:-mercury}"
OTLP="http://localhost:4318"          # loopback ONLY — see guardrail above
API="http://localhost:8077"
DROPIN="/etc/systemd/system/rca-api.service.d/clickstack.conf"
MODE="${1:-on}"

case "$MODE" in
  --status|--off|on|"") ;;
  *) echo "usage: $0 [--off|--status]" >&2; exit 64 ;;
esac

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "1/5  checking the box"
ssh "$HOST" bash -s <<'REMOTE'
set -u
cs=$(docker ps --format '{{.Names}}' | grep -iE 'clickstack|hyperdx' | head -1)
if [ -z "$cs" ]; then
  echo "  ✗ no ClickStack/HyperDX container running"; exit 1
fi
echo "  ✓ container: $cs"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 6 -X POST http://localhost:4318/v1/traces \
        -H 'content-type: application/json' -d '{}' 2>/dev/null || true)
if [ "$code" = "200" ] || [ "$code" = "415" ] || [ "$code" = "400" ]; then
  echo "  ✓ OTLP receiver answering on localhost:4318 (http $code)"
else
  echo "  ✗ OTLP receiver NOT answering on localhost:4318 (http ${code:-none})"
  echo "    the all-in-one image does not open 4317/4318 until a first user exists;"
  echo "    the local-mode image needs no signup. See integrations/clickstack/README.md"
  exit 1
fi
if [ ! -f ~/rca-api/integrations/otel.py ]; then
  echo "  ✗ ~/rca-api/integrations/otel.py missing — deploy from current main first"
  exit 1
fi
echo "  ✓ integrations/otel.py present"
REMOTE

if [ "$MODE" = "--status" ]; then
  say "status only — no changes"
  ssh "$HOST" "systemctl show rca-api -p Environment --value; echo '--- drop-in ---'; sudo cat $DROPIN 2>/dev/null || echo '(none)'"
  exit 0
fi

if [ "$MODE" = "--off" ]; then
  say "2/5  removing the drop-in"
  ssh "$HOST" "sudo rm -f $DROPIN && sudo systemctl daemon-reload && sudo systemctl restart rca-api && sleep 8 && systemctl is-active rca-api"
  say "done — engine back to a no-op tracer"
  exit 0
fi

say "2/5  writing the systemd drop-in"
ssh "$HOST" "sudo mkdir -p $(dirname $DROPIN) && printf '%s\n' '[Service]' 'Environment=CLICKSTACK_ENABLED=1' 'Environment=CLICKSTACK_OTLP=$OTLP' | sudo tee $DROPIN >/dev/null && sudo cat $DROPIN"

say "3/5  restarting rca-api"
ssh "$HOST" "sudo systemctl daemon-reload && sudo systemctl restart rca-api && sleep 20 && echo -n '  service: ' && systemctl is-active rca-api"

say "4/5  forcing one scan so spans exist"
ssh "$HOST" "curl -s -o /dev/null -w '  /scan -> %{http_code} in %{time_total}s\n' -m 180 '$API/scan?db=rca'"

say "5/5  counting spans in ClickStack's own ClickHouse"
ssh "$HOST" bash -s <<'REMOTE'
set -u
cs=$(docker ps --format '{{.Names}}' | grep -iE 'clickstack|hyperdx' | head -1)
sleep 6   # BatchSpanProcessor flush
docker exec "$cs" clickhouse-client --query "
SELECT SpanName, count() spans FROM default.otel_traces
WHERE ServiceName='rca-engine' GROUP BY SpanName ORDER BY spans DESC FORMAT PrettyCompact" 2>&1 | head -12
REMOTE

cat <<'NOTE'

Expect ~198 spans: 192 clickhouse.query plus the rca.* stage spans.
If the table is empty, the engine could not reach the collector — check
`journalctl -u rca-api | grep -i clickstack`; it prints one line and stays a no-op
rather than failing the scan.

For a judge to OPEN the HyperDX UI, port 8080 must be reachable from outside:
  on the box   sudo ufw allow 8080/tcp
  in Azure     add an NSG rule for 8080 (mirror the existing rca-api-8077 rule)
  in the UI    CLICKSTACK_URL=http://23.101.175.68:8080

Until then the traces exist and are queryable by SQL on the box, but the sidebar
"Traces · ClickStack" link will not resolve off-box.
NOTE
