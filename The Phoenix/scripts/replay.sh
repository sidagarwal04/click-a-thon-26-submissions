#!/usr/bin/env bash
# Replay a day of the event stream into ClickHouse at accelerated wall-clock, one simulated
# minute per tick, deriving incrementally after each tick so the served curve grows the way
# it would in production.
#
#   ./scripts/replay.sh                        # 2026-07-26, 1 sim-minute per second
#   ./scripts/replay.sh --day 2026-07-26 --tick 0.5 --from 09:00 --to 12:00
#
# Runs against the phoenix_demo database, never the validated one, so a demo cannot
# disturb benchmark results. Chunk files are cached: the second run starts instantly.
set -euo pipefail
cd "$(dirname "$0")/.."

DAY=2026-07-26; TICK=1; FROM=00:00; TO=23:59; CSV=data/ch-hackathon-raw-data.csv
while [ $# -gt 0 ]; do
  case "$1" in
    --day) DAY="$2"; shift 2;;
    --tick) TICK="$2"; shift 2;;
    --from) FROM="$2"; shift 2;;
    --to) TO="$2"; shift 2;;
    --csv) CSV="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done

CHUNKS="/tmp/phoenix-replay/$DAY"
export CH_DATABASE=phoenix_demo

if [ ! -d "$CHUNKS" ]; then
  echo "== slicing $DAY into per-minute chunks (one pass over the CSV, cached afterwards)"
  mkdir -p "$CHUNKS"
  # ponytail: one partitioned write instead of 1,440 filtered passes over a 232 MB file
  clickhouse local --session_timezone UTC --schema_inference_make_columns_nullable=0 --query "
    INSERT INTO FUNCTION file('$CHUNKS/{_partition_id}.csv', CSVWithNames)
    PARTITION BY formatDateTime(toStartOfMinute(fromUnixTimestamp64Milli(event_timestamp)), '%H%M')
    SELECT * FROM file('$CSV', CSVWithNames)
    WHERE toDate(fromUnixTimestamp64Milli(event_timestamp)) = toDate('$DAY')
    ORDER BY event_timestamp"
fi

echo "== preparing $CH_DATABASE"
./scripts/init_db.sh >/dev/null
for t in raw_events session_minute_runs concurrency_deltas foreground_intervals; do
  ./scripts/ch.sh --query "TRUNCATE TABLE IF EXISTS $t" 2>/dev/null || true
done

echo "== replaying $DAY $FROM-$TO at one simulated minute every ${TICK}s"
START=$(date +%s)
for f in $(ls "$CHUNKS" | sort); do
  hhmm="${f%.csv}"
  clock="${hhmm:0:2}:${hhmm:2:2}"
  [[ "$clock" < "$FROM" ]] && continue
  [[ "$clock" > "$TO" ]] && break

  ./scripts/ch.sh --query "INSERT INTO raw_events_landing FORMAT CSVWithNames" < "$CHUNKS/$f"
  # derive only what this minute touched. Sessions still open keep being re-derived every
  # tick: their old runs are retracted and re-asserted, which is the update path itself.
  ./scripts/ch.sh --param_tolerance_s="${TOLERANCE_S:-90}" --param_pause_inactive="${PAUSE_INACTIVE:-1}" \
    --param_from_ts="$DAY $clock:00" --param_to_ts="$DAY $clock:59" \
    --queries-file sql/pipeline/03_derive_incremental.sql
  printf "\r  %s  (%ds elapsed)" "$clock" "$(( $(date +%s) - START ))"
  sleep "$TICK"
done
echo; echo "== replay complete"
