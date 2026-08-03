#!/usr/bin/env bash
# ch.sh — run a query against the configured ClickHouse service over HTTPS.
#
# Exists so that every ad-hoc check in this project is a reviewable artifact
# rather than a shell-history one-liner. Reads the same .env the Go binaries do
# and never echoes the password.
#
#   ./ingest/concurrency/ch.sh "SELECT count() FROM session_intervals FINAL"
#   ./ingest/concurrency/ch.sh --file ingest/concurrency/sql/090_validate_serving.sql
#   ./ingest/concurrency/ch.sh --format Pretty "SELECT 1"
#
# Parameters for the parameterized rollup SQL are passed through as
# --param_<name>=<value>, matching clickhouse-client:
#
#   ./ingest/concurrency/ch.sh --file ingest/concurrency/sql/020_rollup_live.sql \
#       --param_window_start='2026-08-02 10:00:00' ...
#
# {{db}} in a file is substituted with $CLICKHOUSE_DATABASE before sending, the
# same way chx.Client.Render does it for the Go path.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Walk up for .env the way config.findEnvFile does, so this works from a git
# worktree whose .env lives in the parent checkout.
env_file=""
dir="$repo_root"
for _ in 1 2 3 4 5 6; do
  if [[ -f "$dir/.env" ]]; then env_file="$dir/.env"; break; fi
  dir="$(dirname "$dir")"
done
if [[ -n "$env_file" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$env_file"
  set +a
fi

: "${CLICKHOUSE_HOST:?CLICKHOUSE_HOST is not set (no .env found?)}"
: "${CLICKHOUSE_USER:?CLICKHOUSE_USER is not set}"
: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD is not set}"
db="${CLICKHOUSE_DATABASE:-default}"

format="TabSeparatedWithNames"
sql=""
sql_file=""
params=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)     sql_file="$2"; shift 2 ;;
    --format)   format="$2";   shift 2 ;;
    --param_*)  params+=("$1"); shift ;;
    --)         shift; break ;;
    *)          sql="$1"; shift ;;
  esac
done

if [[ -n "$sql_file" ]]; then
  sql="$(sed "s/{{db}}/${db}/g" "$sql_file")"
fi
[[ -n "$sql" ]] || { echo "ch.sh: no query given" >&2; exit 2; }

url="https://${CLICKHOUSE_HOST}:8443/?database=${db}&default_format=${format}"

# Query parameters must ride in the URL because the request body is the SQL, so
# they need real percent-encoding — timestamps contain spaces and colons.
for p in "${params[@]:-}"; do
  [[ -z "$p" ]] && continue
  kv="${p#--}"
  url+="&${kv%%=*}=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "${kv#*=}")"
done

curl -sS --fail-with-body --max-time 300 "$url" \
  --user "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
  --data-binary "$sql"
