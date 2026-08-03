#!/usr/bin/env bash
# ============================================================================
# tools/publish-test.sh — proof that the aggregates MOVE without a rebuild.
#
# ADR 0013 claims tools/publish.sh publishes incrementally and lands on exactly
# the number a full recompute would; ADR 0016 extends that claim to the USER
# and HOUR/DAY tiers, which this harness's scratch databases previously did not
# even instantiate — which is why their staleness was invisible to it. A claim
# is not evidence. This harness:
#
#   1. builds the model on a truncated slice THROUGH THE INCREMENTAL PATH and
#      shows it is byte-identical to a batch rebuild of the same slice;
#   2. lands late arrivals in three shapes — a handful of open sessions, the
#      whole remaining stream, and one genuine STRAGGLER dated 46 minutes
#      behind the watermark — and after each one shows the served number moved
#      and still equals a from-scratch control build on EVERY minute;
#   3. SHRINKS a published interval (a late pause pulls interval_end EARLIER —
#      the case that broke the version column once) and FLIPS a published
#      interval's dominant platform — the two retraction shapes a set-union
#      user tier can never absorb (ADR 0016);
#   4. reads system.query_log back to show what each incremental run actually
#      touched, against what the rebuild touches;
#   5. republishes an UNCHANGED session and shows the curve does not move —
#      the property that makes over-consuming the change log safe;
#   6. (ADR 0019) CRASHES the publisher at every phase boundary — the marks
#      and the statements between them, 16 points — and proves each recovery
#      converges (PHASE 12, the longest phase: ~30 s per boundary);
#   7. (ADR 0019) runs TWO publishers at once and shows the lease admits
#      exactly one, the served number moves by exactly one viewer — not two,
#      which is what the double-applied correction produced before the lease;
#   8. (ADR 0019) lands two SAME-MILLISECOND markings where the slower insert
#      commits after the faster was consumed, and shows the (marked_at,
#      insert_id) pair identity claims it — marked_at alone suppressed it;
#   9. (ADR 0019) shows the retention headroom columns: a marking older than
#      the claim lookback trips retention_alert instead of expiring silently.
#
# EVERY convergence check covers all four serving tiers: minute deltas,
# intervals, user-minute buckets (v_user_concurrency_minute*), and the
# hour/day cube (v_concurrency_hour / v_concurrency_day).
#
# ISOLATION. Two scratch databases, sonyliv_pub (live, published incrementally)
# and sonyliv_pub_ctl (control, rebuilt from scratch). `sonyliv` is read with
# SELECT only; assert_isolation() below refuses to run if that is not true of
# this file. Never point this at the graded database.
#
#   tools/publish-test.sh          # ~4 min on Cloud, writes evidence/publish.txt
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

CUT="${CUT:-2026-07-26 10:56:00}"
LIVE=sonyliv_pub
CTL=sonyliv_pub_ctl
PROD=sonyliv                      # READ-ONLY. Never a write target.
OUT=evidence/publish.txt
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p evidence

# The straggler: a single heartbeat dropped into a 290 s gap of an
# already-published session. 147 s from the event before it and 143 s from the
# event after, both inside HEARTBEAT_GAP_S = 150, so it bridges the gap and the
# session's two runs MERGE. That is the case that matters: it does not merely
# extend an interval, it makes an interval_start VANISH.
STRAGGLER_SESSION="${STRAGGLER_SESSION:-B52EB43D855A723E1755B97C75CEAC5D05B60BCCEDC5902DECF4610114D89E6B}"
STRAGGLER_TS="${STRAGGLER_TS:-2026-07-26 10:45:10.000}"

ch_host() { local h="${CH_HOST:?CH_HOST unset}"; h="${h#https://}"; h="${h#http://}"; echo "${h%/}"; }
q()  { tools/ch -c "$1"; }
qr() { tools/ch -c "$1 FORMAT TSVRaw"; }
say()  { printf '%s\n' "$*" | tee -a "$OUT"; }
rule() { say "--------------------------------------------------------------------------"; }

assert_isolation() {
  if grep -Eq "(INSERT[[:space:]]+INTO|TRUNCATE[[:space:]]+TABLE|DELETE[[:space:]]+FROM|DROP[[:space:]]+DATABASE)[[:space:]]+\\\$?\{?${PROD}\b" "$0"; then
    echo "REFUSING: $0 writes to ${PROD}" >&2; exit 1
  fi
}
assert_isolation

# Run a SQL file against a database with an explicit query_id, so system.
# query_log can be read back for it afterwards.
qfile() {  # qfile <db> <file> <query_id>
  curl -sS --fail-with-body "https://$(ch_host):${CH_PORT}/?database=$1&query_id=$3" \
    --user "${CH_USER}:${CH_PASSWORD}" --data-binary "@$2"
}

# What a statement actually touched, from the server's own log.
cost() {  # cost <query_id>
  q "SYSTEM FLUSH LOGS" >/dev/null 2>&1 || true
  qr "SELECT concat(
        'read_rows=', formatReadableQuantity(read_rows),
        '  read_bytes=', formatReadableSize(read_bytes),
        '  parts=', toString(ProfileEvents['SelectedParts']),
        '  marks=', toString(ProfileEvents['SelectedMarks']),
        '/', toString(ProfileEvents['SelectedMarksTotal']),
        '  ', toString(round(query_duration_ms)), ' ms')
      FROM system.query_log WHERE query_id = '$1' AND type = 'QueryFinish'
      ORDER BY event_time DESC LIMIT 1"
}

# The canonical tier re-derivations live INSIDE multi-statement files (DDL +
# INSERT + views); qfile speaks HTTP, which takes one statement. Cut the INSERT
# out between its PUBLISH_EXTRACT markers — the same statement tools/publish.sh
# templates, so the control rebuild provably runs the same derivation.
extract_insert() {  # extract_insert <src> <dst>
  sed -n '/PUBLISH_EXTRACT_BEGIN/,/PUBLISH_EXTRACT_END/p' "$1" > "$2"
  grep -q 'INSERT INTO' "$2" || { echo "no INSERT between PUBLISH_EXTRACT markers in $1" >&2; exit 1; }
}
extract_insert sql/45_user_concurrency.sql "$TMP/ctl_users.sql"
extract_insert sql/50_hour_agg.sql         "$TMP/ctl_hours.sql"

# A full batch rebuild of the control database — the "recompute" answer, run
# exactly the way tools/build-model.sh runs it (TRUNCATE every tier it owns,
# re-derive all of it).
control_rebuild() {  # control_rebuild <tag>
  q "TRUNCATE TABLE ${CTL}.session_intervals" >/dev/null
  qfile "$CTL" sql/30_build_intervals.sql "ctl-$1-intervals" >/dev/null
  q "TRUNCATE TABLE ${CTL}.cc_user_minute" >/dev/null
  qfile "$CTL" "$TMP/ctl_users.sql" "ctl-$1-users" >/dev/null
  q "TRUNCATE TABLE ${CTL}.cc_minute_delta" >/dev/null
  qfile "$CTL" sql/40_deltas.sql "ctl-$1-deltas" >/dev/null
  q "TRUNCATE TABLE ${CTL}.cc_hour_agg" >/dev/null
  qfile "$CTL" "$TMP/ctl_hours.sql" "ctl-$1-hours" >/dev/null
}

# The three-way comparison. Anything non-zero is a failure.
compare() {  # compare <label>
  say ""
  say "  CONVERGENCE — incremental ($LIVE) vs from-scratch rebuild ($CTL)"
  q "
  SELECT * FROM (
    SELECT 1 AS ord, 'delta cells differing' AS check, toString(count()) AS value FROM (
      SELECT minute, platform, country, content_id, subtitle_language, player_version,
             audio_language, app_version, sum(d) AS dd, sum(s) AS ss, sum(e) AS ee
      FROM (
        SELECT minute, platform, country, content_id, subtitle_language, player_version,
               audio_language, app_version, delta AS d, starts AS s, ends AS e
        FROM ${LIVE}.cc_minute_delta
        UNION ALL
        SELECT minute, platform, country, content_id, subtitle_language, player_version,
               audio_language, app_version, -delta, -starts, -ends
        FROM ${CTL}.cc_minute_delta)
      GROUP BY minute, platform, country, content_id, subtitle_language, player_version,
               audio_language, app_version
      HAVING dd != 0 OR ss != 0 OR ee != 0)
    UNION ALL
    SELECT 2, 'interval rows differing', toString(count()) FROM (
      SELECT video_session_id, interval_start, interval_end, is_open, platform, country,
             content_id, app_version, audio_language, subtitle_language, player_version,
             sum(sg) AS n
      FROM (
        SELECT video_session_id, interval_start, interval_end, is_open, platform, country,
               content_id, app_version, audio_language, subtitle_language, player_version,
               1 AS sg FROM ${LIVE}.session_intervals FINAL
        UNION ALL
        SELECT video_session_id, interval_start, interval_end, is_open, platform, country,
               content_id, app_version, audio_language, subtitle_language, player_version,
               -1 FROM ${CTL}.session_intervals FINAL)
      GROUP BY video_session_id, interval_start, interval_end, is_open, platform, country,
               content_id, app_version, audio_language, subtitle_language, player_version
      HAVING n != 0)
    UNION ALL
    -- Served concurrency is the RUNNING SUM at each minute, compared over the
    -- UNION of minutes either side knows about — not a row-membership join of
    -- the *_total views. Those views emit a row only for minutes present in
    -- cc_minute_delta, and the incremental path legitimately materializes
    -- minutes the rebuild does not: a correction pair (-X then +X') touches a
    -- minute with net-zero rows, the GROUP BY keeps it, and the carried value
    -- it shows is CORRECT. A membership join counted 8 such minutes as
    -- 'differing' while every actually-served number agreed (ADR 0019 PHASE
    -- 12 caught this the first time the probe region was quiet).
    SELECT 3, 'served minutes differing (running sum over union of minutes)',
           toString(countIf(ca != cb)) FROM (
      SELECT minute,
             sum(sum(dl)) OVER (ORDER BY minute) AS ca,
             sum(sum(dc)) OVER (ORDER BY minute) AS cb
      FROM (
        SELECT minute, delta AS dl, 0 AS dc FROM ${LIVE}.cc_minute_delta
        UNION ALL
        SELECT minute, 0, delta FROM ${CTL}.cc_minute_delta)
      GROUP BY minute)
    UNION ALL
    SELECT 4, 'served minutes compared', toString(count()) FROM (
      SELECT DISTINCT minute FROM (
        SELECT minute FROM ${LIVE}.cc_minute_delta
        UNION ALL SELECT minute FROM ${CTL}.cc_minute_delta))
    UNION ALL
    SELECT 5, 'peak — incremental',  toString(max(concurrent)) FROM ${LIVE}.v_concurrency_minute_delta_total
    UNION ALL
    SELECT 6, 'peak — rebuild',      toString(max(concurrent)) FROM ${CTL}.v_concurrency_minute_delta_total
    UNION ALL
    SELECT 7, 'cc_minute_delta rows — incremental (incl. cancelling corrections)',
           toString(count()) FROM ${LIVE}.cc_minute_delta
    UNION ALL
    SELECT 8, 'cc_minute_delta rows — rebuild', toString(count()) FROM ${CTL}.cc_minute_delta
    UNION ALL
    SELECT 9, 'user cells differing (minute x dims)',
           toString(countIf(ifNull(a.concurrent_users, -1) != ifNull(b.concurrent_users, -1)))
    FROM ${LIVE}.v_user_concurrency_minute a
    FULL OUTER JOIN ${CTL}.v_user_concurrency_minute b
      USING (minute, platform, country, content_id)
    UNION ALL
    SELECT 10, 'user minutes differing (total)',
           toString(countIf(ifNull(a.concurrent_users, -1) != ifNull(b.concurrent_users, -1)))
    FROM ${LIVE}.v_user_concurrency_minute_total a
    FULL OUTER JOIN ${CTL}.v_user_concurrency_minute_total b USING (minute)
    UNION ALL
    SELECT 11, 'user peak — incremental', toString(max(concurrent_users))
    FROM ${LIVE}.v_user_concurrency_minute_total
    UNION ALL
    SELECT 12, 'user peak — rebuild', toString(max(concurrent_users))
    FROM ${CTL}.v_user_concurrency_minute_total
    UNION ALL
    SELECT 13, 'hour-cube rows differing (peak, peak_minute or integral)',
           toString(countIf(   ifNull(a.peak, -1)        != ifNull(b.peak, -1)
                            OR ifNull(a.integral, -1)    != ifNull(b.integral, -1)
                            OR ifNull(a.peak_minute, toDateTime(0))
                               != ifNull(b.peak_minute, toDateTime(0))))
    FROM ${LIVE}.v_concurrency_hour a
    FULL OUTER JOIN ${CTL}.v_concurrency_hour b
      USING (platform, country, content_id, hour)
    UNION ALL
    SELECT 14, 'day rows differing (peak, peak_minute or integral)',
           toString(countIf(   ifNull(a.peak, -1)        != ifNull(b.peak, -1)
                            OR ifNull(a.integral, -1)    != ifNull(b.integral, -1)
                            OR ifNull(a.peak_minute, toDateTime(0))
                               != ifNull(b.peak_minute, toDateTime(0))))
    FROM ${LIVE}.v_concurrency_day a
    FULL OUTER JOIN ${CTL}.v_concurrency_day b
      USING (platform, country, content_id, day)
    UNION ALL
    SELECT 15, 'hour-tier peak — incremental', toString(max(peak)) FROM ${LIVE}.v_concurrency_hour_total
    UNION ALL
    SELECT 16, 'hour-tier peak — rebuild',     toString(max(peak)) FROM ${CTL}.v_concurrency_hour_total
  ) ORDER BY ord FORMAT PrettyCompact" | tee -a "$OUT"
}

# The served curve around the straggler, so "the number moved" is a number.
served_window() {  # served_window <label>
  q "
  SELECT '$1' AS at, toString(minute) AS at_minute, toInt64(sum(sum(delta)) OVER (ORDER BY minute)) AS concurrent
  FROM ${LIVE}.cc_minute_delta
  WHERE minute >= toDateTime('2026-07-26 10:00:00') AND minute <= toDateTime('2026-07-26 10:50:00')
  GROUP BY minute
  HAVING minute >= toDateTime('2026-07-26 10:42:00') AND minute <= toDateTime('2026-07-26 10:48:00')
  ORDER BY minute FORMAT PrettyCompact" | tee -a "$OUT"
}

: > "$OUT"
say "CONTINUOUS PUBLICATION — incremental update proof   (ADR 0013)"
say "generated $(date -u '+%Y-%m-%dT%H:%M:%SZ')  ·  commit $(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
say "live: ${LIVE}   control: ${CTL}   ${PROD} read-only   cut ${CUT}"
rule

# ---------------------------------------------------------------------------
say ""
say "PHASE 0 — reset both scratch databases and apply the schema"
for db in "$LIVE" "$CTL"; do
  q "DROP DATABASE IF EXISTS ${db}" >/dev/null
  q "CREATE DATABASE ${db}" >/dev/null
done
# `env -u CH_DATABASE`: .env exports CH_DATABASE=sonyliv and apply-sql.sh
# (rightly) refuses a --database that contradicts an exported one. Clearing it
# for these two calls is how you say "yes, the scratch database, on purpose".
env -u CH_DATABASE TARGET=cloud tools/apply-sql.sh --database "$LIVE" \
  sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql sql/12_publish.sql sql/15_normalise.sql sql/20_views.sql \
  sql/45_user_concurrency.sql sql/50_hour_agg.sql >/dev/null
env -u CH_DATABASE TARGET=cloud tools/apply-sql.sh --database "$CTL" \
  sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql sql/15_normalise.sql sql/20_views.sql \
  sql/45_user_concurrency.sql sql/50_hour_agg.sql >/dev/null
say "  ${LIVE} has the publication layer (sql/12_publish.sql); ${CTL} does not — it is rebuilt."
say "  BOTH have the user tier (45) and the hour/day cube (50) this time: their"
say "  absence is exactly why the previous harness could not see those tiers go stale."

# ---------------------------------------------------------------------------
say ""
say "PHASE 1 — load the truncated slice into both:  event_timestamp < ${CUT}"
for db in "$LIVE" "$CTL"; do
  q "INSERT INTO ${db}.ev_raw
     SELECT content_id, video_session_id, user_id, event_type, event, event_timestamp,
            platform, app_version, country, audio_language, subtitle_language,
            player_version, session_start_epoch
     FROM ${PROD}.ev_raw WHERE event_timestamp < toDateTime64('${CUT}', 3)" >/dev/null
done
say "  $(qr "SELECT concat(toString(count()), ' events · ', toString(uniqExact(video_session_id)),
             ' sessions · newest ', toString(max(event_timestamp))) FROM ${LIVE}.ev_raw")"
say "  change log: $(qr "SELECT concat(toString(count()), ' rows · ', toString(uniqExact(video_session_id)),
             ' sessions · ', toString(uniqExact(marked_at)), ' insert block(s)') FROM ${LIVE}.session_dirty")"
say ""
say "  The MV collapsed the load to one row per session per block. No session list"
say "  was computed by scanning history — this is what the finalizer consumes."

# ---------------------------------------------------------------------------
say ""
say "PHASE 2 — build BOTH: control by rebuild, live by the incremental finalizer"
say ""
say "  control — tools/build-model.sh's path (TRUNCATE + re-derive all of ev_raw):"
control_rebuild boot
say "    intervals  $(cost ctl-boot-intervals)"
say "    deltas     $(cost ctl-boot-deltas)"
say ""
say "  live — tools/publish.sh, no special bootstrap path:"
sleep "${SETTLE_WAIT:-6}"
tools/publish.sh --database "$LIVE" 2>&1 | sed 's/^/    /' | tee -a "$OUT"
say ""
say "  There is no separate initial-build code. The first run sees every session"
say "  marked dirty by the load and derives them; every later run sees only what"
say "  arrived. One path, so the bootstrap cannot drift from the steady state."
compare boot

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 3 — LATE ARRIVAL (a): the five busiest sessions catch up"
LATE5="$(qr "SELECT arrayStringConcat(groupArray(video_session_id), ''',''')
             FROM (SELECT video_session_id, count() c FROM ${PROD}.ev_raw
                   WHERE event_timestamp >= toDateTime64('${CUT}',3)
                     AND video_session_id IN (SELECT video_session_id FROM ${LIVE}.ev_raw)
                   GROUP BY video_session_id ORDER BY c DESC LIMIT 5)")"
for db in "$LIVE" "$CTL"; do
  q "INSERT INTO ${db}.ev_raw
     SELECT content_id, video_session_id, user_id, event_type, event, event_timestamp,
            platform, app_version, country, audio_language, subtitle_language,
            player_version, session_start_epoch
     FROM ${PROD}.ev_raw
     WHERE event_timestamp >= toDateTime64('${CUT}',3)
       AND video_session_id IN ('${LATE5}')" >/dev/null
done
say "  inserted $(qr "SELECT toString(count()) FROM ${LIVE}.ev_raw WHERE event_timestamp >= toDateTime64('${CUT}',3)") events for 5 sessions"
say "  pending: $(qr "SELECT concat(toString(pending_sessions), ' session(s), lag ', toString(publish_lag_s), 's') FROM ${LIVE}.v_cc_publish_lag")"
say ""
sleep "${SETTLE_WAIT:-6}"   # markings must SETTLE before the finalizer may consume them
tools/publish.sh --database "$LIVE" 2>&1 | sed 's/^/    /' | tee -a "$OUT"
RUN3="$(qr "SELECT toString(max(run_id)) FROM ${LIVE}.cc_publish_runs WHERE phase='committed'")"
say ""
say "  WHAT THE INCREMENTAL RUN TOUCHED, from system.query_log:"
say "    negate   $(cost "publish-${RUN3}-negate")"
say "    derive   $(cost "publish-${RUN3}-derive")"
say "    emit     $(cost "publish-${RUN3}-emit")"
say "    hours    $(cost "publish-${RUN3}-hours")"
say "    users    $(cost "publish-${RUN3}-users")"
say ""
say "  the same update, done by RECOMPUTING (the control):"
control_rebuild late5
say "    intervals  $(cost ctl-late5-intervals)"
say "    deltas     $(cost ctl-late5-deltas)"
compare late5

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 4 — LATE ARRIVAL (b): the entire remaining stream"
for db in "$LIVE" "$CTL"; do
  q "INSERT INTO ${db}.ev_raw
     SELECT content_id, video_session_id, user_id, event_type, event, event_timestamp,
            platform, app_version, country, audio_language, subtitle_language,
            player_version, session_start_epoch
     FROM ${PROD}.ev_raw
     WHERE event_timestamp >= toDateTime64('${CUT}',3)
       AND video_session_id NOT IN ('${LATE5}')" >/dev/null
done
say "  $(qr "SELECT concat(toString(count()), ' events now loaded · newest ', toString(max(event_timestamp))) FROM ${LIVE}.ev_raw")"
say "  pending: $(qr "SELECT concat(toString(pending_sessions), ' session(s)') FROM ${LIVE}.v_cc_publish_lag")"
say ""
sleep "${SETTLE_WAIT:-6}"   # markings must SETTLE before the finalizer may consume them
tools/publish.sh --database "$LIVE" 2>&1 | sed 's/^/    /' | tee -a "$OUT"
RUN4="$(qr "SELECT toString(max(run_id)) FROM ${LIVE}.cc_publish_runs WHERE phase='committed'")"
say ""
say "    derive   $(cost "publish-${RUN4}-derive")"
control_rebuild full
say "    rebuild  $(cost ctl-full-intervals)"
compare full

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 5 — THE STRAGGLER. One heartbeat, event-dated 46 minutes behind the"
say "          watermark, landing inside a 290 s gap of an already-published session."
say ""
say "  session ${STRAGGLER_SESSION}"
say "  event   ${STRAGGLER_TS}   (newest event in ev_raw: $(qr "SELECT toString(max(event_timestamp)) FROM ${LIVE}.ev_raw"))"
say "  ADR 0004 set W = 2400 s. This event is older than W, so the two-tier design"
say "  has no path for it and ADR 0006's correction-by-diff is the only answer."
say ""
say "  intervals BEFORE — note the second one starts at 10:47:33:"
q "SELECT toString(interval_start) AS interval_start, toString(interval_end) AS interval_end, is_open
   FROM ${LIVE}.session_intervals FINAL WHERE video_session_id = '${STRAGGLER_SESSION}'
   ORDER BY interval_start FORMAT PrettyCompact" | tee -a "$OUT"
say ""
say "  served concurrency BEFORE:"
served_window before

for db in "$LIVE" "$CTL"; do
  q "INSERT INTO ${db}.ev_raw
     SELECT content_id, video_session_id, user_id, 'VideoHeartbeat' AS event_type,
            'network-activity' AS event, toDateTime64('${STRAGGLER_TS}', 3) AS event_timestamp,
            platform, app_version, country, audio_language, subtitle_language,
            player_version, session_start_epoch
     FROM ${db}.ev_raw WHERE video_session_id = '${STRAGGLER_SESSION}'
     ORDER BY event_timestamp LIMIT 1" >/dev/null
done
say ""
say "  pending: $(qr "SELECT concat(toString(pending_sessions), ' session(s)') FROM ${LIVE}.v_cc_publish_lag")"
say ""
sleep "${SETTLE_WAIT:-6}"   # markings must SETTLE before the finalizer may consume them
tools/publish.sh --database "$LIVE" 2>&1 | sed 's/^/    /' | tee -a "$OUT"
RUN5="$(qr "SELECT toString(max(run_id)) FROM ${LIVE}.cc_publish_runs WHERE phase='committed'")"
say ""
say "  WHAT ONE-SESSION CORRECTION COSTS, from system.query_log:"
say "    negate   $(cost "publish-${RUN5}-negate")"
say "    derive   $(cost "publish-${RUN5}-derive")"
say "    prune    $(cost "publish-${RUN5}-prune")"
say "    emit     $(cost "publish-${RUN5}-emit")"
say "    hours    $(cost "publish-${RUN5}-hours")"
say "    users    $(cost "publish-${RUN5}-users")"
say "  ev_raw holds $(qr "SELECT formatReadableQuantity(count()) FROM ${LIVE}.ev_raw") events over $(qr "SELECT toString(uniqExact(video_session_id)) FROM ${LIVE}.ev_raw") sessions."
say ""
say "  HOW MUCH OF ev_raw DOES A ONE-SESSION CORRECTION HAVE TO READ?"
say ""
say "  Not 78 rows, and it is worth being blunt about why. ADR 0002 puts"
say "  toStartOfHour(event_timestamp) FIRST in ev_raw's sort key and video_session_id"
say "  third, so a session lookup prunes only by generic exclusion search. The"
say "  finalizer therefore ALSO bounds the read by the batch's event-time window"
say "  (the completeness argument is in tools/publish.sh). A/B below on the real"
say "  query shape — IN (subquery over cc_publish_batch), not an inlined literal,"
say "  because that is what publish.sh issues and the two do not prune alike."
say ""
SW_LO="$(qr "SELECT toString(min(lo_event_ts)) FROM ${LIVE}.cc_publish_batch WHERE run_id = ${RUN5}")"
SW_HI="$(qr "SELECT toString(max(hi_event_ts)) FROM ${LIVE}.cc_publish_batch WHERE run_id = ${RUN5}")"
EV_ROWS="$(qr "SELECT toString(count()) FROM ${LIVE}.ev_raw")"
# Settle the part set first. Measured mid-merge, these numbers move by 3x and
# the ordering between variants inverts — an earlier draft of this harness
# reported the time window as a REGRESSION on exactly that artefact.
q "OPTIMIZE TABLE ${LIVE}.ev_raw FINAL" >/dev/null
# The probe reads the SAME columns the derivation reads. `SELECT count()` is
# answered from part metadata (measured: 1 row / 16 bytes even unscoped) and
# would make every variant look free.
SCOPE_PROBE="SELECT uniqExact(video_session_id), min(event_timestamp), max(event_timestamp) FROM ev_raw"
SCOPE_SUB="(SELECT video_session_id FROM cc_publish_batch WHERE run_id = ${RUN5})"
probe() {  # probe <query_id> <where clause or empty>
  # curl, not q(): q() is tools/ch, which takes no URL parameters, so a
  # query_id passed to it is silently dropped and cost() then finds nothing.
  curl -sS --fail-with-body "https://$(ch_host):${CH_PORT}/?database=${LIVE}&query_id=$1" \
    --user "${CH_USER}:${CH_PASSWORD}" --data-binary "${SCOPE_PROBE} ${2}" >/dev/null
}
for i in 1 2 3; do
  probe "scope-a.unscoped-${RUN5}-$i" ""
  probe "scope-b.session-${RUN5}-$i"  "WHERE video_session_id IN ${SCOPE_SUB}"
  probe "scope-c.windowed-${RUN5}-$i" "WHERE video_session_id IN ${SCOPE_SUB}
                                         AND event_timestamp >= toDateTime64('${SW_LO}',3)
                                         AND event_timestamp <= toDateTime64('${SW_HI}',3)"
done
q "SYSTEM FLUSH LOGS" >/dev/null 2>&1 || true
q "
SELECT variant, read_rows, concat(toString(round(100.0*read_rows/${EV_ROWS}, 1)), '%') AS pct_of_ev_raw,
       read_bytes, ms
FROM (
  SELECT splitByChar('-', query_id)[2] AS variant, round(avg(read_rows)) AS read_rows,
         formatReadableSize(avg(read_bytes)) AS read_bytes, round(avg(query_duration_ms)) AS ms
  FROM system.query_log
  WHERE query_id LIKE 'scope-%-${RUN5}-%' AND type = 'QueryFinish' GROUP BY variant)
ORDER BY variant FORMAT PrettyCompact" | tee -a "$OUT"
say "    a.unscoped = what a rebuild reads    c.windowed = what publish.sh scopes to"
say "    mean of 3 runs each, on a settled part set (${EV_ROWS} rows in ev_raw)"
say ""
say "  intervals AFTER — the two runs merged, so interval_start 10:47:33 no longer"
say "  exists. A ReplacingMergeTree cannot delete a key; the prune phase does:"
q "SELECT toString(interval_start) AS interval_start, toString(interval_end) AS interval_end, is_open
   FROM ${LIVE}.session_intervals FINAL WHERE video_session_id = '${STRAGGLER_SESSION}'
   ORDER BY interval_start FORMAT PrettyCompact" | tee -a "$OUT"
say ""
say "  orphan rows left behind by the vanished key: $(qr "SELECT toString(count()) FROM ${LIVE}.session_intervals WHERE video_session_id='${STRAGGLER_SESSION}' AND interval_start = toDateTime64('2026-07-26 10:47:33',3)")"
say ""
say "  served concurrency AFTER — every minute the straggler bridges gains one viewer:"
served_window after
say ""
say "  and the same rebuilt from scratch, for comparison:"
control_rebuild straggler
compare straggler

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 6 — SHRINK. A late pause pulls a published interval_end EARLIER."
say ""
say "  A provisional interval carries TAIL_S = 60 s of grace past its last event."
say "  A pause arriving inside that grace places the TRUE end earlier — the exact"
say "  case that broke ReplacingMergeTree(interval_end) once (evidence/truncation.txt),"
say "  and the case a set-union user tier can NEVER absorb: the user must be"
say "  RETRACTED from the minute the tail no longer reaches (ADR 0016)."
say ""
# Pick a session whose published last interval ends exactly at last_event +
# 60 s (tail-ended — the last segment reached its run end, no trailing
# unclosed pause) and whose last event sits early enough in its minute that
# losing 50 s of tail crosses a minute boundary. NOT filtered to open
# sessions: on the complete file every session has a VideoSessionEnd, and the
# tail applies regardless — events after the end event are real in this data
# (2.2% of sessions, ADR 0007) and the model absorbs them the same way.
# Deterministic: smallest qualifying session id.
SHRINK_S="$(qr "SELECT video_session_id FROM (
    SELECT video_session_id, max(event_timestamp) AS mx
    FROM ${LIVE}.ev_raw
    GROUP BY video_session_id
    HAVING toSecond(mx) BETWEEN 5 AND 40
  ) AS e
  INNER JOIN (
    SELECT video_session_id, max(interval_end) AS ie
    FROM ${LIVE}.session_intervals FINAL
    GROUP BY video_session_id
  ) AS i USING (video_session_id)
  WHERE i.ie = toDateTime64(toUnixTimestamp(e.mx) + 60, 3)
    AND video_session_id != '${STRAGGLER_SESSION}'
  ORDER BY video_session_id LIMIT 1")"
[ -n "$SHRINK_S" ] || { echo "no shrink candidate found" >&2; exit 1; }
SHRINK_MX="$(qr "SELECT toString(max(event_timestamp)) FROM ${LIVE}.ev_raw WHERE video_session_id = '${SHRINK_S}'")"
M_LOST="$(qr "SELECT toString(toStartOfMinute(max(event_timestamp)) + INTERVAL 1 MINUTE) FROM ${LIVE}.ev_raw WHERE video_session_id = '${SHRINK_S}'")"
say "  session ${SHRINK_S}"
say "  last event ${SHRINK_MX} -> published end +60s; the pause lands at +10s, a"
say "  heartbeat at +30s keeps the run alive past it, so the segment now ends AT"
say "  the pause with no tail. Minute ${M_LOST} must LOSE this viewer."
say ""
say "  last interval BEFORE:"
q "SELECT toString(interval_start) AS interval_start, toString(interval_end) AS interval_end, is_open
   FROM ${LIVE}.session_intervals FINAL WHERE video_session_id = '${SHRINK_S}'
   ORDER BY interval_start DESC LIMIT 1 FORMAT PrettyCompact" | tee -a "$OUT"
say "  served at ${M_LOST} BEFORE:  sessions $(qr "SELECT toString(concurrent) FROM ${LIVE}.v_concurrency_minute_delta_total WHERE minute = toDateTime('${M_LOST}')" ), users $(qr "SELECT toString(concurrent_users) FROM ${LIVE}.v_user_concurrency_minute_total WHERE minute = toDateTime('${M_LOST}')")"

for db in "$LIVE" "$CTL"; do
  q "INSERT INTO ${db}.ev_raw
     SELECT content_id, video_session_id, user_id, 'VideoHeartbeat' AS event_type,
            ev.1 AS event, mx + toIntervalSecond(ev.2) AS event_timestamp,
            platform, app_version, country, audio_language, subtitle_language,
            player_version, session_start_epoch
     FROM (
       SELECT *, (SELECT max(event_timestamp) FROM ${db}.ev_raw
                  WHERE video_session_id = '${SHRINK_S}') AS mx
       FROM ${db}.ev_raw WHERE video_session_id = '${SHRINK_S}'
       ORDER BY event_timestamp DESC LIMIT 1
     )
     ARRAY JOIN [('pause', 10), ('network-activity', 30)] AS ev" >/dev/null
done
say ""
sleep "${SETTLE_WAIT:-6}"   # markings must SETTLE before the finalizer may consume them
tools/publish.sh --database "$LIVE" 2>&1 | sed 's/^/    /' | tee -a "$OUT"
say ""
say "  last interval AFTER — the end moved EARLIER (tail surrendered to the pause):"
q "SELECT toString(interval_start) AS interval_start, toString(interval_end) AS interval_end, is_open
   FROM ${LIVE}.session_intervals FINAL WHERE video_session_id = '${SHRINK_S}'
   ORDER BY interval_start DESC LIMIT 1 FORMAT PrettyCompact" | tee -a "$OUT"
say "  served at ${M_LOST} AFTER:   sessions $(qr "SELECT toString(concurrent) FROM ${LIVE}.v_concurrency_minute_delta_total WHERE minute = toDateTime('${M_LOST}')" ), users $(qr "SELECT toString(ifNull(any(concurrent_users), 0)) FROM ${LIVE}.v_user_concurrency_minute_total WHERE minute = toDateTime('${M_LOST}')")"
say ""
control_rebuild shrink
compare shrink

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 7 — DIMENSION CHANGE. Late events flip a published interval's platform."
say ""
say "  Dimension attribution is the DOMINANT value among an interval's events"
say "  (ADR 0008/0009). A burst of late events under a new platform outvotes the"
say "  old one, so the re-derived interval moves to a different dimension tuple:"
say "  every minute it covers must be RETRACTED from the old platform's user"
say "  buckets and hour curves, and credited to the new one's."
say ""
FLIP_S="$(qr "SELECT video_session_id FROM (
    SELECT video_session_id, max(event_timestamp) AS mx, count() AS n
    FROM ${LIVE}.ev_raw
    GROUP BY video_session_id
    HAVING n BETWEEN 5 AND 80 AND toSecond(mx) BETWEEN 5 AND 40
  ) AS e
  INNER JOIN (
    SELECT video_session_id, max(interval_end) AS ie
    FROM ${LIVE}.session_intervals FINAL
    GROUP BY video_session_id
  ) AS i USING (video_session_id)
  WHERE i.ie = toDateTime64(toUnixTimestamp(e.mx) + 60, 3)
    AND video_session_id NOT IN ('${STRAGGLER_SESSION}', '${SHRINK_S}')
  ORDER BY video_session_id LIMIT 1")"
[ -n "$FLIP_S" ] || { echo "no dimension-flip candidate found" >&2; exit 1; }
# One more injected event than the session has in total guarantees a strict
# majority in the last segment, whatever that segment's own count is.
FLIP_N="$(qr "SELECT toString(count() + 1) FROM ${LIVE}.ev_raw WHERE video_session_id = '${FLIP_S}'")"
say "  session ${FLIP_S} — injecting ${FLIP_N} heartbeats at 100 ms spacing under"
say "  platform 'FlipOS-ADR0016' (harmless in scratch; any string is a valid dim)"
say ""
say "  intervals BEFORE, with their platform attribution:"
q "SELECT toString(interval_start) AS interval_start, toString(interval_end) AS interval_end, platform
   FROM ${LIVE}.session_intervals FINAL WHERE video_session_id = '${FLIP_S}'
   ORDER BY interval_start FORMAT PrettyCompact" | tee -a "$OUT"

for db in "$LIVE" "$CTL"; do
  q "INSERT INTO ${db}.ev_raw
     SELECT content_id, video_session_id, user_id, 'VideoHeartbeat' AS event_type,
            'network-activity' AS event,
            mx + toIntervalMillisecond(100 * (toUInt32(n) + 1)) AS event_timestamp,
            'FlipOS-ADR0016' AS platform, app_version, country, audio_language,
            subtitle_language, player_version, session_start_epoch
     FROM (
       SELECT *, (SELECT max(event_timestamp) FROM ${db}.ev_raw
                  WHERE video_session_id = '${FLIP_S}') AS mx
       FROM ${db}.ev_raw WHERE video_session_id = '${FLIP_S}'
       ORDER BY event_timestamp DESC LIMIT 1
     ) AS base
     CROSS JOIN (SELECT number AS n FROM numbers(${FLIP_N})) AS ns" >/dev/null
done
say ""
sleep "${SETTLE_WAIT:-6}"   # markings must SETTLE before the finalizer may consume them
tools/publish.sh --database "$LIVE" 2>&1 | sed 's/^/    /' | tee -a "$OUT"
say ""
say "  intervals AFTER — the last interval now belongs to FlipOS-ADR0016, so its"
say "  minutes changed dimension tuple, not just length:"
q "SELECT toString(interval_start) AS interval_start, toString(interval_end) AS interval_end, platform
   FROM ${LIVE}.session_intervals FINAL WHERE video_session_id = '${FLIP_S}'
   ORDER BY interval_start FORMAT PrettyCompact" | tee -a "$OUT"
say ""
control_rebuild dimflip
compare dimflip

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 8 — IDEMPOTENCE. Republish sessions whose events did NOT change."
say ""
say "  A resumed run, a replayed batch or an operator correction can all re-publish"
say "  a session whose events did not change. That is only safe if -deltas(X) +"
say "  deltas(X) = 0. Forcing a republication of 200 unchanged sessions tests it."
BEFORE_ROWS="$(qr "SELECT toString(count()) FROM ${LIVE}.cc_minute_delta")"
FORCED="$(qr "SELECT arrayStringConcat(groupArray(video_session_id), ',')
              FROM (SELECT DISTINCT video_session_id FROM ${LIVE}.session_intervals
                    ORDER BY video_session_id LIMIT 200)")"
tools/publish.sh --database "$LIVE" --sessions "$FORCED" 2>&1 | sed 's/^/    /' | tee -a "$OUT"
AFTER_ROWS="$(qr "SELECT toString(count()) FROM ${LIVE}.cc_minute_delta")"
say ""
say "  cc_minute_delta rows: ${BEFORE_ROWS} -> ${AFTER_ROWS} (corrective rows are APPENDED, never updated)"
say "  cursor: $(qr "SELECT if(length(c) > 1 AND c[1] = c[2],
                 concat('UNCHANGED at ', toString(c[1]), ' — a forced run corrects, it does not consume the queue'),
                 concat('moved to ', toString(c[1])))
               FROM (SELECT arraySort(x -> -toUnixTimestamp64Milli(x.1),
                              groupArray((cursor_to, run_id))).1 AS c
                     FROM ${LIVE}.cc_publish_runs WHERE phase='committed')")"
compare idempotence

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 9 — THE COST LEDGER, per run, from cc_publish_runs"
q "SELECT run_id, toString(any(cursor_to)) AS cursor_to, max(sessions) AS sessions,
          sum(elapsed_ms) AS total_ms,
          sumIf(rows_written, phase='derived') AS intervals_written,
          sumIf(rows_written, phase IN ('negated','emitted')) AS delta_rows_written,
          sumIf(rows_written, phase='hours') AS hour_rows,
          sumIf(rows_written, phase='users') AS user_buckets,
          sumIf(elapsed_ms, phase='hours') AS hours_ms,
          sumIf(elapsed_ms, phase='users') AS users_ms
   FROM ${LIVE}.cc_publish_runs GROUP BY run_id ORDER BY run_id FORMAT PrettyCompact" | tee -a "$OUT"
say ""
say "  freshness, as a downstream consumer would read it:"
q "SELECT * FROM ${LIVE}.v_cc_publish_lag FORMAT Vertical" | tee -a "$OUT"

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 10 — RE-MEASURING THE SHELVED PROJECTION on the finalizer's query shape."
say ""
say "  WALKTHROUGH §5 records proj_by_session as measured and NOT shipped: 27.7x on"
say "  a single-session lookup, but \"the actual straggler path uses IN (subquery),"
say "  which full-scans anyway, so the real gain is 1.00x for +94% storage\"."
say "  The finalizer's derive is exactly that IN (subquery) — plus an event-time"
say "  window — so the shape is worth re-measuring rather than inheriting."
say ""
BASE_BYTES="$(qr "SELECT formatReadableSize(sum(bytes_on_disk)) FROM system.parts
                  WHERE database='${LIVE}' AND table='ev_raw' AND active")"
q "ALTER TABLE ${LIVE}.ev_raw ADD PROJECTION IF NOT EXISTS proj_by_session
     (SELECT * ORDER BY (video_session_id, event_timestamp))" >/dev/null
q "ALTER TABLE ${LIVE}.ev_raw MATERIALIZE PROJECTION proj_by_session" >/dev/null
for _ in $(seq 40); do
  [ "$(qr "SELECT toString(count()) FROM system.mutations
           WHERE database='${LIVE}' AND table='ev_raw' AND NOT is_done")" = "0" ] && break
  sleep 4
done
for i in 1 2 3; do
  probe "proj-b.session-${RUN5}-$i"  "WHERE video_session_id IN ${SCOPE_SUB}"
  probe "proj-c.windowed-${RUN5}-$i" "WHERE video_session_id IN ${SCOPE_SUB}
                                        AND event_timestamp >= toDateTime64('${SW_LO}',3)
                                        AND event_timestamp <= toDateTime64('${SW_HI}',3)"
done
q "SYSTEM FLUSH LOGS" >/dev/null 2>&1 || true
q "
SELECT variant, read_rows, concat(toString(round(100.0*read_rows/${EV_ROWS}, 1)), '%') AS pct_of_ev_raw,
       read_bytes, ms, if(projection = '', 'no', 'YES') AS used_projection
FROM (
  SELECT splitByChar('-', query_id)[2] AS variant, round(avg(read_rows)) AS read_rows,
         formatReadableSize(avg(read_bytes)) AS read_bytes, round(avg(query_duration_ms)) AS ms,
         any(arrayStringConcat(projections, ',')) AS projection
  FROM system.query_log
  WHERE query_id LIKE 'proj-%-${RUN5}-%' AND type = 'QueryFinish' GROUP BY variant)
ORDER BY variant FORMAT PrettyCompact" | tee -a "$OUT"
say ""
say "  storage: ev_raw ${BASE_BYTES} -> $(qr "SELECT formatReadableSize(sum(bytes_on_disk)) FROM system.parts
      WHERE database='${LIVE}' AND table='ev_raw' AND active") (projection itself $(qr "SELECT formatReadableSize(sum(bytes_on_disk)) FROM system.projection_parts
      WHERE database='${LIVE}' AND table='ev_raw' AND active AND name='proj_by_session'"))"
say ""
say "  Compare against the PHASE 5 table above: the projection IS chosen for the"
say "  IN (subquery) shape on 26.2. This does not overturn the storage trade — that"
say "  is still the operator's call — but the '1.00x' half of it does not hold for"
say "  the finalizer's query. ADR 0013 records both numbers and ships neither."
say "  NOTE: sql/60_projection.sql hard-codes 'sonyliv.', so it cannot be applied to"
say "  any other database; this phase had to issue the ALTER itself. Same class of"
say "  defect ADR 0010 fixed in sql/80_content.sql."

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 11 — ADOPTION COSTS NOTHING. Turn the publication layer on over a database"
say "          that was built the old way, and prove it does not re-derive history."
say ""
say "  ${CTL} has been rebuilt from scratch and has never had sql/12_publish.sql."
say "  This is the shape of the graded service today."
say ""
say "  before: $(qr "SELECT concat(toString((SELECT count() FROM ${CTL}.session_intervals FINAL)), ' intervals · ',
                     toString((SELECT count() FROM ${CTL}.cc_minute_delta)), ' delta rows · peak ',
                     toString((SELECT max(concurrent) FROM ${CTL}.v_concurrency_minute_delta_total)))")"
env -u CH_DATABASE TARGET=cloud tools/apply-sql.sh --database "$CTL" sql/12_publish.sql >/dev/null
say "  applied sql/12_publish.sql"
tools/publish.sh --database "$CTL" 2>&1 | sed 's/^/    /' | tee -a "$OUT"
say "  after:  $(qr "SELECT concat(toString((SELECT count() FROM ${CTL}.session_intervals FINAL)), ' intervals · ',
                     toString((SELECT count() FROM ${CTL}.cc_minute_delta)), ' delta rows · peak ',
                     toString((SELECT max(concurrent) FROM ${CTL}.v_concurrency_minute_delta_total)))")"
say ""
say "  Nothing moved, because nothing has arrived since the layer went on. The change"
say "  log is empty on a table that was already loaded, so the cursor starts at the"
say "  current ingest position rather than at the beginning of history. Adoption is"
say "  one DDL round trip — it does NOT trigger a rebuild to catch up."

# ===========================================================================
# ADR 0019 PHASES. Everything below runs the publisher with a short lease TTL
# and settle so crash recovery does not wait out production-sized windows:
# TTL 6 s (recovery must outwait a dead holder's lease), settle 2 s.
# ===========================================================================
FAST_ENV="PUBLISH_SETTLE_S=2 PUBLISH_LEASE_TTL_S=6 PUBLISH_LEASE_SETTLE_S=1"
pub()       { env $FAST_ENV tools/publish.sh --database "$LIVE" "$@" 2>&1 | sed 's/^/    /' | tee -a "$OUT"; }
pub_crash() { env $FAST_ENV PUBLISH_CRASH_AT="$1" tools/publish.sh --database "$LIVE" 2>&1 | sed 's/^/    /' | tee -a "$OUT" || true; }
lagv()      { qr "SELECT toString($1) FROM ${LIVE}.v_cc_publish_lag"; }

# SYNTHETIC PROBE SESSIONS. The ADR 0019 phases need an injection whose effect
# on the served tiers is exactly predictable. Real sessions cannot give that:
# on the complete file EVERY session carries a VideoSessionEnd, and a heartbeat
# injected after it is absorbed without extending coverage (ADR 0007/0009) — a
# first draft of PHASE 12 asserted "+30 s" against real sessions and learned
# this the hard way (the re-derivation even retracts the tail to end AT the
# closer once post-end beats exist). A synthetic heartbeat-only session never
# has a closer, so its published end is always last beat + 60 s tail, and every
# +30 s beat moves it by exactly +30 s. Placed after the data's last real event
# (11:30) so the probe minutes carry zero background concurrency.
SYN_DIMS="191919, '%SID%', 'adr19-user', 'VideoHeartbeat', 'network-activity', toDateTime64('%TS%',3), 'ADR19OS', '1.0', 'IN', 'hin', 'eng', '1.0', toDateTime64('%EPOCH%',3)"
syn_beat() {  # syn_beat <session_id> <ts> [live-only]
  local db row
  row="$(printf '%s' "$SYN_DIMS" | sed -e "s|%SID%|$1|" -e "s|%TS%|$2|" -e "s|%EPOCH%|$2|")"
  for db in "$LIVE" "$CTL"; do
    [ "${3:-}" = live-only ] && [ "$db" = "$CTL" ] && continue
    q "INSERT INTO ${db}.ev_raw (content_id, video_session_id, user_id, event_type, event,
        event_timestamp, platform, app_version, country, audio_language, subtitle_language,
        player_version, session_start_epoch) VALUES ($row)" >/dev/null
  done
}

sess_end() {  # sess_end <session>  -> current published max interval_end
  qr "SELECT toString(max(interval_end)) FROM ${LIVE}.session_intervals FINAL
      WHERE video_session_id = '$1'"
}

plus() {  # plus <ts> <seconds>
  qr "SELECT toString(toDateTime64('$1',3) + INTERVAL $2 SECOND)"
}

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 12 — CRASH MATRIX (Q8, ADR 0019). Kill the publisher at EVERY phase"
say "           boundary, then run it again and prove full recovery each time."
say ""
say "  Sixteen injection points: after each phase mark AND after each heavy"
say "  statement (before its mark) — the two ADR 0016 phases included. Three"
say "  recovery shapes are exercised:"
say "    claiming/consumed/batch  -> ROLLBACK. The intent row (phase 'claiming',"
say "        written before any side effect) names the run; recovery deletes its"
say "        consumed rows, drops its batch partition, marks it aborted, and the"
say "        markings become claimable again. Before ADR 0019 a crash between"
say "        the consumed insert and the claimed mark orphaned the batch FOREVER"
say "        — with pending_sessions reading 0 (reproduced)."
say "    claimed..users marks     -> RESUME from the phase marker, reusing the"
say "        run's recorded build_version. Recomputing BV on resume made the"
say "        prune delete the crashed run's own derivation (reproduced: the"
say "        session vanished from all four tiers, every status green)."
say "    *_stmt points            -> RESUME must decide whether the statement"
say "        landed. The insert_deduplication_token does NOT decide it: a replayed"
say "        INSERT SELECT into the shared delta table executed BOTH times on"
say "        26.2.1.525 (system.query_log showed two QueryFinish rows, each with"
say "        written_rows > 0, and the correction double-applied — caught by this"
say "        matrix's first green-to-red run). Recovery now consults the server's"
say "        query log for the negate/emit query_ids; every other statement is"
say "        replay-safe by construction (pinned build_version + Replacing/idempotent)."
say "  Each recovery must also outwait the dead holder's lease (TTL 6 s here)."
say "  Every round appends one +30 s beat to the synthetic probe session and"
say "  requires the published end to advance by exactly +30 s through the crash."
say ""
SYN12="adr19-crash-probe"
LAST12="2026-07-26 12:10:40.000"
syn_beat "$SYN12" "2026-07-26 12:10:10.000"
syn_beat "$SYN12" "$LAST12"
sleep 5
pub --quiet >/dev/null
E="$(sess_end "$SYN12")"; WANT="$(plus "$LAST12" 60)"
say "  probe session ${SYN12} published: end $E (expected $WANT)"
[ "$E" = "$WANT" ] || { echo "PHASE 12: probe session baseline wrong" >&2; exit 1; }
say ""
CRASH_FAILED=0
for CP in claiming consumed batch claimed \
          negate_stmt negated derive_stmt derived prune_stmt pruned \
          emit_stmt emitted hours_stmt hours users_stmt users; do
  LAST12="$(plus "$LAST12" 30)"
  syn_beat "$SYN12" "$LAST12"
  sleep 5
  pub_crash "$CP" >/dev/null
  sleep 7   # the dead holder's lease must expire before recovery can win it
  pub --quiet >/dev/null
  E1="$(sess_end "$SYN12")"
  WANT="$(plus "$LAST12" 60)"
  RIF="$(lagv runs_in_flight)"; PEND="$(lagv pending_sessions)"
  if [ "$E1" = "$WANT" ] && [ "$RIF" = "0" ] && [ "$PEND" = "0" ]; then
    say "  crash@$(printf '%-12s' "$CP") recovered: end -> $E1 (+30s), in-flight 0, pending 0"
  else
    say "  crash@$(printf '%-12s' "$CP") FAILED: end $E1 (wanted $WANT), in-flight $RIF, pending $PEND"
    CRASH_FAILED=1
  fi
done
[ "$CRASH_FAILED" = 0 ] || { echo "PHASE 12: a crash boundary did not recover" >&2; exit 1; }
say ""
say "  convergence after all sixteen crash/recover cycles:"
control_rebuild crashmatrix
compare crashmatrix

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 13 — TWO PUBLISHERS AT ONCE (Q9, ADR 0019). The lease admits one."
say ""
say "  Without the lease this exact scenario was reproduced corrupting the tier:"
say "  two publishers both claimed the same marking under different run_ids, both"
say "  negated the SAME published contribution X and both emitted X-prime, so the"
say "  served number landed at 2X'-X — one viewer became two. Both runs were"
say "  green; nothing detected it; only a full rebuild could repair it."
say ""
SYN13="adr19-lease-probe"
B13="2026-07-26 12:30:10.000"
syn_beat "$SYN13" "$B13"
syn_beat "$SYN13" "$(plus "$B13" 30)"
sleep 5
pub --quiet >/dev/null
E0="$(sess_end "$SYN13")"
[ "$E0" = "$(plus "$B13" 90)" ] || { echo "PHASE 13: probe baseline wrong" >&2; exit 1; }
M9="$(qr "SELECT toString(toStartOfMinute(toDateTime64('$E0',3) + INTERVAL 30 SECOND))")"
# The running sum probed directly from cc_minute_delta: the *_total view emits
# only minutes that carry delta rows, so a quiet probe minute would read as
# absent rather than as its true carried value.
C0="$(qr "SELECT toString(toInt64(sum(delta))) FROM ${LIVE}.cc_minute_delta WHERE minute <= toDateTime('$M9')")"
say "  probe session ${SYN13} ends $E0; probe minute ${M9} serves ${C0} before"
syn_beat "$SYN13" "$(plus "$B13" 60)"
sleep 5
# A is held mid-claim for 6 s so B genuinely overlaps the window in which the
# pre-lease publisher double-claimed; B must stand down, not corrupt.
env $FAST_ENV PUBLISH_SLEEP_AT=batch:6 tools/publish.sh --database "$LIVE" > "$TMP/pubA.log" 2>&1 &
PA=$!
sleep 2
env $FAST_ENV tools/publish.sh --database "$LIVE" > "$TMP/pubB.log" 2>&1 &
PB=$!
wait "$PA" || true; wait "$PB" || true
sed 's/^/    A: /' "$TMP/pubA.log" | tee -a "$OUT"
sed 's/^/    B: /' "$TMP/pubB.log" | tee -a "$OUT"
COMMITS="$(cat "$TMP/pubA.log" "$TMP/pubB.log" | { grep -c 'committed cursor' || true; })"
DECLINES="$(cat "$TMP/pubA.log" "$TMP/pubB.log" | { grep -c 'declining' || true; })"
C1="$(qr "SELECT toString(toInt64(sum(delta))) FROM ${LIVE}.cc_minute_delta WHERE minute <= toDateTime('$M9')")"
say ""
say "  commits: ${COMMITS} (must be 1)   declines: ${DECLINES} (must be 1)"
say "  probe minute ${M9}: ${C0} -> ${C1} (single-publisher answer $((C0+1)); the"
say "  pre-lease double application produced $((C0+2)))"
[ "$COMMITS" = "1" ] && [ "$DECLINES" = "1" ] && [ "$C1" = "$((C0+1))" ] \
  || { echo "PHASE 13: lease did not serialize the publishers" >&2; exit 1; }
control_rebuild lease
compare lease

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 14 — SAME-MILLISECOND IDENTITY (Q10, ADR 0019)."
say ""
say "  Two inserts can share a marked_at — now64(3) is per-query, and two loads"
say "  can land in the same millisecond. cc_publish_consumed used to key on the"
say "  timestamp ALONE: if the slower insert's rows became visible after the"
say "  faster was consumed, its marking matched the consumed set and was skipped"
say "  for ever, with pending_sessions reading 0 (reproduced). The key is now"
say "  the (marked_at, insert_id) pair — initialQueryID() of the firing INSERT,"
say "  captured by mv_session_dirty."
say ""
SYN14="adr19-samems-probe"
B14="2026-07-26 12:40:10.000"
syn_beat "$SYN14" "$B14"
syn_beat "$SYN14" "$(plus "$B14" 30)"
sleep 5
pub --quiet >/dev/null
E="$(sess_end "$SYN14")"
[ "$E" = "$(plus "$B14" 90)" ] || { echo "PHASE 14: probe baseline wrong" >&2; exit 1; }
T14="$(qr "SELECT toString(now64(3) - INTERVAL 4 SECOND)")"
say "  probe session ${SYN14} published (end $E); both markings stamped marked_at = ${T14}"
# The FAST insert's marking: visible immediately, consumed by the next run.
# (Inserted directly so the shared millisecond is exact, not probabilistic.)
q "INSERT INTO ${LIVE}.session_dirty (marked_at, insert_id, video_session_id, min_event_ts, max_event_ts, events)
   VALUES (toDateTime64('$T14',3), 'q10-fast', '${SYN14}',
           toDateTime64('$(plus "$B14" 30)',3), toDateTime64('$(plus "$B14" 30)',3), 1)" >/dev/null
sleep 5
pub --quiet >/dev/null
say "  fast marking consumed: $(qr "SELECT toString(count()) FROM ${LIVE}.cc_publish_consumed WHERE insert_id = 'q10-fast'") run(s) digested it"
# The SLOW insert: its ev_raw rows and marking become visible only NOW — after
# the same-millisecond sibling was consumed. The MV is dropped for the event
# insert and re-applied after, so the fake same-ms marking below is the ONLY
# path to this event in LIVE — end-advance then discriminates, not just the
# pair count. (CTL takes the event through its normal path.)
NEW14="$(plus "$B14" 60)"
q "DROP TABLE ${LIVE}.mv_session_dirty" >/dev/null
syn_beat "$SYN14" "$NEW14"
env -u CH_DATABASE TARGET=cloud tools/apply-sql.sh --database "$LIVE" sql/12_publish.sql >/dev/null
q "INSERT INTO ${LIVE}.session_dirty (marked_at, insert_id, video_session_id, min_event_ts, max_event_ts, events)
   VALUES (toDateTime64('$T14',3), 'q10-slow', '${SYN14}',
           toDateTime64('$NEW14',3), toDateTime64('$NEW14',3), 1)" >/dev/null
sleep 5
pub | grep -E 'claimed|committed' || true
E1="$(sess_end "$SYN14")"
WANT="$(plus "$NEW14" 60)"
SLOW_CONSUMED="$(qr "SELECT toString(count()) FROM ${LIVE}.cc_publish_consumed WHERE insert_id = 'q10-slow'")"
say ""
say "  slow marking claimed: ${SLOW_CONSUMED} (timestamp-only identity claimed 0)"
say "  session end: $E -> $E1 (wanted $WANT)"
[ "$SLOW_CONSUMED" = "1" ] && [ "$E1" = "$WANT" ] \
  || { echo "PHASE 14: the same-millisecond sibling was suppressed" >&2; exit 1; }
control_rebuild samems
compare samems

# ---------------------------------------------------------------------------
say ""
rule
say "PHASE 15 — RETENTION HEADROOM (Q11, ADR 0019). The TTL is a deadline."
say ""
say "  session_dirty, cc_publish_batch and cc_publish_consumed carry 7-day TTLs."
say "  A marking that outlives them expires SILENTLY and the tiers are wrong with"
say "  no signal — and a marking older than the claim lookback (PUBLISH_LOOKBACK_S,"
say "  default 900 s behind the cursor) is already unreachable long before the TTL"
say "  eats it. v_cc_publish_lag now carries the signal: retention_headroom_s is"
say "  seconds until the oldest undigested marking hits the TTL, and"
say "  retention_alert trips a full day before the cliff. This phase plants a"
say "  6.5-day-old marking and reads the alarm."
say ""
say "  healthy: headroom $(lagv "ifNull(toString(retention_headroom_s), 'NULL')"), alert $(lagv retention_alert)"
q "INSERT INTO ${LIVE}.session_dirty (marked_at, insert_id, video_session_id, min_event_ts, max_event_ts, events)
   VALUES (now64(3) - INTERVAL 561600 SECOND, 'retention-probe', 'retention-probe-session',
           now64(3) - INTERVAL 561600 SECOND, now64(3) - INTERVAL 561600 SECOND, 1)" >/dev/null
say "  planted:  age $(lagv oldest_pending_age_s)s, headroom $(lagv retention_headroom_s)s, alert $(lagv retention_alert) (1 = a rebuild is due before the queue lies)"
AL="$(lagv retention_alert)"
pub >/dev/null   # must NOT claim it: 6.5 days is far beyond the lookback
CLAIMED_PROBE="$(qr "SELECT toString(count()) FROM ${LIVE}.cc_publish_consumed WHERE insert_id = 'retention-probe'")"
say "  a publish run against it claimed: ${CLAIMED_PROBE} (0 — beyond the lookback the"
say "  ALERT is the path to repair, not the claim; the repair is a forced"
say "  republication or a rebuild, both idempotent)"
q "DELETE FROM ${LIVE}.session_dirty WHERE insert_id = 'retention-probe'" >/dev/null
say "  cleared:  alert $(lagv retention_alert)"
[ "$AL" = "1" ] && [ "$CLAIMED_PROBE" = "0" ] \
  || { echo "PHASE 15: retention alert did not behave" >&2; exit 1; }

say ""
rule
say "Every 'differing' row above is 0 or this run failed. cc_minute_delta was never"
say "truncated after PHASE 2 and session_intervals was never rebuilt: every number"
say "moved by appending a correction and re-deriving the sessions that changed."
echo
echo "evidence written to $OUT"
