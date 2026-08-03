#!/usr/bin/env bash
# tools/edge-test.sh — the executable edge-case matrix (Codex 003 §11 / §13.1).
# Runs hand-derived golden fixtures (tests/edge/fixtures/) through the REAL derivation
# (sql/30_build_intervals.sql + sql/40_deltas.sql + sql/45_user_concurrency.sql,
# sed-templated, never reimplemented) in scratch db `edge_matrix`, and compares
# against expected intervals, session minutes, and exact user minutes whose values
# were derived BY HAND from the spec — never from the model under test.
# Usage: tools/edge-test.sh           run the matrix, PASS/FAIL per fixture
#        tools/edge-test.sh sabotage  prove fixtures can fail: mutate the SQL stream,
#                                     assert the paired fixture goes red. Disk untouched.
# SAFETY: local-only; refuses TARGET=cloud; the graded `sonyliv` db is never named.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB=edge_matrix
FIXDIR="$ROOT/tests/edge/fixtures"

if [ "${TARGET:-local}" != local ]; then
  echo "edge-test: TARGET='${TARGET}' refused — this harness is LOCAL-ONLY (graded-db rule)." >&2
  exit 1
fi

ch() { TARGET=local "$ROOT/tools/ch" "$1"; }

# --------------------------------------------------------------------------- preflight
preflight() {
  local tz
  tz="$(ch "SELECT timezone()")"
  if [ "$tz" != "UTC" ]; then
    echo "edge-test: server timezone is '$tz', not UTC — every hand-derived expectation" >&2
    echo "assumes UTC (see evidence/adversarial/README.md row 16). Refusing to run." >&2
    exit 1
  fi
}

# --------------------------------------------------------------------------- schema
setup_schema() {
  ch "DROP DATABASE IF EXISTS ${DB}"
  ch "CREATE DATABASE ${DB}"

  # ev_raw clone + a `batch` column so late-data fixtures can stage arrivals.
  # The templated derivation reads named columns only, so the extra column is inert.
  ch "CREATE TABLE ${DB}.ev_raw (
        batch UInt8,
        content_id Int64, video_session_id String, user_id String,
        event_type LowCardinality(String), event LowCardinality(String),
        event_timestamp DateTime64(3),
        platform LowCardinality(String), app_version LowCardinality(String),
        country LowCardinality(String), audio_language LowCardinality(String),
        subtitle_language LowCardinality(String), player_version LowCardinality(String),
        session_start_epoch DateTime64(3),
        extra Map(LowCardinality(String), String) DEFAULT map()
      ) ENGINE = MergeTree ORDER BY (video_session_id, event_timestamp)"

  # session_intervals / cc_minute_delta clones — SAME engines as production
  # (sql/10_intervals.sql) so FINAL and merge semantics are identical.
  local si_cols="video_session_id String, user_id String, content_id Int64,
        platform LowCardinality(String), country LowCardinality(String),
        app_version LowCardinality(String), audio_language LowCardinality(String),
        subtitle_language LowCardinality(String), player_version LowCardinality(String),
        extra_dimensions Map(LowCardinality(String), String) DEFAULT map(),
        interval_start DateTime64(3), interval_end DateTime64(3),
        is_open UInt8, build_version UInt64"
  local dt_cols="minute DateTime,
        platform LowCardinality(String), country LowCardinality(String), content_id Int64,
        subtitle_language LowCardinality(String), player_version LowCardinality(String),
        audio_language LowCardinality(String), app_version LowCardinality(String),
        delta SimpleAggregateFunction(sum, Int64),
        starts SimpleAggregateFunction(sum, Int64),
        ends SimpleAggregateFunction(sum, Int64)"
  ch "CREATE TABLE ${DB}.session_intervals (${si_cols})
      ENGINE = ReplacingMergeTree(build_version) ORDER BY (video_session_id, interval_start)"
  ch "CREATE TABLE ${DB}.si_old (${si_cols})
      ENGINE = ReplacingMergeTree(build_version) ORDER BY (video_session_id, interval_start)"
  ch "CREATE TABLE ${DB}.cc_minute_delta (${dt_cols})
      ENGINE = AggregatingMergeTree ORDER BY (platform, country, content_id, minute,
        subtitle_language, player_version, audio_language, app_version)"
  ch "CREATE TABLE ${DB}.delta_old  (${dt_cols})
      ENGINE = AggregatingMergeTree ORDER BY (platform, country, content_id, minute,
        subtitle_language, player_version, audio_language, app_version)"
  ch "CREATE TABLE ${DB}.delta_corr (${dt_cols})
      ENGINE = AggregatingMergeTree ORDER BY (platform, country, content_id, minute,
        subtitle_language, player_version, audio_language, app_version)"
  ch "CREATE TABLE ${DB}.cc_user_minute (
        minute DateTime,
        platform LowCardinality(String), country LowCardinality(String), content_id Int64,
        active_state AggregateFunction(uniqExact, String),
        computed_at DateTime64(3) DEFAULT now64(3)
      ) ENGINE = ReplacingMergeTree(computed_at)
        PARTITION BY toYYYYMMDD(minute)
        ORDER BY (platform, country, content_id, minute)"

  # Hand-derived expectations. platform/audio_language '*' = not asserted.
  ch "CREATE TABLE ${DB}.expected_intervals (
        video_session_id String, interval_start DateTime64(3), interval_end DateTime64(3),
        is_open UInt8, platform String DEFAULT '*', audio_language String DEFAULT '*',
        video_resolution String DEFAULT '*',
        extra_dimensions Map(LowCardinality(String), String) DEFAULT map()
      ) ENGINE = MergeTree ORDER BY (video_session_id, interval_start)"
  ch "CREATE TABLE ${DB}.expected_minutes (
        fixture String, minute DateTime, platform String DEFAULT '*', cc Int64
      ) ENGINE = MergeTree ORDER BY (fixture, platform, minute)"
  ch "CREATE TABLE ${DB}.expected_user_minutes (
        fixture String, minute DateTime, platform String DEFAULT '*', users UInt64
      ) ENGINE = MergeTree ORDER BY (fixture, platform, minute)"
  ch "CREATE TABLE ${DB}.expected_no_interval (
        video_session_id String, interval_start DateTime64(3)
      ) ENGINE = MergeTree ORDER BY (video_session_id, interval_start)"
  ch "CREATE TABLE ${DB}.fixture_span (
        fixture String, t_from DateTime, t_to DateTime, is_late UInt8 DEFAULT 0
      ) ENGINE = MergeTree ORDER BY fixture"
}

# --------------------------------------------------------------------------- fixtures
# Fixture files hold multiple statements; the HTTP interface takes one per request,
# so split on lines ending in ';'. Comment lines must not end in ';'.
send_file() {
  local f="$1" buf=""
  while IFS= read -r line || [ -n "$line" ]; do
    buf+="$line"$'\n'
    case "$line" in
      --*) ;;  # a ';' at the end of a comment line is not a terminator
      *\;) ch "$buf"; buf="";;
    esac
  done < "$f"
  if printf '%s' "$buf" | grep -qvE '^\s*(--.*)?$'; then
    echo "edge-test: trailing non-statement content in $f" >&2; exit 1
  fi
}

load_fixtures() {
  local f
  for f in "$FIXDIR"/*.sql; do send_file "$f"; done
}

# --------------------------------------------------------------------------- build
# The production derivation, templated exactly like evidence/adversarial/README.md:
# only the INSERT target and the FROM source change. Optional sabotage seds are
# applied to the STREAM — the files on disk are never modified.
SAB30="${SAB30:-}"   # extra sed program for 30_build_intervals.sql
SAB40="${SAB40:-}"   # extra sed program for 40_deltas.sql
SAB45="${SAB45:-}"   # extra sed program for 45_user_concurrency.sql
CORRMODE="${CORRMODE:-full}"  # full | drop-vanished (sabotage 8)

assert_isolated() {  # every INSERT must target edge_matrix; sonyliv must not appear
  local sql="$1"
  if printf '%s' "$sql" | grep -q 'sonyliv'; then
    echo "edge-test: templated SQL names sonyliv — refusing" >&2; exit 1
  fi
  if printf '%s' "$sql" | grep 'INSERT INTO' | grep -qv "INSERT INTO ${DB}\."; then
    echo "edge-test: templated SQL has an INSERT outside ${DB} — refusing" >&2; exit 1
  fi
}

build_pass() {  # $1 = si target, $2 = delta target, $3 = max batch
  local si="$1" dt="$2" maxb="$3" sql30 sql40
  sql30="$(sed -e "s/INSERT INTO session_intervals/INSERT INTO ${DB}.${si}/" \
               -e "s/FROM v_ev_model_input/FROM ${DB}.ev_raw WHERE batch <= ${maxb}/" \
               "$ROOT/sql/30_build_intervals.sql")"
  [ -n "$SAB30" ] && sql30="$(printf '%s' "$sql30" | sed -e "$SAB30")"
  assert_isolated "$sql30"
  ch "$sql30"

  sql40="$(sed -e "s/INSERT INTO cc_minute_delta/INSERT INTO ${DB}.${dt}/" \
               -e "s/FROM session_intervals FINAL/FROM ${DB}.${si} FINAL/" \
               "$ROOT/sql/40_deltas.sql")"
  [ -n "$SAB40" ] && sql40="$(printf '%s' "$sql40" | sed -e "$SAB40")"
  assert_isolated "$sql40"
  ch "$sql40"
}

build_users() {
  local sql45
  sql45="$(sed -n '/PUBLISH_EXTRACT_BEGIN:user/,/PUBLISH_EXTRACT_END:user/p' \
                "$ROOT/sql/45_user_concurrency.sql")"
  [ -n "$SAB45" ] && sql45="$(printf '%s' "$sql45" | sed -e "$SAB45")"
  sql45="$(printf '%s' "$sql45" | sed \
               -e "s/INSERT INTO cc_user_minute/INSERT INTO ${DB}.cc_user_minute/" \
               -e "s/FROM session_intervals AS si FINAL/FROM ${DB}.session_intervals AS si FINAL/g" \
               -e "s/FROM session_intervals FINAL/FROM ${DB}.session_intervals FINAL/g" \
               -e "s/FROM cc_user_minute FINAL/FROM ${DB}.cc_user_minute FINAL/g")"
  assert_isolated "$sql45"
  ch "$sql45"
}

DIMS="platform, country, content_id, subtitle_language, player_version, audio_language, app_version"

build_all() {
  ch "TRUNCATE TABLE ${DB}.session_intervals"
  ch "TRUNCATE TABLE ${DB}.cc_minute_delta"
  ch "TRUNCATE TABLE ${DB}.si_old"
  ch "TRUNCATE TABLE ${DB}.delta_old"
  ch "TRUNCATE TABLE ${DB}.delta_corr"
  ch "TRUNCATE TABLE ${DB}.cc_user_minute"

  build_pass si_old delta_old 1                 # the world before the late events
  build_pass session_intervals cc_minute_delta 99   # the world after (full rebuild)
  build_users

  # ADR 0006 correction-by-diff: negate EVERY old row of the touched sessions, then
  # append the new rows, in one block. Here every session counts as touched.
  # CORRMODE=drop-vanished is deliberately WRONG (sabotage 8): it only negates old
  # rows whose (minute, dims) key still exists in the new build — the classic bug
  # that leaves vanished minutes/dimensions serving stale +1s for ever.
  local oldfilter=""
  if [ "$CORRMODE" = drop-vanished ]; then
    oldfilter="WHERE (minute, ${DIMS}) IN (SELECT minute, ${DIMS} FROM ${DB}.cc_minute_delta)"
  fi
  ch "INSERT INTO ${DB}.delta_corr
      SELECT minute, ${DIMS}, -delta, -starts, -ends FROM ${DB}.delta_old ${oldfilter}
      UNION ALL
      SELECT minute, ${DIMS},  delta,  starts,  ends FROM ${DB}.cc_minute_delta"
}

# --------------------------------------------------------------------------- checks
CORRECTED_SRC="(SELECT * FROM ${DB}.delta_old UNION ALL SELECT * FROM ${DB}.delta_corr)"

q_intervals() {  # $1 = fixture
  cat <<SQL
WITH
 e AS (SELECT video_session_id, interval_start, interval_end, is_open, platform, audio_language,
              video_resolution, extra_dimensions
       FROM ${DB}.expected_intervals WHERE startsWith(video_session_id, '$1_')),
 a AS (SELECT video_session_id, interval_start, interval_end, is_open,
              toString(platform) AS platform, toString(audio_language) AS audio_language,
              extra_dimensions['video_resolution'] AS video_resolution, extra_dimensions
       FROM ${DB}.session_intervals FINAL WHERE startsWith(video_session_id, '$1_'))
SELECT
  if(a.video_session_id = '', 'missing', if(e.video_session_id = '', 'unexpected', 'mismatch')) AS kind,
  if(a.video_session_id = '', e.video_session_id, a.video_session_id) AS sid,
  if(a.video_session_id = '', e.interval_start, a.interval_start)     AS start,
  e.interval_end AS want_end, a.interval_end AS got_end,
  e.is_open AS want_open, a.is_open AS got_open,
  e.platform AS want_pf, a.platform AS got_pf,
  e.audio_language AS want_au, a.audio_language AS got_au,
  e.video_resolution AS want_resolution, a.video_resolution AS got_resolution,
  toJSONString(e.extra_dimensions) AS want_extra,
  toJSONString(a.extra_dimensions) AS got_extra
FROM e FULL OUTER JOIN a
  ON e.video_session_id = a.video_session_id AND e.interval_start = a.interval_start
WHERE e.video_session_id = '' OR a.video_session_id = ''
   OR e.interval_end != a.interval_end OR e.is_open != a.is_open
   OR (e.platform != '*' AND e.platform != a.platform)
   OR (e.audio_language != '*' AND e.audio_language != a.audio_language)
   OR (e.video_resolution != '*' AND e.video_resolution != a.video_resolution)
   OR (length(e.extra_dimensions) > 0 AND e.extra_dimensions != a.extra_dimensions)
ORDER BY sid, start
SQL
}

q_minutes_total() {  # $1 = fixture, $2 = delta source
  cat <<SQL
WITH
  (SELECT t_from FROM ${DB}.fixture_span WHERE fixture = '$1') AS lo,
  (SELECT t_to   FROM ${DB}.fixture_span WHERE fixture = '$1') AS hi,
  d AS (SELECT minute, toInt64(sum(delta)) AS dl FROM $2
        WHERE minute >= lo AND minute < hi GROUP BY minute),
  grid AS (SELECT h + toIntervalMinute(toInt64(n)) AS minute
           FROM (SELECT DISTINCT toStartOfHour(minute) AS h FROM d) AS hh
           CROSS JOIN (SELECT number AS n FROM numbers(60)) AS nn),
  act AS (SELECT minute, sum(dl) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute) AS cc
          FROM (SELECT g.minute AS minute, coalesce(d.dl, toInt64(0)) AS dl
                FROM grid g LEFT JOIN d ON g.minute = d.minute)),
  exp AS (SELECT minute, cc FROM ${DB}.expected_minutes WHERE fixture = '$1' AND platform = '*')
SELECT if(a.minute = toDateTime(0), e.minute, a.minute) AS m, e.cc AS want, a.cc AS got
FROM act a FULL OUTER JOIN exp e ON a.minute = e.minute
WHERE e.cc != a.cc
ORDER BY m
SQL
}

q_minutes_platform() {  # $1 = fixture, $2 = delta source
  cat <<SQL
WITH
  (SELECT t_from FROM ${DB}.fixture_span WHERE fixture = '$1') AS lo,
  (SELECT t_to   FROM ${DB}.fixture_span WHERE fixture = '$1') AS hi,
  d AS (SELECT minute, toString(platform) AS pf, toInt64(sum(delta)) AS dl FROM $2
        WHERE minute >= lo AND minute < hi GROUP BY minute, platform),
  grid AS (SELECT h + toIntervalMinute(toInt64(n)) AS minute, pf
           FROM (SELECT DISTINCT toStartOfHour(minute) AS h, pf FROM d) AS hh
           CROSS JOIN (SELECT number AS n FROM numbers(60)) AS nn),
  act AS (SELECT minute, pf, sum(dl) OVER (PARTITION BY pf, toStartOfHour(minute) ORDER BY minute) AS cc
          FROM (SELECT g.minute AS minute, g.pf AS pf, coalesce(d.dl, toInt64(0)) AS dl
                FROM grid g LEFT JOIN d ON g.minute = d.minute AND g.pf = d.pf)),
  exp AS (SELECT minute, platform AS pf, cc FROM ${DB}.expected_minutes
          WHERE fixture = '$1' AND platform != '*')
SELECT if(a.minute = toDateTime(0), e.minute, a.minute) AS m,
       if(a.pf = '', e.pf, a.pf) AS pf, e.cc AS want, a.cc AS got
FROM act a FULL OUTER JOIN exp e ON a.minute = e.minute AND a.pf = e.pf
WHERE e.cc != a.cc
ORDER BY m, pf
SQL
}

q_users_total() {  # $1 = fixture
  cat <<SQL
WITH
  (SELECT t_from FROM ${DB}.fixture_span WHERE fixture = '$1') AS lo,
  (SELECT t_to   FROM ${DB}.fixture_span WHERE fixture = '$1') AS hi,
  a AS (
    SELECT minute, uniqExactMerge(active_state) AS users
    FROM ${DB}.cc_user_minute FINAL
    WHERE minute >= lo AND minute < hi
    GROUP BY minute
  ),
  e AS (
    SELECT minute, users
    FROM ${DB}.expected_user_minutes
    WHERE fixture = '$1' AND platform = '*'
  )
SELECT if(a.minute = toDateTime(0), e.minute, a.minute) AS m,
       e.users AS want, a.users AS got
FROM a FULL OUTER JOIN e ON a.minute = e.minute
WHERE a.minute = toDateTime(0) OR e.minute = toDateTime(0) OR e.users != a.users
ORDER BY m
SQL
}

q_users_platform() {  # $1 = fixture
  cat <<SQL
WITH
  (SELECT t_from FROM ${DB}.fixture_span WHERE fixture = '$1') AS lo,
  (SELECT t_to   FROM ${DB}.fixture_span WHERE fixture = '$1') AS hi,
  a AS (
    SELECT minute, toString(platform) AS pf, uniqExactMerge(active_state) AS users
    FROM ${DB}.cc_user_minute FINAL
    WHERE minute >= lo AND minute < hi
    GROUP BY minute, platform
  ),
  e AS (
    SELECT minute, platform AS pf, users
    FROM ${DB}.expected_user_minutes
    WHERE fixture = '$1' AND platform != '*'
  )
SELECT if(a.minute = toDateTime(0), e.minute, a.minute) AS m,
       if(a.pf = '', e.pf, a.pf) AS pf, e.users AS want, a.users AS got
FROM a FULL OUTER JOIN e ON a.minute = e.minute AND a.pf = e.pf
WHERE a.minute = toDateTime(0) OR e.minute = toDateTime(0) OR e.users != a.users
ORDER BY m, pf
SQL
}

q_no_interval() {  # $1 = fixture
  cat <<SQL
SELECT n.video_session_id, n.interval_start
FROM ${DB}.expected_no_interval n
INNER JOIN (SELECT video_session_id, interval_start FROM ${DB}.session_intervals FINAL) a
  ON n.video_session_id = a.video_session_id AND n.interval_start = a.interval_start
WHERE startsWith(n.video_session_id, '$1_')
SQL
}

FAILED=0

check_fixture() {  # $1 = fixture. Prints "<fixture>  PASS|FAIL ..." and mismatch detail.
  local fx="$1" is_late has_pf has_users has_user_pf out fails=""
  is_late="$(ch "SELECT is_late FROM ${DB}.fixture_span WHERE fixture = '${fx}'")"
  has_pf="$(ch "SELECT count() FROM ${DB}.expected_minutes WHERE fixture = '${fx}' AND platform != '*'")"
  has_users="$(ch "SELECT count() FROM ${DB}.expected_user_minutes WHERE fixture = '${fx}' AND platform = '*'")"
  has_user_pf="$(ch "SELECT count() FROM ${DB}.expected_user_minutes WHERE fixture = '${fx}' AND platform != '*'")"

  out="$(ch "$(q_intervals "$fx")")"
  [ -n "$out" ] && { fails+=" intervals"; printf '    [intervals]\n%s\n' "$out" | sed 's/^/    /'; }

  out="$(ch "$(q_minutes_total "$fx" "${DB}.cc_minute_delta")")"
  [ -n "$out" ] && { fails+=" minutes"; printf '    [minutes]\n%s\n' "$out" | sed 's/^/    /'; }

  if [ "$has_pf" != "0" ]; then
    out="$(ch "$(q_minutes_platform "$fx" "${DB}.cc_minute_delta")")"
    [ -n "$out" ] && { fails+=" minutes-by-platform"; printf '    [minutes-by-platform]\n%s\n' "$out" | sed 's/^/    /'; }
  fi

  out="$(ch "$(q_no_interval "$fx")")"
  [ -n "$out" ] && { fails+=" vanished-interval-present"; printf '    [vanished-interval-present]\n%s\n' "$out" | sed 's/^/    /'; }

  if [ "$has_users" != "0" ]; then
    out="$(ch "$(q_users_total "$fx")")"
    [ -n "$out" ] && { fails+=" users"; printf '    [users]\n%s\n' "$out" | sed 's/^/    /'; }
  fi
  if [ "$has_user_pf" != "0" ]; then
    out="$(ch "$(q_users_platform "$fx")")"
    [ -n "$out" ] && { fails+=" users-by-platform"; printf '    [users-by-platform]\n%s\n' "$out" | sed 's/^/    /'; }
  fi

  # Late-data fixtures: the served answer must ALSO be right when reached via
  # old + (-old + new), not only via the fresh rebuild — including netting minutes
  # and dimension tuples that exist only on the old side.
  if [ "$is_late" = "1" ]; then
    out="$(ch "$(q_minutes_total "$fx" "$CORRECTED_SRC")")"
    [ -n "$out" ] && { fails+=" corrected-minutes"; printf '    [corrected-minutes]\n%s\n' "$out" | sed 's/^/    /'; }
    if [ "$has_pf" != "0" ]; then
      out="$(ch "$(q_minutes_platform "$fx" "$CORRECTED_SRC")")"
      [ -n "$out" ] && { fails+=" corrected-minutes-by-platform"; printf '    [corrected-minutes-by-platform]\n%s\n' "$out" | sed 's/^/    /'; }
    fi
  fi

  if [ -n "$fails" ]; then
    printf '%-6s FAIL —%s\n' "$fx" "$fails"
    FAILED=$((FAILED + 1))
    return 1
  fi
  printf '%-6s PASS\n' "$fx"
}

run_matrix() {
  local fx rc=0
  FAILED=0
  for fx in $(ch "SELECT fixture FROM ${DB}.fixture_span ORDER BY fixture"); do
    check_fixture "$fx" || rc=1
  done
  return $rc
}

# --------------------------------------------------------------------------- modes
main_run() {
  preflight
  setup_schema
  load_fixtures
  build_all
  echo "== edge matrix — $(ch "SELECT count() FROM ${DB}.fixture_span") fixtures =="
  local rc=0
  run_matrix || rc=1
  if [ $rc -ne 0 ]; then
    echo "== VERDICT: FAIL — ${FAILED} fixture(s) red =="
  else
    echo "== VERDICT: PASS — every fixture green =="
  fi
  return $rc
}

# Each sabotage: name | env overrides | fixture that MUST go red.
# Applied to the sed STREAM only; sql/*.sql on disk are never modified, so there is
# nothing to revert — the final clean run is the proof of restoration.
sabotage_run() {
  preflight
  setup_schema
  load_fixtures

  local spec name env fx rc=0
  local specs=(
    "resume-strict|SAB30=s/x -> x >= p, resumes/x -> x > p, resumes/g|O01"
    "no-tail-credit|SAB30=s/if(seg.2 = run_end, TAIL_S, 0)/0/|B01"
    "gap-inclusive|SAB30=s/> GAP_S/>= GAP_S/|B05"
    "pause-permissive|SAB30=s/1 AS UNCLOSED_PAUSE_TO_RUN_END/0 AS UNCLOSED_PAUSE_TO_RUN_END/|B02"
    "tie-break-second|SAB30=s/arrayDistinct(v_audio))\[1\]/arrayDistinct(v_audio))[2]/|D01"
    "no-minute-merge|SAB40=s/(length(acc.1) = 0) OR (x.1 > (acc.2 + 60))/(1 = 1)/|S08"
    "merge-off-by-one|SAB40=s/(x.1 > (acc.2 + 60))/(x.1 > acc.2)/|D02"
    "close-leaks-next-hour|SAB40=s/AND ((((intDiv(e, 60) \* 60)) + 60) < (h + 3600))//;s/AND (((intDiv(e, 60) \* 60) + 60) < (h + 3600))//|B06"
    "corr-drops-vanished|CORRMODE=drop-vanished|L02"
    "user-fold-by-session|SAB45=s/GROUP BY video_session_id, user_id/GROUP BY video_session_id/|U03"
  )

  echo "== sabotage — every mutation must turn its fixture red =="
  for spec in "${specs[@]}"; do
    name="${spec%%|*}"; env="${spec#*|}"; env="${env%%|*}"; fx="${spec##*|}"
    (
      export SAB30="" SAB40="" SAB45="" CORRMODE=full
      export "${env%%=*}"="${env#*=}"
      build_all
    )
    if check_fixture "$fx" >/dev/null 2>&1; then
      printf '%-22s NOT CAUGHT — %s stayed green. This fixture is decoration.\n' "$name" "$fx"
      rc=1
    else
      printf '%-22s caught by %s\n' "$name" "$fx"
    fi
  done

  # restore: clean rebuild, whole matrix must be green again
  SAB30="" SAB40="" SAB45="" CORRMODE=full build_all
  echo "== post-sabotage clean rebuild =="
  run_matrix || rc=1
  return $rc
}

case "${1:-run}" in
  run)      main_run ;;
  sabotage) sabotage_run ;;
  *) echo "usage: tools/edge-test.sh [run|sabotage]" >&2; exit 2 ;;
esac
