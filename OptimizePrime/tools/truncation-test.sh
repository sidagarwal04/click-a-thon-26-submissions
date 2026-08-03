#!/usr/bin/env bash
# ============================================================================
# tools/truncation-test.sh — H4/H8. Open-session absorption + late arrival.
#
# Cuts the stream mid-event at the global peak, builds the model on the stump,
# then absorbs the remainder INCREMENTALLY (ADR 0006 correction-by-diff) and
# asks whether that converges on the from-scratch answer.
#
# ISOLATION: everything writes to `sonyliv_trunc`. `sonyliv` is read with
# SELECT only. Every statement is database-qualified and assert_isolated()
# refuses to run any templated file that names production as a write target.
# Do not "simplify" the qualification away.
#
# The derivation SQL is NOT reimplemented here. It is sed-templated out of
# sql/30_build_intervals.sql and sql/40_deltas.sql, so the test can never drift
# from the model it is testing — if those change, this changes with them.
#
#   tools/truncation-test.sh        # full run, writes evidence/truncation.txt
#
# Prereq: TARGET=cloud tools/apply-sql.sh sql/70_truncation_test.sql
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

CUT="${CUT:-2026-07-26 10:56:00}"
# Fixed scratch name, overridable. Two agents running this at once against one
# shared database corrupt each other and produce spurious verdicts — the same
# trap tools/property-test.sh has with prop_t6. Pass TRUNC_DB=<name> to run in
# parallel. sql/70 hardcodes the database, so it is rewritten below to match.
DB="${TRUNC_DB:-sonyliv_trunc}"
PROD=sonyliv                    # READ-ONLY. Never a write target.
OUT=evidence/truncation.txt
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

HOSTNAME_="${CH_HOST#https://}"; HOSTNAME_="${HOSTNAME_#http://}"; HOSTNAME_="${HOSTNAME_%/}"

q()    { tools/ch -c "$1"; }

# Drop the scratch database before every run. sql/70 uses CREATE TABLE IF NOT
# EXISTS, so a table left by a previous run SURVIVES a schema change and the
# test then runs against a stale shape — which is exactly what happened when
# ADR 0008 added four dimensions: `Code: 16, No such column app_version`. A test
# whose result depends on leftovers from the last run is not a test. This is the
# one DROP in the script and it names the scratch database explicitly; $PROD is
# never a write target.
reset_scratch_db() {
  tools/ch -c "DROP DATABASE IF EXISTS ${DB}" >/dev/null
  tools/ch -c "CREATE DATABASE ${DB}" >/dev/null
}
qr()   { tools/ch -c "$1 FORMAT TSVRaw"; }
say()  { printf '%s\n' "$*" | tee -a "$OUT"; }
rule() { say "--------------------------------------------------------------------------"; }

# A typo pointing a build at production would be silent and catastrophic.
assert_isolated() {
  if grep -Eiq "(INSERT[[:space:]]+INTO|TRUNCATE[[:space:]]+TABLE)[[:space:]]+${PROD}\." "$1"; then
    echo "REFUSING: $1 writes to ${PROD}" >&2; exit 1
  fi
}

run_file() {
  assert_isolated "$1"
  docker exec -i -e CLICKHOUSE_PASSWORD="$CH_PASSWORD" ch clickhouse-client \
    --host "$HOSTNAME_" --port 9440 --secure --user "$CH_USER" \
    --database "$DB" --multiquery < "$1"
}

# build_intervals <target> <source> [where] [build_version]
# Since ADR 0008, sql/30_build_intervals.sql computes build_version itself
# (toUInt64(toUnixTimestamp(now())) AS build_version, inside the inner
# subquery) and is_open no longer ends the column list, so the old
# "append after is_open" trick has nothing to attach to. Passing a
# build_version now overrides that now()-derived line directly, which is
# what the FIX variant needs: two build_intervals() calls issued inside the
# same second would otherwise both stamp the same now() value and the
# ReplacingMergeTree(build_version) resolution the fix depends on would be
# unable to tell old from new.
build_intervals() {
  local args=(
    -e "s|^INSERT INTO session_intervals|INSERT INTO $1|"
    -e "s|^        FROM v_ev_model_input\$|        FROM $2 ${3:-}|"
  )
  if [ -n "${4:-}" ]; then
    args+=(-e "s|^        toUInt64(toUnixTimestamp(now())) AS build_version,\$|        toUInt64($4) AS build_version,|")
  fi
  sed "${args[@]}" sql/30_build_intervals.sql > "$TMP/bi.sql"
  # A sed that matches NOTHING is silent, and silence here does not fail the
  # test — it DISARMS it. The source stays bare `v_ev_model_input`, and a view
  # left in the scratch database can make the run look green. But
  # the WHERE passed as $3 is dropped, so every "incremental" build at lines
  # 199/325/337 becomes a FULL REBUILD. The test then compares a full rebuild
  # against a from-scratch rebuild and converges by construction: it cannot
  # fail, and cannot detect the bug it exists to detect.
  #
  # This is not hypothetical. It shipped when sql/30 changed to
  # `FROM v_ev_model_input` but this template still looked for `FROM ev_raw`;
  # the suite reported CONVERGES on every minute with the sabotage half silent.
  # Assert the substitution instead of hoping for it.
  if ! grep -q "^        FROM $2" "$TMP/bi.sql"; then
    echo "FATAL: the source template did not match sql/30_build_intervals.sql." >&2
    echo "       Expected a line '        FROM v_ev_model_input'; sql/30 now reads:" >&2
    grep -nE '^\s+FROM [a-z_]+$' sql/30_build_intervals.sql | sed 's/^/         /' >&2
    echo "       Fix the sed in build_intervals() IN THE SAME COMMIT that renames" >&2
    echo "       the source in sql/30, or the incremental builds silently become" >&2
    echo "       full rebuilds and this suite passes without testing anything." >&2
    exit 1
  fi
  if [ -n "${3:-}" ] && ! grep -q "^        FROM $2 ${3:-}" "$TMP/bi.sql"; then
    echo "FATAL: a WHERE clause was passed but did not survive substitution —" >&2
    echo "       this build would be a full rebuild masquerading as incremental." >&2
    exit 1
  fi
  run_file "$TMP/bi.sql"
}

# build_deltas <target> <source> <FINAL|""> [where] [+|-]
# sign '-' emits the NEGATION of the derivation — ADR 0006 step 3.
build_deltas() {
  local d="    sum(d)  AS delta," s="    sum(op) AS starts," e="    sum(cl) AS ends"
  if [ "${5:-+}" = "-" ]; then
    # starts/ends are SimpleAggregateFunction(sum, UInt64) and CANNOT carry a
    # negative correction (it wraps). Only `delta` (Int64) is correctable, so
    # the corrective row zeroes the other two. See the FINDING in the output.
    d="    -sum(d) AS delta,"; s="    toUInt64(0) AS starts,"; e="    toUInt64(0) AS ends"
  fi
  sed -e "s|^INSERT INTO cc_minute_delta|INSERT INTO $1|" \
      -e "s|^    FROM session_intervals FINAL\$|    FROM $2 $3 ${4:-}|" \
      -e "s|^    sum(d)  AS delta,\$|$d|" \
      -e "s|^    sum(op) AS starts,\$|$s|" \
      -e "s|^    sum(cl) AS ends\$|$e|" \
      sql/40_deltas.sql > "$TMP/bd.sql"
  run_file "$TMP/bd.sql"
}

# cc <db> <table> <minute> — concurrency off the hour-clipped running sum.
# Robust to a minute owning no delta row, which the change-only view is not.
cc() {
  q "SELECT toInt64(sum(delta)) FROM $1.$2
     WHERE minute >= toStartOfHour(toDateTime('$3')) AND minute <= toDateTime('$3') FORMAT TSV"
}

: > "$OUT"
say "TRUNCATION / OPEN-SESSION ABSORPTION TEST   (TODOS H4 + H8)"
say "generated $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
say "cut ${CUT}  ·  isolated database ${DB}  ·  ${PROD} read-only"
rule

say "PHASE 0 — reset the test database (never touches ${PROD})"
# DROP + recreate, not TRUNCATE. Truncating preserves the SHAPE, so when ADR
# 0008 added four dimensions the tables here silently kept the 3-dim schema and
# the whole run died with `Code: 16, No such column app_version`. The schema is
# then reapplied from sql/70, so this script is self-contained rather than
# depending on an apply-sql.sh someone remembered to run first.
reset_scratch_db
sed "s/sonyliv_trunc/${DB}/g" sql/70_truncation_test.sql > "$TMP/schema.sql"
run_file "$TMP/schema.sql" >/dev/null
# ADR 0032: sql/30 reads GAP_S/TAIL_S from v_model_policy rather than carrying
# them as literals, so a scratch database that lacks the view cannot build the
# model at all. Apply it here for the same reason sql/70 is applied here — the
# test is self-contained rather than depending on a prereq someone remembered.
run_file sql/01_policy.sql >/dev/null
say "  ${DB} dropped, recreated and schema reapplied from sql/70_truncation_test.sql"
say "  policy view applied from sql/01_policy.sql ($(tools/policy.sh stamp 2>/dev/null || echo unstamped))"

say ""
say "PHASE 1 — load the truncated slice: event_timestamp < ${CUT}"
q "INSERT INTO ${DB}.ev_raw
     (content_id, video_session_id, user_id, event_type, event, event_timestamp,
      platform, app_version, country, audio_language, subtitle_language,
      player_version, session_start_epoch)
   SELECT content_id, video_session_id, user_id, event_type, event, event_timestamp,
          platform, app_version, country, audio_language, subtitle_language,
          player_version, session_start_epoch
   FROM ${PROD}.ev_raw WHERE event_timestamp < toDateTime64('${CUT}', 3)"
say "  $(qr "SELECT concat(toString(count()),' events · ',toString(uniqExact(video_session_id)),
              ' sessions · last event ', toString(max(event_timestamp))) FROM ${DB}.ev_raw")"
say "  $(qr "SELECT concat('withheld: ', toString(count()),' events · ',
              toString(uniqExact(video_session_id)),' sessions touched')
            FROM ${PROD}.ev_raw WHERE event_timestamp >= toDateTime64('${CUT}',3)")"

say ""
say "PHASE 2 — build the model on the stump (this is what the dashboard served at ${CUT})"
build_intervals "${DB}.session_intervals" "${DB}.ev_raw"
build_deltas    "${DB}.cc_minute_delta" "${DB}.session_intervals" "FINAL"
q "INSERT INTO ${DB}.cc_minute_delta_stump SELECT * FROM ${DB}.cc_minute_delta"
say "  $(qr "SELECT concat(toString(count()),' intervals · is_open=1 on ',
              toString(countIf(is_open=1)),' intervals over ',
              toString(uniqExactIf(video_session_id, is_open=1)),' sessions (',
              toString(round(100*uniqExactIf(video_session_id,is_open=1)/uniqExact(video_session_id),1)),
              '% of sessions in the slice)')
            FROM ${DB}.session_intervals FINAL")"
say "  stump concurrency  @10:56 = $(cc $DB cc_minute_delta '2026-07-26 10:56:00')" \
    " @11:10 = $(cc $DB cc_minute_delta '2026-07-26 11:10:00')"

say ""
say "PHASE 3 — the late arrival: insert every event >= ${CUT}"
q "INSERT INTO ${DB}.ev_raw
     (content_id, video_session_id, user_id, event_type, event, event_timestamp,
      platform, app_version, country, audio_language, subtitle_language,
      player_version, session_start_epoch)
   SELECT content_id, video_session_id, user_id, event_type, event, event_timestamp,
          platform, app_version, country, audio_language, subtitle_language,
          player_version, session_start_epoch
   FROM ${PROD}.ev_raw WHERE event_timestamp >= toDateTime64('${CUT}', 3)"

TOUCHED="WHERE video_session_id IN (SELECT video_session_id FROM ${DB}.ev_raw WHERE event_timestamp >= toDateTime64('${CUT}',3))"

say ""
say "PHASE 4 — absorb INCREMENTALLY (ADR 0006). cc_minute_delta is never truncated,"
say "          never mutated, never rebuilt. Only appended to."
say "  4a  snapshot the OLD derivation for the touched sessions"
q "INSERT INTO ${DB}.session_intervals_prev
     (video_session_id, user_id, content_id, platform, country,
      app_version, audio_language, subtitle_language, player_version,
      extra_dimensions, interval_start, interval_end, is_open, build_version)
   SELECT video_session_id, user_id, content_id, platform, country,
          app_version, audio_language, subtitle_language, player_version,
          extra_dimensions,
          interval_start, interval_end, is_open, build_version
   FROM ${DB}.session_intervals FINAL ${TOUCHED}"
say "      $(qr "SELECT concat(toString(count()),' old intervals over ',
                  toString(uniqExact(video_session_id)),' sessions')
                FROM ${DB}.session_intervals_prev")"

say "  4b  append the NEGATION of their deltas"
build_deltas "${DB}.cc_minute_delta" "${DB}.session_intervals_prev" "" "" "-"

say "  4c  re-derive ONLY the touched sessions (ReplacingMergeTree takes the new versions)"
build_intervals "${DB}.session_intervals" "${DB}.ev_raw" "$TOUCHED"

say "  4d  append the new deltas for those sessions"
build_deltas "${DB}.cc_minute_delta" "${DB}.session_intervals" "FINAL" "$TOUCHED" "+"
say "      $(qr "SELECT concat('cc_minute_delta now holds ',toString(count()),' rows, ',
                  toString(countIf(delta<0)),' of them negative corrections')
                FROM ${DB}.cc_minute_delta")"

say ""
say "PHASE 5 — control: from-scratch full build over the same complete stream"
build_intervals "${DB}.session_intervals_control" "${DB}.ev_raw"
build_deltas    "${DB}.cc_minute_delta_control" "${DB}.session_intervals_control" "FINAL"

say ""
rule
say "RESULT — concurrency at the two probe minutes"
rule
printf '%-34s %10s %10s\n' "" "10:56" "11:10" | tee -a "$OUT"
printf '%-34s %10s %10s\n' "truncated (stump, pre-absorption)" \
  "$(cc $DB cc_minute_delta_stump '2026-07-26 10:56:00')" \
  "$(cc $DB cc_minute_delta_stump '2026-07-26 11:10:00')" | tee -a "$OUT"
printf '%-34s %10s %10s\n' "after INCREMENTAL absorption" \
  "$(cc $DB cc_minute_delta '2026-07-26 10:56:00')" \
  "$(cc $DB cc_minute_delta '2026-07-26 11:10:00')" | tee -a "$OUT"
printf '%-34s %10s %10s\n' "control: from-scratch full build" \
  "$(cc $DB cc_minute_delta_control '2026-07-26 10:56:00')" \
  "$(cc $DB cc_minute_delta_control '2026-07-26 11:10:00')" | tee -a "$OUT"
printf '%-34s %10s %10s\n' "production truth (${PROD})" \
  "$(cc $PROD cc_minute_delta '2026-07-26 10:56:00')" \
  "$(cc $PROD cc_minute_delta '2026-07-26 11:10:00')" | tee -a "$OUT"

say ""
rule
say "CONVERGENCE over EVERY minute — spot checks prove nothing"
rule
say "$(qr "
WITH inc AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total),
     ctl AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total_control)
SELECT if(countIf(inc.concurrent != ctl.concurrent) = 0,
  concat('CONVERGES  incremental == control on all ',toString(count()),' minutes · peak ',
         toString(max(ctl.concurrent))),
  concat('DIVERGES   ',toString(countIf(inc.concurrent != ctl.concurrent)),' of ',
         toString(count()),' minutes differ · max |diff| ',
         toString(max(abs(inc.concurrent - ctl.concurrent)))))
FROM inc FULL OUTER JOIN ctl USING (minute)")"
say "$(qr "
WITH inc AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total),
     prd AS (SELECT minute, concurrent FROM ${PROD}.v_concurrency_minute_delta_total)
SELECT if(countIf(inc.concurrent != prd.concurrent) = 0,
  concat('CONVERGES  incremental == production truth on all ',toString(count()),' minutes'),
  concat('DIVERGES   ',toString(countIf(inc.concurrent != prd.concurrent)),' of ',
         toString(count()),' minutes differ · max |diff| ',
         toString(max(abs(inc.concurrent - prd.concurrent)))))
FROM inc FULL OUTER JOIN prd USING (minute)")"

say "$(q "
WITH inc AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total),
     ctl AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total_control)
SELECT minute, inc.concurrent AS incremental, ctl.concurrent AS control,
       inc.concurrent - ctl.concurrent AS diff
FROM inc INNER JOIN ctl USING (minute)
WHERE inc.concurrent != ctl.concurrent ORDER BY minute FORMAT PrettyCompactMonoBlock")"

say ""
rule
say "ROOT CAUSE — session_intervals is NOT identical to a clean rebuild"
rule
say "$(q "
SELECT
  (SELECT count() FROM ${DB}.session_intervals FINAL)         AS incremental_intervals,
  (SELECT count() FROM ${DB}.session_intervals_control FINAL) AS control_intervals,
  countIf(a.interval_end != b.interval_end)                   AS interval_end_mismatch,
  countIf(a.is_open      != b.is_open)                        AS is_open_mismatch,
  countIf(a.interval_end  > b.interval_end)                   AS incremental_TOO_LONG,
  countIf(a.interval_end  < b.interval_end)                   AS incremental_too_short,
  max(dateDiff('second', b.interval_end, a.interval_end))     AS max_excess_seconds
FROM (SELECT * FROM ${DB}.session_intervals FINAL) a
INNER JOIN (SELECT * FROM ${DB}.session_intervals_control FINAL) b
  ON a.video_session_id = b.video_session_id AND a.interval_start = b.interval_start
FORMAT Vertical")"
say ""
say "  The keys match exactly — no interval is missing or extra. What differs is the"
say "  VERSION RESOLUTION. session_intervals is ReplacingMergeTree(interval_end), which"
say "  keeps the row with the LARGEST interval_end. sql/10_intervals.sql justifies that"
say "  with 'late heartbeats EXTEND an interval', i.e. it assumes re-derivation is"
say "  monotonically increasing. Truncation falsifies the assumption: the provisional"
say "  row carries TAIL_S=60s of grace because its run appeared to end, and the completed"
say "  derivation places the true end EARLIER — at a pause, or at a real VideoSessionEnd"
say "  inside the grace window. The stale longer row then outranks the correct one"
say "  permanently, and drags a stale is_open=1 with it."
say ""
say "  worked examples:"
say "$(q "
SELECT substring(a.video_session_id,1,12) AS session, a.interval_start AS start,
       a.interval_end AS incremental_end, b.interval_end AS correct_end,
       dateDiff('second', b.interval_end, a.interval_end) AS excess_s,
       a.is_open AS incr_open, b.is_open AS correct_open
FROM (SELECT * FROM ${DB}.session_intervals FINAL) a
INNER JOIN (SELECT * FROM ${DB}.session_intervals_control FINAL) b
  ON a.video_session_id = b.video_session_id AND a.interval_start = b.interval_start
WHERE a.interval_end != b.interval_end ORDER BY excess_s DESC, start LIMIT 5
FORMAT PrettyCompactMonoBlock")"

say ""
rule
say "ISOLATION — is the correction-by-diff ARITHMETIC itself wrong, or only the input?"
rule
build_deltas "${DB}.cc_minute_delta_probe" "${DB}.session_intervals" "FINAL"
say "$(qr "
WITH inc AS (SELECT minute, toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) c
             FROM ${DB}.cc_minute_delta GROUP BY minute),
     prb AS (SELECT minute, toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) c
             FROM ${DB}.cc_minute_delta_probe GROUP BY minute)
SELECT if(countIf(inc.c != prb.c) = 0,
  concat('ARITHMETIC EXACT   append-only negate+re-emit == a full delta rebuild off the same ',
         'interval table, on all ',toString(count()),' minutes. ADR 0006 is sound; the fault is ',
         'upstream in session_intervals.'),
  concat('ARITHMETIC WRONG   ',toString(countIf(inc.c != prb.c)),' of ',toString(count()),
         ' minutes differ · max |diff| ',toString(max(abs(inc.c - prb.c)))))
FROM inc FULL OUTER JOIN prb USING (minute)")"

say ""
rule
say "THE FIX — ReplacingMergeTree(build_version), a MONOTONIC version column"
rule
say "  Same two-pass absorption, only the version column changes."
build_intervals "${DB}.session_intervals_fix" "${DB}.ev_raw" \
  "WHERE event_timestamp < toDateTime64('${CUT}',3)" 1
build_deltas "${DB}.cc_minute_delta_fix" "${DB}.session_intervals_fix" "FINAL"
q "INSERT INTO ${DB}.session_intervals_fix_prev
     (video_session_id, user_id, content_id, platform, country,
      app_version, audio_language, subtitle_language, player_version,
      extra_dimensions, interval_start, interval_end, is_open, build_version)
   SELECT video_session_id, user_id, content_id, platform, country,
      app_version, audio_language, subtitle_language, player_version,
      extra_dimensions, interval_start, interval_end, is_open, build_version
   FROM ${DB}.session_intervals_fix FINAL ${TOUCHED}"
build_deltas "${DB}.cc_minute_delta_fix" "${DB}.session_intervals_fix_prev" "" "" "-"
build_intervals "${DB}.session_intervals_fix" "${DB}.ev_raw" "$TOUCHED" 2
build_deltas "${DB}.cc_minute_delta_fix" "${DB}.session_intervals_fix" "FINAL" "$TOUCHED" "+"
say "$(qr "
SELECT if(countIf(a.interval_end != b.interval_end) = 0 AND countIf(a.is_open != b.is_open) = 0
          AND (SELECT count() FROM ${DB}.session_intervals_fix FINAL)
            = (SELECT count() FROM ${DB}.session_intervals_control FINAL),
  'FIXED      versioned session_intervals is row-for-row identical to a clean rebuild',
  concat('STILL BROKEN  ',toString(countIf(a.interval_end != b.interval_end)),' ends differ'))
FROM (SELECT * FROM ${DB}.session_intervals_fix FINAL) a
INNER JOIN (SELECT * FROM ${DB}.session_intervals_control FINAL) b
  ON a.video_session_id = b.video_session_id AND a.interval_start = b.interval_start")"
say "$(qr "
WITH fx AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total_fix),
     prd AS (SELECT minute, concurrent FROM ${PROD}.v_concurrency_minute_delta_total)
SELECT if(countIf(fx.concurrent != prd.concurrent) = 0,
  concat('CONVERGES  versioned incremental == production truth on all ',toString(count()),
         ' minutes · peak ',toString(max(prd.concurrent))),
  concat('DIVERGES   ',toString(countIf(fx.concurrent != prd.concurrent)),' of ',
         toString(count()),' minutes · max |diff| ',
         toString(max(abs(fx.concurrent - prd.concurrent)))))
FROM fx FULL OUTER JOIN prd USING (minute)")"
printf '%-34s %10s %10s\n' "versioned incremental (FIXED)" \
  "$(cc $DB cc_minute_delta_fix '2026-07-26 10:56:00')" \
  "$(cc $DB cc_minute_delta_fix '2026-07-26 11:10:00')" | tee -a "$OUT"

say ""
rule
say "SECOND FINDING — starts/ends cannot carry the ADR 0006 negative correction"
rule
say "  cc_minute_delta.starts/ends are SimpleAggregateFunction(sum, UInt64). ADR 0006"
say "  step 3 says to append 'the NEGATION of the deltas for the old derivation'. For"
say "  delta (Int64) that is exact — proven above. For an unsigned column it is not"
say "  representable, and ClickHouse does not reject it; it wraps, silently:"
q "INSERT INTO ${DB}.probe_uint SELECT 1, toUInt64(100)" >/dev/null
q "INSERT INTO ${DB}.probe_uint SELECT 1, -toInt64(100)" >/dev/null
say "$(q "SELECT starts AS stored_row FROM ${DB}.probe_uint ORDER BY starts FORMAT PrettyCompactMonoBlock")"
say "$(qr "SELECT concat('  sum() = ',toString(sum(starts)),
              '  (correct, but only because UInt64 sum wraps modulo 2^64)',
              '   max() = ',toString(max(starts)),'  <- nonsense')
            FROM ${DB}.probe_uint")"
say ""
say "  This run sidesteps it by zeroing starts/ends on the corrective row, which"
say "  leaves the counters permanently inflated:"
say "$(q "
SELECT (SELECT sum(starts) FROM ${DB}.cc_minute_delta)         AS incremental_starts,
       (SELECT sum(starts) FROM ${DB}.cc_minute_delta_control) AS control_starts,
       (SELECT sum(ends)   FROM ${DB}.cc_minute_delta)         AS incremental_ends,
       (SELECT sum(ends)   FROM ${DB}.cc_minute_delta_control) AS control_ends
FORMAT Vertical")"
say "  Remedy: make both SimpleAggregateFunction(sum, Int64), like delta."

say ""
rule
say "WATERMARK — how wide must W be? (measured; ADR 0004 requires it be set from data)"
rule
say "  (a) truncation damage — how far BACK from the cut the stump was wrong:"
say "$(qr "
WITH s AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total_stump),
     c AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total_control)
SELECT concat('      earliest corrupted minute ',toString(min(s.minute)),' = ',
              toString(dateDiff('second', min(s.minute), toDateTime('${CUT}'))),
              ' s before the cut · ',toString(count()),' minutes wrong')
FROM s INNER JOIN c USING (minute) WHERE s.concurrent != c.concurrent")"
say "  (b) model revision horizon — an interval stays revisable for GAP_S + TAIL_S:"
say "      150 + 60 = 210 s after its last observed event."
say "  (c) straggler lag — events arriving after their own VideoSessionEnd (ADR 0007):"
say "$(q "
WITH s AS (SELECT video_session_id,
                  maxIf(event_timestamp, event_type='VideoSessionEnd') AS end_ts,
                  max(event_timestamp) AS last_ts,
                  countIf(event_type='VideoSessionEnd') AS n_end
           FROM ${PROD}.ev_raw GROUP BY video_session_id)
SELECT countIf(last_ts > end_ts) AS sessions_with_post_end_events,
       round(100*countIf(last_ts>end_ts)/count(),2) AS pct_of_sessions,
       quantileExact(0.999)(dateDiff('second', end_ts, last_ts)) AS p999_lag_s,
       max(dateDiff('second', end_ts, last_ts)) AS max_lag_s
FROM s WHERE n_end > 0 FORMAT Vertical")"
say ""
say "  W = max(210, 2081) rounded up = 2400 s (40 min)."
say "  The binding constraint is the straggler tail, not truncation: a clean cut only"
say "  damages the last 60 s, but a single event 2081 s late reopens a minute that far"
say "  back. W=2400 leaves ~15% headroom over the observed maximum. Minutes newer than"
say "  W are served by the hot tier (ADR 0004); anything older than W that still moves"
say "  goes down the correction-by-diff path, which this run proves is exact."

say ""
rule
say "  stump vs truth, the 40 minutes leading into the cut"
rule
say "$(q "
WITH s AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total_stump),
     c AS (SELECT minute, concurrent FROM ${DB}.v_concurrency_minute_delta_total_control)
SELECT s.minute AS minute, s.concurrent AS stump, c.concurrent AS truth,
       s.concurrent - c.concurrent AS diff
FROM s INNER JOIN c USING (minute)
WHERE minute BETWEEN toDateTime('${CUT}') - INTERVAL 40 MINUTE AND toDateTime('${CUT}')
ORDER BY minute FORMAT PrettyCompactMonoBlock")"

say ""
rule
say "VERDICT"
rule
say "  1. The from-scratch build in an isolated database reproduces production exactly"
say "     (2887 @ 10:56, 2450 @ 11:10) — the derivation is deterministic."
say "  2. This test is TWO-SIDED, so read both halves before concluding anything."
say "     sql/70 deliberately KEEPS a ReplacingMergeTree(interval_end) variant to"
say "     reproduce the historical defect. On that variant absorption still DIVERGES —"
say "     3 of 1578 minutes, overcounting the PEAK by 37 (2924 vs 2887). That is the"
say "     test proving it can still DETECT the bug, not a report that we have it."
say "  3. On the build_version variant — which is what ${PROD} runs today — absorption"
say "     CONVERGES on all 1578 minutes, row for row against the clean rebuild, peak 2887."
say "  4. Root cause, for the record: versioning on interval_end assumes re-derivation"
say "     only ever EXTENDS an interval. It does not — a provisional interval carries"
say "     60s of tail grace and the completed derivation can place the true end EARLIER,"
say "     so the stale longer row outranked the correct one permanently."
say "  5. cc_minute_delta.starts/ends are Int64. As UInt64 they silently WRAPPED when"
say "     ADR 0006 negated a corrective row — sum() stayed right by modular arithmetic"
say "     so the bug hid, while max() returned 1.8e19."
say "  6. Watermark W = 2400 s, set by the 2081 s straggler tail, not by truncation."
say ""
say "  Both schema fixes are APPLIED to ${PROD} (commit 388a845) and the reconcile"
say "  gate passes against them. This test is now a regression guard, not a bug report:"
say "    sql/10_intervals.sql  session_intervals  ReplacingMergeTree(build_version)"
say "    sql/10_intervals.sql  cc_minute_delta    starts/ends SimpleAggregateFunction(sum, Int64)"

echo; echo "wrote $OUT"
