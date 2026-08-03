#!/usr/bin/env bash
# Proves 130 sparse output dates are built as 3 inserts of at most 64 dates.
set -euo pipefail
cd "$(dirname "$0")/.."

[ "${TARGET:-local}" = local ] || {
  echo "chunked-backfill-test.sh is local-only." >&2
  exit 1
}

DB="chunk_backfill_${$}"
case "$DB" in chunk_backfill_[0-9]*) ;; *) echo "unsafe scratch database: $DB" >&2; exit 1 ;; esac
q() { env -u CH_DATABASE CH_DATABASE_LOCAL="$DB" TARGET=local tools/ch "$1"; }
admin_q() { env -u CH_DATABASE CH_DATABASE_LOCAL=default TARGET=local tools/ch "$1"; }
cleanup() { admin_q "DROP DATABASE IF EXISTS $DB" >/dev/null 2>&1 || true; }
trap cleanup EXIT

admin_q "CREATE DATABASE $DB"
env -u CH_DATABASE CH_DATABASE_LOCAL="$DB" TARGET=local tools/apply-sql.sh --database "$DB" \
  sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql >/dev/null

# 129 isolated dates plus one 25-hour interval. The long interval contributes
# the missing second day, proving date discovery and final-output filtering do
# not discard days after an interval's start.
q "INSERT INTO session_intervals
     (video_session_id, user_id, content_id, platform, country, app_version,
      audio_language, subtitle_language, player_version, extra_dimensions,
      interval_start, interval_end, is_open, build_version)
   SELECT concat('s', toString(number)), concat('u', toString(number)), 1,
          'web', 'IN', '1.0', 'hin', 'none', 'p1', map('cohort', 'A'),
          toDateTime64('2026-01-01 10:00:10', 3) + toIntervalDay(number * 2),
          toDateTime64('2026-01-01 10:00:50', 3) + toIntervalDay(number * 2),
          0, 1
   FROM numbers(129)"

q "INSERT INTO session_intervals
     (video_session_id, user_id, content_id, platform, country, app_version,
      audio_language, subtitle_language, player_version, extra_dimensions,
      interval_start, interval_end, is_open, build_version)
   VALUES ('long', 'long-user', 2, 'long-run', 'IN', '1.0', 'hin', 'none', 'p1',
           map('cohort', 'B'), toDateTime64('2026-01-01 23:59:10', 3),
           toDateTime64('2026-01-03 00:00:10', 3), 0, 1)"

USER_OUT="$(env -u CH_DATABASE CH_DATABASE_LOCAL="$DB" TARGET=local \
  tools/chunked-backfill.sh users)"
DELTA_OUT="$(env -u CH_DATABASE CH_DATABASE_LOCAL="$DB" TARGET=local \
  tools/chunked-backfill.sh deltas)"
printf '%s\n%s\n' "$USER_OUT" "$DELTA_OUT"

printf '%s\n' "$USER_OUT" | grep -q '130 actual output date(s), 3 insert chunk(s), max 64 dates/insert'
printf '%s\n' "$DELTA_OUT" | grep -q '130 actual output date(s), 3 insert chunk(s), max 64 dates/insert'

read -r USER_DATES USER_BUCKETS DELTA_DATES DELTA_ROWS <<EOF
$(q "SELECT
       (SELECT uniqExact(toDate(minute)) FROM cc_user_minute FINAL),
       (SELECT count() FROM cc_user_minute FINAL),
       (SELECT uniqExact(toDate(minute)) FROM cc_minute_delta),
       (SELECT count() FROM cc_minute_delta)
     FORMAT TSVRaw")
EOF

[ "$USER_DATES" = 130 ] && [ "$USER_BUCKETS" = 1571 ] || {
  echo "user tier mismatch: dates=$USER_DATES buckets=$USER_BUCKETS" >&2
  exit 1
}
[ "$DELTA_DATES" = 130 ] && [ "$DELTA_ROWS" = 285 ] || {
  echo "delta tier mismatch: dates=$DELTA_DATES rows=$DELTA_ROWS" >&2
  exit 1
}

echo "PASS — 130 sparse dates including a multi-day interval, 3 chunks/tier, exact rows"
