#!/usr/bin/env bash
# Run ONCE after registering in HyperDX (http://localhost:8081).
#
# ClickStack's collector only starts its OTLP receivers after a team exists, and
# ingestion requires the team's API key as an authorization header. This fetches
# the key from HyperDX's Mongo, writes OTEL_EXPORTER_OTLP_HEADERS into .env, and
# restarts rca-mcp so investigation spans flow to HyperDX Traces.
set -euo pipefail
cd "$(dirname "$0")"

KEY=$(docker compose exec -T mongodb mongosh --quiet --eval \
  'var t = db.getSiblingDB("hyperdx").teams.findOne(); print(t ? t.apiKey : "")')
if [[ -z "$KEY" ]]; then
  echo "!! no HyperDX team yet — register at http://localhost:8081 first" >&2
  exit 1
fi

grep -q '^OTEL_EXPORTER_OTLP_HEADERS=' .env 2>/dev/null \
  && sed -i '' "s|^OTEL_EXPORTER_OTLP_HEADERS=.*|OTEL_EXPORTER_OTLP_HEADERS=authorization=${KEY}|" .env \
  || echo "OTEL_EXPORTER_OTLP_HEADERS=authorization=${KEY}" >> .env

docker compose up -d --build rca-mcp
echo "wired: rca-mcp now exports spans to ClickStack"
