#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

ROOT="$(pwd)"
exec ./grafana/bin/grafana server \
  --homepath "$ROOT/grafana" \
  --config "$ROOT/conf/custom.ini"
