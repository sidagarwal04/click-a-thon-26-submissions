#!/usr/bin/env bash
# Start the exact incremental finalizer as a continuously running service.
set -euo pipefail

die() {
  printf 'publisher-entrypoint: %s\n' "$*" >&2
  exit 1
}

DATABASE="${PUBLISH_DATABASE:-}"
LOOP_SECONDS="${PUBLISH_LOOP_SECONDS:-10}"

[ -n "$DATABASE" ] || die "PUBLISH_DATABASE is required"
case "$DATABASE" in
  *[!A-Za-z0-9_]* | [0-9]*) die "PUBLISH_DATABASE is not a usable ClickHouse identifier" ;;
esac
case "$LOOP_SECONDS" in
  '' | *[!0-9]*) die "PUBLISH_LOOP_SECONDS must be an integer from 1 to 300" ;;
esac
[ "$LOOP_SECONDS" -ge 1 ] && [ "$LOOP_SECONDS" -le 300 ] || \
  die "PUBLISH_LOOP_SECONDS must be an integer from 1 to 300"

case "${TARGET:-cloud}" in
  cloud)
    [ -n "${CH_HOST:-}" ] || die "CH_HOST is required for TARGET=cloud"
    [ -n "${CH_PORT:-}" ] || die "CH_PORT is required for TARGET=cloud"
    [ -n "${CH_USER:-}" ] || die "CH_USER is required for TARGET=cloud"
    [ -n "${CH_PASSWORD:-}" ] || die "CH_PASSWORD is required for TARGET=cloud"
    ;;
  local)
    [ -n "${CH_LOCAL_URL:-}" ] || die "CH_LOCAL_URL is required for TARGET=local"
    [ -n "${CH_PASSWORD_LOCAL:-}" ] || die "CH_PASSWORD_LOCAL is required for TARGET=local"
    ;;
  *) die "TARGET must be cloud or local" ;;
esac

cd "${PUBLISH_APP_ROOT:-/app}"

# publish.sh performs the authoritative seven-object schema preflight before it
# takes the lease. The service intentionally does not run migrations or a full
# rebuild: a restart must never mutate schema or replace good serving data.
export CH_DATABASE="$DATABASE"
exec tools/publish.sh --database "$DATABASE" --loop "$LOOP_SECONDS"
