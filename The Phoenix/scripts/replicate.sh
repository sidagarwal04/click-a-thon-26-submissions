#!/usr/bin/env bash
# Replicate phoenix into the generation-2 database by copying raw events and RE-DERIVING.
#
#   ./scripts/replicate.sh                        # phoenix -> phoenix_next
#   SRC_DB=phoenix DST_DB=phoenix_next ./scripts/replicate.sh
#   REBUILD=1 ./scripts/replicate.sh              # drop and rebuild an existing destination
#
# WHY COPY-AND-REDERIVE RATHER THAN COPY THE DERIVED TABLES. Copying foreground_intervals and
# the runs and the deltas would produce a destination that is byte-identical and proves
# nothing: a copy is a copy. Copying only raw_events and running the unmodified pipeline means
# the destination's serving layer is an INDEPENDENT derivation, and the fact that it reproduces
# phoenix's frozen-slice peak and average is the evidence that the replica can be trusted.
# scripts/replica_parity.sh is where that comparison happens; this script only builds.
#
# WHY NOT A VIEW ONTO phoenix.raw_events, which is what rebuild_swap.sh does. That is right for
# a shadow that lives for ninety seconds and is thrown away. This destination is durable, gains
# an insight layer, and eventually gains its own ingest, so it needs its own rows. It also has
# to be PINNED: a teammate ingests into phoenix continuously, and a destination reading a view
# would drift under every query.
#
# WHY THE FROZEN SLICE IS THE THING TO COMPARE, and not the whole table. phoenix's derived
# tables lag its raw_events by however long it has been since the last batch derive, measured
# at 47 minutes when this was written. Comparing at the live watermark pits a fresh derivation
# against a stale one and fails for a reason that has nothing to do with the replica.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

SRC="${SRC_DB:-phoenix}"
DST="${DST_DB:-phoenix_next}"
export EVIDENCE_STAMP_DB="$DST"

ch() { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { ch --format TSVRaw --query "$1" | head -1; }

[ "$SRC" = "$DST" ] && { echo "SRC and DST are both $SRC" >&2; exit 1; }

# The thirteen columns every generation of raw_events shares. Named rather than SELECT *
# because generation 2 adds arrival_timestamp and phoenix does not have it, and because
# SELECT * would carry ingested_at, whose value on phoenix's pre-ALTER parts is the wall clock
# of whichever query reads it. Copying that would turn a read-time artifact into a stored
# number that looks authoritative. arrival_timestamp is left at its not-observed sentinel:
# these rows did not arrive, they were copied, and no lateness may be inferred from them.
RAW_COLS='video_session_id, user_id, content_id, event_type, event, event_timestamp,
          platform, app_version, country, audio_language, subtitle_language, player_version,
          session_start_epoch'

existing="$(CH_DATABASE=$DST val "SELECT count() FROM raw_events" 2>/dev/null || echo 0)"
if [ "${existing:-0}" != "0" ]; then
  [ "${REBUILD:-0}" = "1" ] || {
    echo "REFUSING: $DST already holds $existing raw events." >&2
    echo "  Copying again would APPEND, and raw_events is a plain MergeTree that will not" >&2
    echo "  deduplicate them. Re-run with REBUILD=1 to drop and rebuild $DST." >&2
    exit 1
  }
  echo "== REBUILD=1: dropping $DST ($existing raw events present)" >&2
  ch --query "DROP DATABASE IF EXISTS $DST"
fi

echo "== 1. create $DST from sql/schema/" >&2
./scripts/init_db.sh "$DST" >/dev/null

# Captured ONCE, before either copy, and every later comparison is bounded by it. Without this
# the destination's contents depend on how long the two INSERTs took.
#
# CUT_BEFORE pins the cut instead of taking the source's live watermark, which is what you want
# when the destination should be the VALIDATED CORPUS and nothing else. Copying at the live
# watermark drags the source's live slice along: phoenix_next carried 1,298,060 such rows when
# the since-dropped phoenix_insights was built from it. Every comparison below derives from $CUT, so bounding it
# keeps s_raw/d_raw and s_frz/d_frz self-consistent and the PASS still means something.
#
# NOTE the boundary is INCLUSIVE (<=) while the frozen predicate is strict (<), so passing a
# date here admits a row landing exactly at midnight. The count assertion downstream is what
# catches that, and it is why the runbook checks for exactly 905558 rather than "about right".
CUT="${CUT_BEFORE:-$(CH_DATABASE=$SRC val "SELECT toString(max(event_timestamp)) FROM raw_events")}"
echo "== 2. cut at $CUT" >&2

echo "== 3. copy content" >&2
CH_DATABASE="$DST" ch --query "INSERT INTO content SELECT * FROM ${SRC}.content"
CONTENT_AT="$(date -u +'%Y-%m-%d %H:%M:%S')"

echo "== 4. copy raw_events at or before the cut" >&2
# Into raw_events, never raw_events_landing: the landing table's MV converts epoch millis, and
# these rows have already been through it once.
CH_DATABASE="$DST" ch --query \
  "INSERT INTO raw_events ($RAW_COLS) SELECT $RAW_COLS FROM ${SRC}.raw_events WHERE event_timestamp <= '$CUT'"

echo "== 5. derive, unmodified pipeline, with its own post-conditions" >&2
./scripts/derive.sh "$DST" >&2

s_raw="$(CH_DATABASE=$SRC val "SELECT count() FROM raw_events WHERE event_timestamp <= '$CUT'")"
d_raw="$(CH_DATABASE=$DST val "SELECT count() FROM raw_events")"
# THE CORPUS BOUNDARY IS PINNED HERE, and is deliberately NOT the {frozen_before} parameter.
# ch.sh defaults FROZEN_BEFORE to 2100-01-01 so the consoles can SEE the live slice, which is
# right for reading a live curve and poison for this assertion: at 2100-01-01 "frozen slice"
# means "every row in the table", so a live source is compared against a pinned destination and
# can never match. Observed as a spurious FAIL reporting 3,804,245 against 905,558 while every
# assertion that mattered had passed. The graded corpus boundary is a fixed date, not a knob.
CORPUS_BEFORE="${CORPUS_BEFORE:-2026-08-01}"
s_frz="$(CH_DATABASE=$SRC val "SELECT count() FROM raw_events WHERE event_timestamp < '$CORPUS_BEFORE'")"
d_frz="$(CH_DATABASE=$DST val "SELECT count() FROM raw_events WHERE event_timestamp < '$CORPUS_BEFORE'")"
s_con="$(CH_DATABASE=$SRC val "SELECT count() FROM content")"
d_con="$(CH_DATABASE=$DST val "SELECT count() FROM content")"
d_arr="$(CH_DATABASE=$DST val "SELECT countIf(arrival_timestamp > toDateTime64(0, 3)) FROM raw_events")"

verdict=PASS
[ "$s_raw" = "$d_raw" ] || verdict=FAIL
[ "$s_frz" = "$d_frz" ] || verdict=FAIL
[ "$s_con" = "$d_con" ] || verdict=FAIL
# Every copied row must carry the not-observed sentinel. A non-zero count here means something
# wrote a manufactured arrival time, which is the one thing that would poison the lateness work.
[ "${d_arr:-1}" = "0" ]  || verdict=FAIL

{
  printf 'metric\tvalue\n'
  printf 'source_database\t%s\n'      "$SRC"
  printf 'destination_database\t%s\n' "$DST"
  printf 'cut_event_timestamp\t%s\t(source rows at or before this were copied)\n' "$CUT"
  printf 'content_copied_at_utc\t%s\t(content has no event time to bound, so it is read at its own instant; 33k rows of slowly-changing dimensions)\n' "$CONTENT_AT"
  printf 'source.raw_events_at_cut\t%s\n'  "$s_raw"
  printf 'dest.raw_events\t%s\t(required equal to source at cut)\n' "$d_raw"
  printf 'source.frozen_slice\t%s\n'       "$s_frz"
  printf 'dest.frozen_slice\t%s\t(required equal, this is the graded corpus)\n' "$d_frz"
  printf 'source.content\t%s\n'            "$s_con"
  printf 'dest.content\t%s\t(required equal)\n' "$d_con"
  printf 'dest.rows_with_observed_arrival\t%s\t(required 0, copied rows did not arrive)\n' "$d_arr"
  printf 'verdict\t%s\n' "$verdict"
} | evidence "replicate_${SRC}_to_${DST}" "copy raw events at a pinned cut and re-derive through the unmodified pipeline" \
  | xargs cat

[ "$verdict" = PASS ] || { echo "REPLICATION CHECKS FAILED" >&2; exit 1; }
echo "REPLICATED $SRC -> $DST at cut $CUT" >&2
