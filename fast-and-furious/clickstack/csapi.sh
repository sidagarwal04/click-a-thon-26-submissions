#!/usr/bin/env bash
# csapi.sh — authenticated request against the managed ClickStack API.
#
# Same role as ingest/concurrency/ch.sh: every call this project makes to
# ClickStack goes through one reviewable script instead of a shell one-liner.
#
#   ./clickstack/csapi.sh GET  /sources
#   ./clickstack/csapi.sh GET  /dashboards
#   ./clickstack/csapi.sh POST /dashboards @clickstack/dashboards/01-live-concurrency.json
#   ./clickstack/csapi.sh DELETE /dashboards/<id>
#
# Managed ClickStack rides on the ClickHouse Cloud API, so it authenticates with a
# Cloud API key (Basic auth, key id as username) rather than a HyperDX personal
# token — the OSS deployment is the one that uses a bearer token on :8000.
#
# Required in .env (gitignored):
#   CLICKHOUSE_CLOUD_KEY_ID       Cloud API key id
#   CLICKHOUSE_CLOUD_KEY_SECRET   Cloud API key secret  (Org Admin or Service Admin)
#   CLICKHOUSE_CLOUD_ORG_ID       organization uuid
#   CLICKHOUSE_CLOUD_SERVICE_ID   service uuid
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Walk up for .env the way ingest/internal/config.findEnvFile does, so this works
# from a git worktree whose .env lives in the parent checkout.
dir="$repo_root"
for _ in 1 2 3 4 5 6; do
  if [[ -f "$dir/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "$dir/.env"
    set +a
    break
  fi
  dir="$(dirname "$dir")"
done

for v in CLICKHOUSE_CLOUD_KEY_ID CLICKHOUSE_CLOUD_KEY_SECRET CLICKHOUSE_CLOUD_ORG_ID CLICKHOUSE_CLOUD_SERVICE_ID; do
  if [[ -z "${!v:-}" ]]; then
    echo "csapi.sh: $v is not set. See the header of this script." >&2
    exit 2
  fi
done

base="https://api.clickhouse.cloud/v1/organizations/${CLICKHOUSE_CLOUD_ORG_ID}/services/${CLICKHOUSE_CLOUD_SERVICE_ID}/clickstack"

method="${1:?usage: csapi.sh <METHOD> <path> [body|@file]}"
path="${2:?usage: csapi.sh <METHOD> <path> [body|@file]}"
body="${3:-}"

args=(-sS --show-error --max-time 120 -X "$method"
      --user "${CLICKHOUSE_CLOUD_KEY_ID}:${CLICKHOUSE_CLOUD_KEY_SECRET}"
      -H 'Content-Type: application/json'
      -w '\n%{http_code}\n')

if [[ -n "$body" ]]; then
  if [[ "$body" == @* ]]; then
    args+=(--data-binary "@${body#@}")
  else
    args+=(--data-binary "$body")
  fi
fi

# The trailing status line is separated so callers can branch on it while still
# seeing the response body — a 400 from this API carries the reason in the body,
# and --fail would throw it away.
out="$(curl "${args[@]}" "${base}${path}")"
status="$(printf '%s' "$out" | tail -n1)"
printf '%s' "$out" | sed '$d'

case "$status" in
  2*) exit 0 ;;
  *)  echo "csapi.sh: HTTP $status for $method $path" >&2; exit 1 ;;
esac
