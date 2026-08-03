#!/usr/bin/env bash
# tools/build-model.sh — rebuild the whole model from ev_raw, in order.
#
#   ev_raw -> session_intervals (30_build_intervals.sql)
#          -> cc_user_minute    (45_user_concurrency.sql backfill — ADR 0016)
#          -> cc_minute_delta   (40_deltas.sql)
#          -> cc_hour_agg       (50_hour_agg.sql)
#
# Order matters and the steps are NOT individually idempotent in the same way:
#   session_intervals is a ReplacingMergeTree keyed (video_session_id,
#     interval_start), so a re-insert replaces.
#   cc_minute_delta is an AggregatingMergeTree of SUMS. A second insert without
#     a TRUNCATE silently DOUBLES every number. There is no dedup to save you,
#     and the result looks plausible — so this script truncates first, always.
#   cc_user_minute is, since ADR 0016, a ReplacingMergeTree(computed_at) of
#     uniqExact states, populated by the canonical backfill INSERT inside
#     sql/45_user_concurrency.sql — the MV that used to fire during the
#     intervals insert is retired, because a per-block MV writes PARTIAL states
#     and under replace semantics the newest write wins, so a partial state
#     would erase a complete bucket. Re-applying 45 replaces every bucket it
#     recomputes AND writes retraction tombstones for buckets that vanished, so
#     the truncate here is storage hygiene (drop tombstone keys), not the
#     correctness mechanism it used to be when the tier was a set union that
#     could only ever grow (measured then: served 2,953 vs true 2,844,
#     ADR 0012).
#   cc_hour_agg is a ReplacingMergeTree keyed (dims, hour). A re-run REPLACES a
#     matching key, so it cannot double — but it was not rebuilt here at all,
#     so `make model` left the hour/day views serving a pre-fix number while
#     the minute views served the new one (measured: 2,887 vs 2,917). It is
#     truncated rather than replaced-in-place, because replacement cannot
#     retract a (dims, hour) key the new derivation no longer produces.
#     (The incremental publisher handles that same case without a truncate by
#     writing all-zero rows that the views filter — ADR 0016.)
#
#   tools/build-model.sh              # local
#   TARGET=cloud tools/build-model.sh # the graded service
set -euo pipefail
cd "$(dirname "$0")/.."
# Bug 11 (queue Q33): `set -a && . ./.env` OVERWRITES variables already exported
# by the caller. Two agents hit this within an hour on 2026-08-02 — one could not
# build a scratch model at all, the other asked for a scratch database and had
# this script TRUNCATE `default.session_intervals` before dying on a schema
# mismatch. `CH_DATABASE=scratch TARGET=cloud tools/build-model.sh` resolved to
# `sonyliv`, and only the REBUILD_GRADED guard below stood between that and the
# graded database. The guard was never meant to be the only line of defence.
# Capture the caller's view FIRST, then let it win — same pattern as tools/ch,
# tools/load.sh and tools/apply-sql.sh.
ENV_DB="${CH_DATABASE-}"
ENV_DB_LOCAL="${CH_DATABASE_LOCAL-}"
[ -f .env ] && set -a && . ./.env && set +a
[ -n "$ENV_DB" ]       && export CH_DATABASE="$ENV_DB"
[ -n "$ENV_DB_LOCAL" ] && export CH_DATABASE_LOCAL="$ENV_DB_LOCAL"
TARGET="${TARGET:-local}"

q() {  # q <sql>
  if [ "$TARGET" = cloud ]; then tools/ch -c "$1"; else tools/ch "$1"; fi
}

# gate <sql> — run a check that prints its own PASS/FAIL line, and REMEMBER a
# failure so the script exits non-zero at the end. These used to print FAIL and
# exit 0, which meant `make model && <anything>` ran the <anything> on a broken
# model. All three tier checks below are gates; the run continues past a failure
# so you see every tier's verdict in one go, not just the first that broke.
GATE_FAILED=0
gate() {
  local out
  out="$(q "$1")"
  printf '%s\n' "$out"
  case "$out" in *FAIL*) GATE_FAILED=1 ;; esac
}

# ── The guard that was missing on 2026-08-01 ────────────────────────────────
# This script TRUNCATEs four tables and rebuilds them. Run against the GRADED
# database it destroys and recreates the answers we are scored on, and there is
# no undo. That is not hypothetical: a worktree on a stale base ran exactly this
# against `sonyliv`, with pre-ADR-0009 SQL, and left the service serving two
# different model generations — minute peak 2,887 with 1,949.331 hours, hour
# peak 2,917 — for about two hours until an external audit noticed. Nothing in
# this script objected, because until now nothing in it asked.
#
# So: rebuilding the graded database is allowed, but it must be DELIBERATE.
# Set REBUILD_GRADED=yes for that one invocation. Every other target — local,
# any scratch database — is unaffected and needs no ceremony.
# NOT overridable. Cross-model validation (Codex, 2026-08-02) found that
# `GRADED_DB="${GRADED_DB:-sonyliv}"` let any caller disable this guard with
# GRADED_DB=anything — verified by the orchestrator, which reached stage 2/6 of a
# graded rebuild without either authorisation flag. A guard whose subject is
# caller-controlled is not a guard. `readonly` makes a later assignment fail
# loudly instead of silently widening the hole.
readonly GRADED_DB=sonyliv
if [ "$TARGET" = cloud ]; then
  TARGET_DB="${CH_DATABASE:-}"
  if [ "$TARGET_DB" = "$GRADED_DB" ] && [ "${REBUILD_GRADED:-}" != yes ]; then
    cat >&2 <<EOF
tools/build-model.sh: REFUSING to rebuild the graded database '$GRADED_DB'.

  This truncates session_intervals, cc_user_minute, cc_minute_delta and
  cc_hour_agg on the service we are scored on, then rebuilds them from ev_raw.
  If your working tree is on a stale base, the rebuild writes STALE SQL over
  correct answers and the result looks plausible. That has happened once.

  Before you override, confirm all three:
    1. git log --oneline -1        is a commit you meant to build from
    2. git status --porcelain      is clean
    3. you actually intend to replace the graded answers

  Then:  REBUILD_GRADED=yes TARGET=cloud tools/build-model.sh

  For any other purpose use a scratch database — sql/70_truncation_test.sql
  shows the pattern — or run without TARGET=cloud for local.
EOF
    exit 1
  fi
  if [ "$TARGET_DB" = "$GRADED_DB" ]; then
    echo "== ⚠ REBUILDING THE GRADED DATABASE '$GRADED_DB' (REBUILD_GRADED=yes)"
    echo "==   commit $(git rev-parse --short HEAD 2>/dev/null || echo '?')  tree $( [ -z "$(git status --porcelain 2>/dev/null)" ] && echo clean || echo DIRTY )"
  fi
fi

# A BUILD THAT DIES MID-WAY LEAVES A SILENTLY-WRONG MODEL. Say so, loudly.
#
# On 2026-08-02 a build died at stage 4/6 on a missing cube_level column, AFTER
# the delta insert. `set -e` aborted immediately and correctly returned non-zero
# — but the database was left with a doubled cc_minute_delta (56,146 rows, peak
# 5,834 against a true 2,917) and NOTHING said the model was half-built. The
# script's own end-of-run reconcile, which would have caught it instantly, was
# never reached. An external audit found it hours later.
#
# The exit code is not enough: nobody reads it when the failure text scrolls past.
# This trap makes the consequence impossible to miss and names the fix.
BUILD_COMPLETE=0
on_exit() {
  local rc=$?
  if [ "$rc" -ne 0 ] && [ "$BUILD_COMPLETE" -eq 0 ]; then
    cat >&2 <<EOF

##########################################################################
# BUILD FAILED PART-WAY — THE MODEL IN '${TARGET_DB:-$TARGET}' IS NOW HALF-BUILT
#
#   Some tiers were rebuilt and some were not. cc_minute_delta is an
#   AggregatingMergeTree of SUMS: if its insert ran, a re-run without the
#   truncate DOUBLES every number and the result looks entirely plausible.
#
#   DO NOT SERVE FROM IT and do not assume a re-run is safe on its own.
#   Re-run this script to completion, then confirm:
#
#     tools/reconcile.sh    (TARGET=$TARGET)   must report 0 mismatched
#
#   This exact failure produced a doubled graded tier on 2026-08-02.
##########################################################################
EOF
  fi
  exit $rc
}
trap on_exit EXIT

echo "== target: $TARGET"

# ── 0. THE POLICY (ADR 0032) ────────────────────────────────────────────────
# sql/30 and sql/90 read GAP_S / TAIL_S / UNCLOSED_PAUSE_TO_RUN_END /
# POINT_ACTIVITY_COUNTS from `v_model_policy`, which this file creates. Apply it
# FIRST and unconditionally, so a build can never run against a policy view left
# behind by an older tree — the build stamps its own policy rather than
# inheriting whatever the database happened to hold.
#
# `check` runs before the apply because a stale sql/01_policy.sql (edited
# policy/model.policy, forgot `tools/policy.sh gen`) would otherwise be written
# into the database and every tier below would be built under the OLD values
# while the declaration claimed the new ones.
echo "== 0/6  policy ($(tools/policy.sh stamp))"
tools/policy.sh check >/dev/null || { tools/policy.sh check; echo "== BUILD REFUSED — the policy declaration and sql/01_policy.sql disagree." >&2; exit 1; }
TARGET="$TARGET" APPLY_GRADED_DESTRUCTIVE="${REBUILD_GRADED:-}" tools/apply-sql.sh sql/01_policy.sql >/dev/null
q "SELECT concat('   policy v', policy_version, ' (', policy_hash, ') applied') FROM v_model_policy FORMAT TSVRaw"

# Establish the semantic input boundary before any derived table reads the
# events. ev_raw remains lossless; q_reason only removes rows whose session or
# timestamp cannot be used by the model, and ev_quarantine retains them with a
# reason and source identity. Applying the file again at stage 6 refreshes the
# read-side normalisation views after the serving tables have been rebuilt.
echo "== 0b/6  accepted-row boundary (ADR 0025)"
TARGET="$TARGET" APPLY_GRADED_DESTRUCTIVE="${REBUILD_GRADED:-}" tools/apply-sql.sh sql/15_normalise.sql >/dev/null
q "SELECT concat('   model input ', toString(model_input_rows), ' / raw ', toString(raw_rows),
                 ' · quarantined ', toString(quarantined_rows))
   FROM v_preprocess_summary FORMAT TSVRaw"

echo "== 1/6  session_intervals (gap + pause, ADR 0001/0007)"
q "TRUNCATE TABLE session_intervals" >/dev/null
TARGET="$TARGET" APPLY_GRADED_DESTRUCTIVE="${REBUILD_GRADED:-}" tools/apply-sql.sh sql/30_build_intervals.sql >/dev/null
q "SELECT concat('   intervals: ', toString(count()), ' over ', toString(uniqExact(video_session_id)), ' sessions') FROM session_intervals FINAL FORMAT TSVRaw"

echo "== 2/6  cc_user_minute (uniqExact per bucket, replaced not unioned — ADR 0016)"
# A pre-ADR-0016 database carries the AggregatingMergeTree shape, whose set
# union cannot retract a user. The engine cannot be ALTERed; the table is pure
# derived state, so the migration IS the rebuild: drop and let 45 recreate.
USER_ENGINE="$(q "SELECT engine FROM system.tables WHERE database = currentDatabase() AND name = 'cc_user_minute' FORMAT TSVRaw" | tr -d '[:space:]')"
case "$USER_ENGINE" in
  *ReplacingMergeTree* | "") : ;;   # current shape, or fresh — 45 creates it
  *)
    echo "   cc_user_minute is ${USER_ENGINE} (pre-ADR-0016) — dropping and recreating."
    echo "   Derived state only; sql/45_user_concurrency.sql rebuilds it below."
    q "DROP VIEW IF EXISTS mv_user_minute" >/dev/null
    q "DROP TABLE cc_user_minute" >/dev/null
    ;;
esac
# Truncate is storage hygiene here (drops retraction tombstones); the backfill
# inside 45 replaces every bucket regardless. See the header.
q "TRUNCATE TABLE IF EXISTS cc_user_minute" >/dev/null
TARGET="$TARGET" APPLY_GRADED_DESTRUCTIVE="${REBUILD_GRADED:-}" tools/chunked-backfill.sh users
q "SELECT concat('   user-minute buckets: ', toString(count())) FROM cc_user_minute FINAL FORMAT TSVRaw"

echo "== 3/6  cc_minute_delta (hour-clipped, ADR 0003)"
q "TRUNCATE TABLE cc_minute_delta" >/dev/null
TARGET="$TARGET" APPLY_GRADED_DESTRUCTIVE="${REBUILD_GRADED:-}" tools/chunked-backfill.sh deltas
q "SELECT concat('   delta rows: ', toString(count()), '  opens ', toString(sum(starts)), '  closes ', toString(sum(ends))) FROM cc_minute_delta FORMAT TSVRaw"
# WHY NO EXTRA ASSERTION HERE, and why the doubling of 2026-08-02 was missed.
#
# The graded cc_minute_delta reached 56,146 rows — exactly 2x — and served a
# peak of 5,834 against a true 2,917. The TRUNCATE above was present and ran;
# two full inserts landed anyway.
#
# This script ALREADY has the check that catches it: the reconcile step below
# compares the delta serving layer against interval expansion, every minute.
# Doubled deltas double the running sum, so that comparison fails loudly.
#
# It did not fire because the run that caused the doubling DIED AT STAGE 4/6 on
# a missing cube_level column, before reaching it. A half-finished build left a
# doubled table and said nothing, and an external audit found it hours later.
#
# So the defect is not a missing assertion — it is that a FAILED build leaves a
# silently-wrong model behind. An opens-vs-intervals check was tried here and is
# WRONG: hour-clipping means the two legitimately differ (20,002 vs 30,323 on
# the delivered file). The real fix belongs at the top: refuse to leave a
# partially-built graded model, or re-run the reconcile even on failure.
# Recorded rather than papered over.

echo "== 4/6  cc_hour_agg (the hour tier, ADR 0003)"
# A pre-ADR-0022 database has no `cube_level` column, and 50_hour_agg.sql's
# CREATE is `IF NOT EXISTS` — so a truncate leaves the OLD shape in place and the
# INSERT dies with "No such column cube_level". Same situation as cc_user_minute
# above and the same answer: the cube is pure derived state rebuilt from
# cc_minute_delta, so the migration IS the rebuild. ADR 0022 added the column and
# did not add this step; found when the first authorised rebuild after it failed
# at stage 4/6.
HOUR_HAS_CUBE_LEVEL="$(q "SELECT count() FROM system.columns WHERE database = currentDatabase() AND table = 'cc_hour_agg' AND name = 'cube_level' FORMAT TSVRaw" | tr -d '[:space:]')"
HOUR_EXISTS="$(q "SELECT count() FROM system.tables WHERE database = currentDatabase() AND name = 'cc_hour_agg' FORMAT TSVRaw" | tr -d '[:space:]')"
if [ "$HOUR_EXISTS" = "1" ] && [ "$HOUR_HAS_CUBE_LEVEL" = "0" ]; then
  echo "   cc_hour_agg has no cube_level (pre-ADR-0022) — dropping and recreating."
  echo "   Derived state only; sql/50_hour_agg.sql rebuilds it from cc_minute_delta below."
  q "DROP TABLE cc_hour_agg" >/dev/null
fi
q "TRUNCATE TABLE IF EXISTS cc_hour_agg" >/dev/null   # IF EXISTS: 50_hour_agg.sql creates it just below
TARGET="$TARGET" APPLY_GRADED_DESTRUCTIVE="${REBUILD_GRADED:-}" tools/apply-sql.sh sql/50_hour_agg.sql >/dev/null
q "SELECT concat('   hour rows: ', toString(count()), '  peak ', toString(max(peak))) FROM cc_hour_agg FINAL WHERE platform='*' AND country='*' AND content_id=-1 FORMAT TSVRaw"

echo "== 5/6  views"
TARGET="$TARGET" APPLY_GRADED_DESTRUCTIVE="${REBUILD_GRADED:-}" tools/apply-sql.sh sql/20_views.sql >/dev/null
echo "   ok"

# Re-apply the same file to refresh its read-side normalisation views over the
# newly rebuilt delta tier. The quarantine sweep is idempotent.
echo "== 6/6  normalisation UDFs + views (ADR 0011)"
TARGET="$TARGET" APPLY_GRADED_DESTRUCTIVE="${REBUILD_GRADED:-}" tools/apply-sql.sh sql/15_normalise.sql >/dev/null
echo "   ok"

# This gate was BLIND to the defect it exists to catch (ADR 0031, U3-F1). It
# densified the LEVEL with `WITH FILL … INTERPOLATE`, which carries a level
# across an hour boundary even though deltas are hour-clipped (ADR 0003) — 10
# phantom viewer-minutes on the delivered file. It then INNER JOINed to the
# interval expansion, and a phantom minute has NO interval row, so the join
# dropped exactly the rows that were wrong: measured on local scratch, the old
# form reported `PASS 3732 minutes` while its dense side was wrong at 10.
#
# Two changes, both load-bearing, both measured on y2_pac0:
#   * densify the DELTA on an explicit spine, then take the hour-partitioned
#     running sum — the only correct recipe (docs/CONVENTIONS.md). A `range()`
#     spine rather than WITH FILL, because `FILL FROM` rejects a scalar subquery
#     and the bounds here are derived, not literal.
#   * FULL OUTER, not INNER, for the same reason the user-tier gate below is
#     already FULL OUTER: a minute present on only one side is precisely the
#     failure, and an inner join hides it.
# After: `PASS 17030 minutes, peak 2917` — and swapping only the dense side back
# to the naive recipe makes it `FAIL 10 of 17030`, so it now sees U3-F1.
echo "== reconcile: delta serving layer vs interval expansion, every minute"
gate "
WITH
  bounds AS (SELECT min(minute) AS lo, max(minute) AS hi FROM cc_minute_delta),
  spine AS (
    SELECT toDateTime(arrayJoin(range(
             toUInt32((SELECT lo FROM bounds)),
             toUInt32((SELECT hi FROM bounds)) + 60, 60))) AS minute
  ),
  d AS (SELECT minute, sum(delta) AS dd FROM cc_minute_delta GROUP BY minute),
  dense AS (
    SELECT s.minute AS minute,
           toInt64(sum(coalesce(d.dd, 0)) OVER (
             PARTITION BY toStartOfHour(s.minute) ORDER BY s.minute
             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS concurrent
    FROM spine AS s LEFT JOIN d USING (minute)
  )
SELECT if(countIf(dense.concurrent != i.concurrent) = 0,
          concat('   PASS  ', toString(count()), ' minutes, peak ', toString(max(i.concurrent))),
          concat('   FAIL  ', toString(countIf(dense.concurrent != i.concurrent)), ' of ',
                 toString(count()), ' minutes disagree'))
FROM dense FULL OUTER JOIN v_concurrency_minute_intervals i USING (minute) FORMAT TSVRaw"

# ---------------------------------------------------------------------------
# USER TIER GATE. The check that would have caught ADR 0012's defect the day it
# appeared. cc_user_minute is a set union, so a contaminated table stays
# PLAUSIBLE — it drifts upward and never down. Comparing the served number to
# session_intervals expanded directly is the only thing that sees it.
#
# FULL OUTER JOIN, not INNER: contamination also leaves behind whole MINUTES
# that the current derivation no longer produces (measured: 3,743 served vs
# 3,732 real), and an inner join would quietly skip exactly those.
# ---------------------------------------------------------------------------
echo "== reconcile: user tier vs interval expansion, every minute"
gate "
WITH truth AS (
  SELECT toDateTime(m) AS minute, uniqExact(user_id) AS u
  FROM (
    SELECT user_id, arrayJoin(range(toUInt32(toStartOfMinute(interval_start)),
                                    toUInt32(toStartOfMinute(interval_end)) + 1, 60)) AS m
    FROM session_intervals FINAL
  ) GROUP BY minute
),
served AS (SELECT minute, concurrent_users AS u FROM v_user_concurrency_minute_total)
SELECT if(countIf(served.u != truth.u) = 0,
          concat('   PASS  ', toString(count()), ' minutes, user peak ', toString(max(truth.u))),
          concat('   FAIL  ', toString(countIf(served.u != truth.u)), ' of ', toString(count()),
                 ' minutes disagree, served peak ', toString(max(served.u)),
                 ' vs true ', toString(max(truth.u))))
FROM served FULL OUTER JOIN truth USING (minute) FORMAT TSVRaw"

# ---------------------------------------------------------------------------
# HOUR TIER GATE. cc_hour_agg cannot double (ReplacingMergeTree), but it CAN go
# stale — it was not rebuilt by this script at all until ADR 0012, so the hour
# and day views served 2,887 while the minute views served 2,917. A tier that
# disagrees with the tier it is derived from is the whole failure mode.
# ---------------------------------------------------------------------------
echo "== reconcile: hour tier peak vs minute tier peak"
gate "
SELECT if(h = m, concat('   PASS  hour tier peak ', toString(h), ' = minute tier peak'),
                 concat('   FAIL  hour tier peak ', toString(h), ' != minute tier peak ', toString(m)))
FROM (
  SELECT (SELECT max(peak) FROM v_concurrency_hour_total)              AS h,
         (SELECT max(concurrent) FROM v_concurrency_minute_delta_total) AS m
) FORMAT TSVRaw"

BUILD_COMPLETE=1
if [ "$GATE_FAILED" != 0 ]; then
  echo "== BUILD FAILED — a tier disagrees with session_intervals. Do NOT benchmark this build." >&2
  exit 1
fi
