#!/usr/bin/env bash
# tools/build-generation.sh — build a NEW model generation, gate it, and commit
# it as one atomic pointer move (ADR 0034).
#
#   tools/build-generation.sh --database sonyliv_scratch
#   KILL_AFTER=stage tools/build-generation.sh --database sonyliv_scratch
#
# THE INCIDENT THIS EXISTS FOR. On 2026-08-02 a rebuild of the graded database
# died at stage 4/6 on a missing `cube_level` column, AFTER the delta insert.
# `set -e` aborted correctly and returned non-zero — and left `cc_minute_delta`
# holding 56,146 rows instead of 28,073, serving a peak of 5,834 against a true
# 2,917. The build's own reconcile, which catches doubling instantly, was never
# reached. An external audit found it hours later. The exit code was right; the
# database was wrong; nothing connected the two.
#
# THE STRUCTURAL ANSWER: a build never writes the tables anyone reads.
#
#   1  next        allocate generation G, record 'building'
#   2  build       full rebuild into a DISPOSABLE database <db>_bld_gG, using
#                  the current tools/build-model.sh — including all three of its
#                  reconcile gates
#   3  stage       copy the four tiers into <db>.gen_* tagged with G. Present on
#                  disk, INVISIBLE to every reader: the pointer still says G-1
#   4  verify      re-run the gates against generation G *as staged*, through
#                  the same pinned shape a reader uses. Catches a bad copy, a
#                  doubled insert, a tier that did not land
#   5  commit      ONE insert into model_generation. Every tier flips together
#   6  retire      DROP PARTITION for generations older than KEEP (default 2),
#                  and drop the build database
#
# Die anywhere in 1-4 and the serving surface is untouched: readers stay on the
# previous generation, whole and self-consistent. Die in 5 and either the row
# landed (committed) or it did not (still previous) — an insert of one row has
# no half.
#
# KILL_AFTER=<phase> aborts immediately after that phase, on purpose. It is how
# evidence/generation-pinning/40-killed-build.sh reproduces the real incident
# against this design. Phases: next | build | stage | verify.
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_DB="${CH_DATABASE-}"
ENV_DB_LOCAL="${CH_DATABASE_LOCAL-}"
[ -f .env ] && set -a && . ./.env && set +a
[ -n "$ENV_DB" ]       && export CH_DATABASE="$ENV_DB"
[ -n "$ENV_DB_LOCAL" ] && export CH_DATABASE_LOCAL="$ENV_DB_LOCAL"

TARGET="${TARGET:-local}"
DB=""
KEEP="${KEEP:-2}"
KILL_AFTER="${KILL_AFTER:-}"
# DOUBLE_DELTA=yes stages the delta tier TWICE — the exact corruption of the
# 2026-08-02 incident (56,146 rows = 2 x 28,073). Used by the evidence scripts
# to prove the verify gate catches it before the pointer moves.
DOUBLE_DELTA="${DOUBLE_DELTA:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --database)   DB="$2"; shift 2 ;;
    --database=*) DB="${1#--database=}"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$DB" ] || { echo "usage: tools/build-generation.sh --database NAME" >&2; exit 2; }

readonly GRADED_DB=sonyliv
if [ "$DB" = "$GRADED_DB" ] && [ "${REBUILD_GRADED:-}" != yes ]; then
  echo "tools/build-generation.sh: REFUSING to build into the graded database '$GRADED_DB' without REBUILD_GRADED=yes." >&2
  exit 1
fi

# CH_DATABASE names the GRADED database and is commonly exported in a shell that
# has sourced .env. On the local target it must not be visible at all: every
# tool here treats a CH_DATABASE that disagrees with --database as an operator
# mistake and dies, and none of them should be resolving 'sonyliv' anyway.
if [ "$TARGET" = cloud ]; then
  q()  { CH_DATABASE="$DB" tools/ch -c "$1"; }
  qb() { CH_DATABASE="$BUILD_DB" tools/ch -c "$1"; }
  apply() { TARGET=cloud CH_DATABASE="$1" tools/apply-sql.sh --database "$1" "${@:2}"; }
else
  q()  { env -u CH_DATABASE CH_DATABASE_LOCAL="$DB" tools/ch "$1"; }
  qb() { env -u CH_DATABASE CH_DATABASE_LOCAL="$BUILD_DB" tools/ch "$1"; }
  apply() { env -u CH_DATABASE TARGET=local CH_DATABASE_LOCAL="$1" tools/apply-sql.sh --database "$1" "${@:2}"; }
fi

scalar() { q "$1 FORMAT TSVRaw" | tr -d '[:space:]'; }

phase() {  # phase <name> — record progress, and honour KILL_AFTER
  echo "   [$1]"
  if [ "$KILL_AFTER" = "$1" ]; then
    echo "== KILL_AFTER=$1 — aborting deliberately, mid-build." >&2
    exit 137
  fi
}

# ── 1 · next ────────────────────────────────────────────────────────────────
ACTIVE="$(scalar "SELECT generation FROM v_active_generation")"
G="$(scalar "SELECT ifNull(max(generation), 0) + 1 FROM model_generation")"
BUILD_DB="${DB}_bld_g${G}"
echo "== generation $G  (active is currently ${ACTIVE:-0})  build db: $BUILD_DB"

q "INSERT INTO model_generation (generation, status, git_commit, notes) VALUES
   ($G, 'building', '$(git rev-parse --short HEAD 2>/dev/null || echo '?')',
    'build db $BUILD_DB')" >/dev/null
phase next

# ── 2 · build ───────────────────────────────────────────────────────────────
# This is the canonical tools/build-model.sh, pointed
# at a database nobody reads — which is the entire point: the existing build and
# all three of its gates keep working, they just cannot damage the serving layer
# any more.
echo "== 2/6  full rebuild into $BUILD_DB (current tools/build-model.sh)"
q "CREATE DATABASE IF NOT EXISTS $BUILD_DB" >/dev/null
apply "$BUILD_DB" sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql >/dev/null

# ev_raw for the build. A copy is honest but not free (see ADR 0034 "cost"): at
# 100x this is a full re-read of the raw tier per build. The production form
# points the derivation at `<serving>.ev_raw` directly — a cross-database read
# in ClickHouse costs nothing — which is a one-line change to sql/30 and is left
# out here so that build-model.sh stays byte-for-byte the script that runs today.
# Explicit physical columns make source-envelope additions such as ingested_at
# harmless. SELECT * made a new source-only column shift/fail the whole build.
EV_HAS_EXTRA="$(scalar "SELECT count() FROM system.columns
                         WHERE database = '$DB' AND table = 'ev_raw' AND name = 'extra'")"
EV_EXTRA_EXPR="CAST(map(), 'Map(String, String)')"
[ "$EV_HAS_EXTRA" = 1 ] && EV_EXTRA_EXPR=extra
qb "INSERT INTO ev_raw
      (content_id, video_session_id, user_id, event_type, event, event_timestamp,
       platform, app_version, country, audio_language, subtitle_language,
       player_version, session_start_epoch, extra)
    SELECT content_id, video_session_id, user_id, event_type, event, event_timestamp,
       platform, app_version, country, audio_language, subtitle_language,
       player_version, session_start_epoch, ${EV_EXTRA_EXPR}
    FROM ${DB}.ev_raw" >/dev/null
CONTENT_EXISTS="$(scalar "SELECT count() FROM system.tables
                           WHERE database = '$DB' AND name = 'content_dim'")"
if [ "$CONTENT_EXISTS" = 1 ]; then
  CONTENT_HAS_EXTRA="$(scalar "SELECT count() FROM system.columns
                               WHERE database = '$DB' AND table = 'content_dim' AND name = 'extra'")"
  CONTENT_EXTRA_EXPR="CAST(map(), 'Map(String, String)')"
  [ "$CONTENT_HAS_EXTRA" = 1 ] && CONTENT_EXTRA_EXPR=extra
  qb "INSERT INTO content_dim (content_id, title, video_type, category, extra)
      SELECT content_id, title, video_type, category, ${CONTENT_EXTRA_EXPR}
      FROM ${DB}.content_dim" >/dev/null
fi
echo "   ev_raw: $(qb "SELECT count() FROM ev_raw FORMAT TSVRaw" | tr -d '[:space:]') rows"

if [ "$TARGET" = cloud ]; then TARGET=cloud CH_DATABASE="$BUILD_DB" tools/build-model.sh
else                          env -u CH_DATABASE TARGET=local CH_DATABASE_LOCAL="$BUILD_DB" tools/build-model.sh; fi
phase build

# ── 3 · stage ───────────────────────────────────────────────────────────────
# Rows land in the serving database and are INVISIBLE, because the pointer still
# names G-1 and `generation` leads both the partition key and the sort key.
# Explicit lists make schema evolution fail loudly. A positional `SELECT $G, *`
# can silently shift values when a future physical column is inserted mid-table.
echo "== 3/6  stage generation $G into $DB (invisible: pointer still at ${ACTIVE:-0})"
q "INSERT INTO gen_session_intervals
     (generation, video_session_id, user_id, content_id, platform, country,
      app_version, audio_language, subtitle_language, player_version,
      extra_dimensions, interval_start, interval_end, is_open, build_version)
   SELECT $G, video_session_id, user_id, content_id, platform, country,
      app_version, audio_language, subtitle_language, player_version,
      extra_dimensions, interval_start, interval_end, is_open, build_version
   FROM ${BUILD_DB}.session_intervals" >/dev/null
q "INSERT INTO gen_cc_minute_delta
     (generation, minute, platform, country, content_id, subtitle_language,
      player_version, audio_language, app_version, delta, starts, ends)
   SELECT $G, minute, platform, country, content_id, subtitle_language,
      player_version, audio_language, app_version, delta, starts, ends
   FROM ${BUILD_DB}.cc_minute_delta" >/dev/null
if [ "$DOUBLE_DELTA" = yes ]; then
  echo "   !! DOUBLE_DELTA=yes — staging cc_minute_delta a SECOND time (the 2026-08-02 corruption)"
  q "INSERT INTO gen_cc_minute_delta
       (generation, minute, platform, country, content_id, subtitle_language,
        player_version, audio_language, app_version, delta, starts, ends)
     SELECT $G, minute, platform, country, content_id, subtitle_language,
        player_version, audio_language, app_version, delta, starts, ends
     FROM ${BUILD_DB}.cc_minute_delta" >/dev/null
fi
q "INSERT INTO gen_cc_hour_agg
     (generation, hour, platform, country, content_id, cube_level, peak,
      peak_minute, integral, computed_at)
   SELECT $G, hour, platform, country, content_id, cube_level, peak,
      peak_minute, integral, computed_at
   FROM ${BUILD_DB}.cc_hour_agg" >/dev/null
q "INSERT INTO gen_cc_user_minute
     (generation, minute, platform, country, content_id, active_state, computed_at)
   SELECT $G, minute, platform, country, content_id, active_state, computed_at
   FROM ${BUILD_DB}.cc_user_minute" >/dev/null
echo "   staged: $(scalar "SELECT concat(toString((SELECT count() FROM gen_session_intervals WHERE generation=$G)), ' intervals, ', toString((SELECT count() FROM gen_cc_minute_delta WHERE generation=$G)), ' deltas, ', toString((SELECT count() FROM gen_cc_hour_agg WHERE generation=$G)), ' hours, ', toString((SELECT count() FROM gen_cc_user_minute WHERE generation=$G)), ' user buckets')")"
phase stage

# ── 4 · verify ──────────────────────────────────────────────────────────────
# The gates again, but against the STAGED generation, in the serving database,
# through the same shape a reader sees. build-model.sh's gates ran in the build
# database; these catch everything that can go wrong AFTER them — a copy that
# ran twice, a tier whose insert was skipped, a partition that did not land.
#
# This is the check that the real incident never reached. Here it cannot be
# skipped, because reaching the commit is the only way to be served.
echo "== 4/6  verify generation $G as staged"
GATE=""
gate() {  # gate <label> <sql returning PASS.../FAIL...>
  local out; out="$(q "$2 FORMAT TSVRaw")"
  printf '   %-22s %s\n' "$1" "$out"
  GATE="${GATE}${1}: ${out}"$'\n'
  case "$out" in *FAIL*) GATE_FAILED=1 ;; esac
}
GATE_FAILED=0

# 4a — every tier landed, and landed ONCE. Row counts must equal the build db's
# exactly. A doubled additive tier is +100% here and cannot get past it.
gate "row counts" "
SELECT if(bad = 0, concat('PASS  ', toString(tot), ' rows across 4 tiers'),
                   concat('FAIL  ', toString(bad), ' of 4 tiers differ from ${BUILD_DB}'))
FROM (
  SELECT
    (SELECT count() FROM gen_session_intervals WHERE generation=$G) != (SELECT count() FROM ${BUILD_DB}.session_intervals)
  + ((SELECT count() FROM gen_cc_minute_delta  WHERE generation=$G) != (SELECT count() FROM ${BUILD_DB}.cc_minute_delta))
  + ((SELECT count() FROM gen_cc_hour_agg      WHERE generation=$G) != (SELECT count() FROM ${BUILD_DB}.cc_hour_agg))
  + ((SELECT count() FROM gen_cc_user_minute   WHERE generation=$G) != (SELECT count() FROM ${BUILD_DB}.cc_user_minute)) AS bad,
    (SELECT count() FROM gen_session_intervals WHERE generation=$G)
  + (SELECT count() FROM gen_cc_minute_delta   WHERE generation=$G)
  + (SELECT count() FROM gen_cc_hour_agg       WHERE generation=$G)
  + (SELECT count() FROM gen_cc_user_minute    WHERE generation=$G) AS tot
)"

# 4b — the delta serving layer vs interval expansion, every minute, computed
# entirely inside generation $G. This is build-model.sh's headline reconcile,
# re-expressed against the staged generation. A doubled delta tier doubles the
# running sum, so this fails loudly even if 4a were somehow satisfied.
gate "delta vs intervals" "
WITH
  bounds AS (SELECT min(minute) AS lo, max(minute) AS hi FROM gen_cc_minute_delta WHERE generation = $G),
  spine AS (
    SELECT toDateTime(arrayJoin(range(
             toUInt32((SELECT lo FROM bounds)),
             toUInt32((SELECT hi FROM bounds)) + 60, 60))) AS minute
  ),
  d AS (SELECT minute, sum(delta) AS dd FROM gen_cc_minute_delta WHERE generation = $G GROUP BY minute),
  dense AS (
    SELECT s.minute AS minute,
           toInt64(sum(coalesce(d.dd, 0)) OVER (
             PARTITION BY toStartOfHour(s.minute) ORDER BY s.minute
             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent
    FROM spine AS s LEFT JOIN d USING (minute)
  ),
  -- uniqExact(video_session_id), NOT count(): a session whose intervals touch
  -- the same minute twice is ONE viewer. count() reads 3,073 at the peak where
  -- the truth is 2,917 — it is the 44%-of-sessions double count that
  -- sql/40_deltas.sql merges away, and it is why v_concurrency_minute_intervals
  -- is written this way. Reproducing that view's expression exactly is the whole
  -- point of this gate.
  truth AS (
    SELECT toDateTime(m) AS minute, uniqExact(video_session_id) AS concurrent
    FROM (
      SELECT video_session_id,
             arrayJoin(range(toUInt32(toStartOfMinute(interval_start)),
                             toUInt32(toStartOfMinute(interval_end)) + 1, 60)) AS m
      FROM gen_session_intervals FINAL WHERE generation = $G
    ) GROUP BY minute
  )
SELECT if(countIf(dense.concurrent != truth.concurrent) = 0,
          concat('PASS  ', toString(count()), ' minutes, peak ', toString(max(truth.concurrent))),
          concat('FAIL  ', toString(countIf(dense.concurrent != truth.concurrent)), ' of ',
                 toString(count()), ' minutes disagree, served peak ',
                 toString(max(dense.concurrent)), ' vs true ', toString(max(truth.concurrent))))
FROM dense FULL OUTER JOIN truth USING (minute)"

# 4c — hour tier agrees with the minute tier it is derived from, inside $G.
gate "hour vs minute peak" "
SELECT if(h = m, concat('PASS  hour peak ', toString(h), ' = minute peak'),
                 concat('FAIL  hour peak ', toString(h), ' != minute peak ', toString(m)))
FROM (
  SELECT (SELECT max(peak) FROM gen_cc_hour_agg FINAL
           WHERE generation = $G AND platform='*' AND country='*' AND content_id=-1 AND cube_level=0) AS h,
         (SELECT max(c) FROM (
            SELECT toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS c
            FROM gen_cc_minute_delta WHERE generation = $G GROUP BY minute)) AS m
)"

if [ "$GATE_FAILED" != 0 ]; then
  q "INSERT INTO model_generation (generation, status, gate_verdict, notes) VALUES
     ($G, 'abandoned', '$(printf '%s' "$GATE" | tr "'" ' ' | tr '\n' '|')', 'verify gate failed')" >/dev/null
  cat >&2 <<EOF

== GENERATION $G FAILED ITS GATES — NOT COMMITTED.
   The serving layer is untouched: readers stay on generation ${ACTIVE:-0}.
   Staged rows are still on disk for inspection:
     SELECT * FROM ${DB}.gen_cc_minute_delta WHERE generation = $G
   Drop them with:
     ALTER TABLE ${DB}.gen_cc_minute_delta DROP PARTITION ...   (see ADR 0034)
EOF
  exit 1
fi
phase verify

# ── 5 · commit ──────────────────────────────────────────────────────────────
# One row. Four tiers flip together, because all four pinned views read the same
# pointer. This is the whole reason the pointer is a control table and not four
# RENAMEs: `EXCHANGE TABLES` is atomic per table, so four of them is four commit
# points and a reader can land between two of them.
echo "== 5/6  commit generation $G"
q "INSERT INTO model_generation (generation, status, git_commit, gate_verdict, notes) VALUES
   ($G, 'committed', '$(git rev-parse --short HEAD 2>/dev/null || echo '?')',
    '$(printf '%s' "$GATE" | tr "'" ' ' | tr '\n' '|')', 'promoted by tools/build-generation.sh')" >/dev/null
echo "   active generation is now $(scalar "SELECT generation FROM v_active_generation")"

# ── 6 · retire ──────────────────────────────────────────────────────────────
# Metadata only. KEEP=2 leaves exactly one generation to roll back to; the
# rollback itself is `INSERT INTO model_generation VALUES (G, 'abandoned', ...)`,
# after which v_active_generation names G-1 again and every tier follows.
echo "== 6/6  retire generations older than $((G - KEEP + 1))  (KEEP=$KEEP)"
for t in gen_session_intervals gen_cc_minute_delta gen_cc_hour_agg gen_cc_user_minute; do
  parts="$(scalar "SELECT arrayStringConcat(groupUniqArray(partition), ' ') FROM system.parts
             WHERE database = '$DB' AND table = '$t' AND active
               AND toUInt32(splitByChar(',', trim(BOTH '()' FROM partition))[1]) <= $((G - KEEP))")"
  for p in $parts; do q "ALTER TABLE $t DROP PARTITION $p" >/dev/null || true; done
done
q "DROP DATABASE IF EXISTS $BUILD_DB" >/dev/null
echo "== done. $(scalar "SELECT concat('serving generation ', toString(generation)) FROM v_active_generation")"
