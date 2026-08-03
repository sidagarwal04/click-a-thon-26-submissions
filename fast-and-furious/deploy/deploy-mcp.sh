#!/usr/bin/env bash
# deploy-mcp.sh — build sonyliv-mcp for linux/amd64, ship it to EC2, restart the unit.
#
#   MCP_HOST=ec2-user@1.2.3.4 ./deploy/deploy-mcp.sh
#   MCP_HOST=... ./deploy/deploy-mcp.sh --check     verify a deployment without shipping
#
# Prerequisites on the box, once:
#   sudo useradd --system --shell /usr/sbin/nologin sonyliv
#   sudo mkdir -p /opt/sonyliv/bin /etc/sonyliv
#   sudo install -m 600 -o sonyliv -g sonyliv /dev/null /etc/sonyliv/mcp.env
#
# /etc/sonyliv/mcp.env must contain the RESTRICTED user, not the service user — the
# server refuses to start if it can read events_clean, but do not rely on that as the
# only check:
#
#   CLICKHOUSE_HOST=<service>.clickhouse.cloud
#   CLICKHOUSE_PORT=9440
#   CLICKHOUSE_SECURE=true
#   CLICKHOUSE_DATABASE=sonyliv_prod
#   CLICKHOUSE_USER=sonyliv_mcp
#   CLICKHOUSE_PASSWORD=<the password from 009_mcp_reader.sql>
#   SONYLIV_MCP_TOKEN=<openssl rand -hex 32>
#   MCP_ADDR=172.17.0.1:8848
#
# MCP_ADDR is the address the unit binds. On this box it is the Docker bridge gateway,
# because LibreChat runs in a container and containers cannot reach the host's loopback.
# Confirm the gateway before setting it -- it is 172.17.0.1 for stock docker0, but a box
# with a custom bridge or a pre-existing 172.17/16 route will differ:
#
#   ip -4 addr show docker0 | awk '/inet /{print $2}'
#
# TLS is deliberately NOT handled here, and the bridge does not change that. Both loopback
# and the Docker bridge are host-local, so nothing plaintext leaves the box; anything that
# publishes :8848 off-box needs nginx or a load balancer with a certificate in front,
# because the bearer token is SQL access.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"

host="${MCP_HOST:-}"
[[ -n "$host" ]] || { echo "deploy-mcp.sh: set MCP_HOST=user@host" >&2; exit 2; }

remote_check() {
  # Both the address and the token come from /etc/sonyliv/mcp.env, the same file the unit
  # reads, so a check can never pass against an address the service is not on.
  #
  # It is mode 0600 owned by sonyliv, so the deploy user cannot source it directly -- the
  # earlier `. /etc/sonyliv/mcp.env` here could only ever have worked on a box where that
  # file was wrongly readable. Read it through the one sudo the deploy user is granted
  # (NOPASSWD /bin/bash, see README.md), and take only the two variables this needs rather
  # than eval-ing a file that also holds the ClickHouse password.
  # shellcheck disable=SC2029
  ssh "$host" 'set -euo pipefail
    eval "$(sudo bash -c "grep -E \"^(SONYLIV_MCP_TOKEN|MCP_ADDR)=\" /etc/sonyliv/mcp.env")"
    : "${MCP_ADDR:=127.0.0.1:8848}"

    echo "== remote health (${MCP_ADDR}) =="
    systemctl is-active sonyliv-mcp
    curl -sS --max-time 5 "http://${MCP_ADDR}/healthz"

    echo "== refusals, exercised on the box against the deployed process =="
    q() { curl -sS --max-time 30 -H "Content-Type: application/json" \
            -H "Authorization: Bearer $SONYLIV_MCP_TOKEN" -X POST "http://${MCP_ADDR}/mcp" -d "$1"; }
    echo -n "  currentUser via MCP: "
    q "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"run_select_query\",\"arguments\":{\"query\":\"SELECT 1 FROM serving_watermark\"}}}" | head -c 160; echo
    echo -n "  events_clean refused: "
    q "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"run_select_query\",\"arguments\":{\"query\":\"SELECT count() FROM events_clean\"}}}" | grep -o "outside the serving layer" || echo "NOT REFUSED — investigate"'
}

if [[ "${1:-}" == "--check" ]]; then
  remote_check
  exit 0
fi

echo "== build (linux/amd64) =="
cd "$repo/ingest"
version="$(git -C "$repo" rev-parse --short HEAD 2>/dev/null || echo dev)"
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
  -ldflags "-s -w -X main.buildVersion=$version" \
  -o "$repo/ingest/bin/sonyliv-mcp.linux-amd64" ./cmd/sonyliv-mcp
echo "  built $version"

echo "== ship =="
# Staged into /tmp then installed, so a partial transfer never becomes the live binary.
scp -q "$repo/ingest/bin/sonyliv-mcp.linux-amd64" "$host:/tmp/sonyliv-mcp.new"
scp -q "$here/sonyliv-mcp.service" "$host:/tmp/sonyliv-mcp.service"

echo "== install and restart =="
# shellcheck disable=SC2029
ssh "$host" 'set -euo pipefail
  # The unit now binds ${MCP_ADDR}. An address that is not on any interface makes the
  # service crash-loop, so refuse before the restart rather than after -- a failed deploy
  # that left the old process running is recoverable; one that took it down is not.
  eval "$(sudo bash -c "grep -E \"^MCP_ADDR=\" /etc/sonyliv/mcp.env || true")"
  if [ -z "${MCP_ADDR:-}" ]; then
    echo "MCP_ADDR is not set in /etc/sonyliv/mcp.env -- add it (see deploy-mcp.sh header)" >&2
    exit 2
  fi
  ip="${MCP_ADDR%:*}"
  if [ "$ip" != "0.0.0.0" ] && ! ip -4 -o addr show | grep -qw "$ip"; then
    echo "MCP_ADDR=$MCP_ADDR but $ip is on no interface (is dockerd up?)" >&2
    exit 2
  fi

  sudo install -m 0755 -o root -g root /tmp/sonyliv-mcp.new /opt/sonyliv/bin/sonyliv-mcp
  sudo install -m 0644 -o root -g root /tmp/sonyliv-mcp.service /etc/systemd/system/sonyliv-mcp.service
  rm -f /tmp/sonyliv-mcp.new /tmp/sonyliv-mcp.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now sonyliv-mcp
  sudo systemctl restart sonyliv-mcp
  sleep 2
  systemctl is-active sonyliv-mcp'

remote_check
echo
echo "done. LibreChat reaches this at http://host.docker.internal:8848/mcp with the bearer"
echo "token; see deploy/librechat/. Any client off the box needs TLS in front."
