#!/usr/bin/env bash
# tools/publish-window-test.sh — local regression for complete-session re-derivation.
# A first singleton produces no interval under POINT_ACTIVITY_COUNTS=0. Two later
# heartbeats arrive in a separate insert inside GAP_S. Incremental publication must
# recover the old singleton, start at its timestamp, and match a full rebuild,
# including independently attributed unknown dimensions. Local scratch databases only.
set -euo pipefail
cd "$(dirname "$0")/.."

[ "${TARGET:-local}" = local ] || {
  echo "publish-window-test: local only" >&2
  exit 2
}

LIVE=publisher_window_test
CONTROL=publisher_window_control

base_q() { TARGET=local tools/ch "$1"; }
live_q() { CH_DATABASE_LOCAL="$LIVE" TARGET=local tools/ch "$1"; }
control_q() { CH_DATABASE_LOCAL="$CONTROL" TARGET=local tools/ch "$1"; }
apply() {
  env -u CH_DATABASE -u CH_DATABASE_LOCAL TARGET=local \
    tools/apply-sql.sh --database "$1" "${@:2}" >/dev/null
}
publish() {
  env -u CH_DATABASE -u CH_DATABASE_LOCAL TARGET=local \
    PUBLISH_SETTLE_S=0 PUBLISH_LEASE_SETTLE_S=0 \
    tools/publish.sh --database "$LIVE" --quiet
}
fail() { echo "publish-window-test: FAIL — $*" >&2; exit 1; }

base_q "DROP DATABASE IF EXISTS ${LIVE}" >/dev/null
base_q "DROP DATABASE IF EXISTS ${CONTROL}" >/dev/null
base_q "CREATE DATABASE ${LIVE}" >/dev/null
base_q "CREATE DATABASE ${CONTROL}" >/dev/null

apply "$LIVE" sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql \
  sql/12_publish.sql sql/15_normalise.sql sql/20_views.sql sql/45_user_concurrency.sql sql/50_hour_agg.sql
apply "$CONTROL" sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql sql/15_normalise.sql sql/20_views.sql

live_q "INSERT INTO ev_raw
  (content_id, video_session_id, user_id, event_type, event, event_timestamp,
   platform, app_version, country, audio_language, subtitle_language,
   player_version, session_start_epoch, extra)
 VALUES
  (1, 'PW_S1', 'PW_U1', 'VideoHeartbeat', 'network-activity',
   '2026-07-31 10:00:00', 'web', '1', 'IN', 'hin', 'none', 'p1',
   '2026-07-31 10:00:00', map('experiment_id','A','video_resolution','1080'))" >/dev/null
publish

[ "$(live_q "SELECT count() FROM session_intervals FINAL FORMAT TSVRaw")" = 0 ] \
  || fail "the singleton unexpectedly produced an interval"

live_q "INSERT INTO ev_raw
  (content_id, video_session_id, user_id, event_type, event, event_timestamp,
   platform, app_version, country, audio_language, subtitle_language,
   player_version, session_start_epoch, extra)
 VALUES
  (1, 'PW_S1', 'PW_U1', 'VideoHeartbeat', 'network-activity',
   '2026-07-31 10:01:40', 'web', '1', 'IN', 'hin', 'none', 'p1',
   '2026-07-31 10:00:00', map('experiment_id','B','video_resolution','720')),
  (1, 'PW_S1', 'PW_U1', 'VideoHeartbeat', 'network-activity',
   '2026-07-31 10:02:00', 'web', '1', 'IN', 'hin', 'none', 'p1',
   '2026-07-31 10:00:00', map('experiment_id','B','video_resolution','720'))" >/dev/null
publish

live_q "INSERT INTO ${CONTROL}.ev_raw SELECT * FROM ${LIVE}.ev_raw" >/dev/null
apply "$CONTROL" sql/30_build_intervals.sql sql/40_deltas.sql

interval_diff="$(base_q "SELECT count() FROM
(
  SELECT video_session_id, interval_start, interval_end, is_open,
         toJSONString(extra_dimensions) AS extra_json, sum(sign) AS net
  FROM
  (
    SELECT video_session_id, interval_start, interval_end, is_open,
           extra_dimensions, 1 AS sign FROM ${LIVE}.session_intervals FINAL
    UNION ALL
    SELECT video_session_id, interval_start, interval_end, is_open,
           extra_dimensions, -1 AS sign FROM ${CONTROL}.session_intervals FINAL
  )
  GROUP BY video_session_id, interval_start, interval_end, is_open, extra_json
  HAVING net != 0
) FORMAT TSVRaw")"
[ "$interval_diff" = 0 ] || fail "$interval_diff interval rows differ from full rebuild"

actual="$(live_q "SELECT concat(
  toString(interval_start), '|', toString(interval_end), '|',
  extra_dimensions['experiment_id'], '|', video_resolution)
 FROM session_intervals FINAL FORMAT TSVRaw")"
[ "$actual" = "2026-07-31 10:00:00.000|2026-07-31 10:03:00.000|B|720" ] \
  || fail "unexpected published interval: $actual"

echo "publish-window-test: PASS — singleton history recovered; incremental = rebuild; dynamic dimensions preserved"
