#!/usr/bin/env bash
# Load a large CSV into ClickHouse Cloud over HTTP, in resumable chunks.
#
#   scripts/load_large_csv.sh <table> <file.csv> [rows-per-chunk]
#
# WHY NOT JUST `curl --data-binary @file`
# ClickHouse itself has no INSERT size limit -- the HTTP interface streams the
# body, so 1.8 GB is not the problem people expect. The problems are the ones
# around it:
#
#   * ONE REQUEST, ALL OR NOTHING. A dropped connection 1.6 GB in leaves a
#     partially-inserted table and no way to resume. On hotel/venue wifi on
#     submission day that is the likely outcome, not the unlucky one.
#   * NO PROGRESS. A single curl gives no idea whether it is 10% or 90% done,
#     so you cannot tell a slow upload from a hung one.
#   * TIMEOUTS. Cloud closes idle connections; a slow uplink can trip that.
#
# So: split into chunks, send each with retries, and record which chunks landed
# so a re-run skips them. Each chunk is one INSERT, and ClickHouse INSERTs are
# atomic per block -- a failed chunk leaves nothing behind to clean up.
#
# COLUMNS ARE MATCHED BY NAME, NOT POSITION.
# The unseen file lists its columns in a different order from the one we already
# have (`video_session_id,user_id,content_id,...` against
# `content_id,video_session_id,user_id,...`). Plain CSV is positional, so that
# load would put session ids into content_id and succeed -- wrong data, no
# error, discovered only if someone happens to look. So every chunk carries the
# header and goes in as CSVWithNames, which maps by name. It also means a new
# column in the file is handled rather than fatal.
#
# GZIP IS THE OTHER HALF. Event CSV is extremely repetitive (session ids,
# platform names, versions), so it compresses ~8-10x. Sending it compressed
# turns a 1.8 GB upload into ~200 MB on the wire; ClickHouse decompresses
# server-side. This is usually the difference between minutes and an hour.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.local ]] || { echo "missing .env.local" >&2; exit 1; }
set -a; . ./.env.local; set +a

TABLE="${1:?usage: load_large_csv.sh <table> <file.csv> [rows-per-chunk]}"
FILE="${2:?usage: load_large_csv.sh <table> <file.csv> [rows-per-chunk]}"
CHUNK_ROWS="${3:-500000}"
[[ -f "$FILE" ]] || { echo "no such file: $FILE" >&2; exit 1; }

WORK=".run/load-$(basename "$TABLE")"
DONE="$WORK/done"
mkdir -p "$WORK/chunks"; touch "$DONE"

TOTAL_ROWS=$(( $(wc -l < "$FILE") - 1 ))   # minus the header
echo "file      : $FILE ($(du -h "$FILE" | cut -f1), ${TOTAL_ROWS} data rows)"
echo "table     : $TABLE"
echo "chunk size: ${CHUNK_ROWS} rows"

# Split once; a re-run reuses the chunks rather than re-splitting 1.8 GB.
if [[ -z "$(ls -A "$WORK/chunks" 2>/dev/null)" ]]; then
  echo "splitting (one-time) ..."
  # Keep the header out of the split: every chunk is sent as CSV without names,
  # so the column ORDER of the file must match the table. That is checked below.
  tail -n +2 "$FILE" | split -l "$CHUNK_ROWS" - "$WORK/chunks/part-"
  # Every chunk needs the header, because each is an independent CSVWithNames
  # request. Without it, chunk 2 onward would treat a data row as the header.
  head -1 "$FILE" > "$WORK/header.csv"
fi
CHUNKS=$(ls "$WORK/chunks" | wc -l | tr -d ' ')

# Report the column diff before uploading a gigabyte. Matching is by name, so a
# different ORDER is fine; what matters is whether any column is missing from
# the table (it would be dropped) or missing from the file (it gets a default).
HEADER=$(head -1 "$FILE" | tr -d '\r"' )
COLS=$(curl -sS --user "$CH_USER:$CH_PASS" --data-binary \
  "SELECT arrayStringConcat(groupArray(name), ',') FROM system.columns
   WHERE database='default' AND table='${TABLE}'
     AND default_kind IN ('', 'DEFAULT')" "$CH_HOST" | tr -d '\n')
python3 - "$HEADER" "$COLS" <<'PYEOF'
import sys
f = set(x.strip() for x in sys.argv[1].split(',') if x.strip())
t = set(x.strip() for x in sys.argv[2].split(',') if x.strip())
if f - t:
    print(f"  WARNING  in file but not in table (will be DROPPED): {sorted(f - t)}")
    print("           add the column to the table first if you want to keep it")
if t - f:
    print(f"  WARNING  in table but not in file (will get DEFAULTS): {sorted(t - f)}")
if f == t:
    print("columns   : file and table match (order does not matter, mapped by name)")
PYEOF
echo

BEFORE=$(curl -sS --user "$CH_USER:$CH_PASS" --data-binary "SELECT count() FROM ${TABLE}" "$CH_HOST" | tr -d '\n')
echo "rows already in ${TABLE}: ${BEFORE}"
echo

i=0
for part in "$WORK/chunks"/part-*; do
  i=$((i+1))
  name=$(basename "$part")
  grep -qx "$name" "$DONE" && { printf "  [%3d/%3d] %s  already loaded\n" "$i" "$CHUNKS" "$name"; continue; }

  ok=0
  for attempt in 1 2 3; do
    # gzip the body and let ClickHouse decompress: ~8-10x less on the wire.
    # skip_unknown_fields: a column the file has and the table does not is
    # dropped rather than fatal -- the unseen file may carry more than we model.
    QUERY="INSERT%20INTO%20${TABLE}%20FORMAT%20CSVWithNames"
    OPTS="input_format_skip_unknown_fields=1&input_format_with_names_use_header=1"
    if cat "$WORK/header.csv" "$part" | gzip -c | curl -sS --fail-with-body \
         --user "$CH_USER:$CH_PASS" \
         -H "Content-Encoding: gzip" \
         --max-time 900 \
         --data-binary @- \
         "$CH_HOST/?query=${QUERY}&${OPTS}" >/dev/null; then
      ok=1; break
    fi
    echo "      attempt $attempt failed, retrying ..." >&2
    sleep $((attempt * 5))
  done

  [[ $ok -eq 1 ]] || { echo "  chunk $name FAILED after 3 attempts — re-run to resume" >&2; exit 1; }
  echo "$name" >> "$DONE"
  printf "  [%3d/%3d] %s  ok\n" "$i" "$CHUNKS" "$name"
done

echo
AFTER=$(curl -sS --user "$CH_USER:$CH_PASS" --data-binary "SELECT count() FROM ${TABLE}" "$CH_HOST" | tr -d '\n')
GAINED=$(( AFTER - BEFORE ))
# The table may already hold an earlier day, so the total is not the file's row
# count -- what must match is how many rows this load ADDED.
echo "rows in ${TABLE}: ${BEFORE} -> ${AFTER}  (added ${GAINED}, file had ${TOTAL_ROWS})"
if [[ "$GAINED" == "$TOTAL_ROWS" ]]; then echo "MATCH — every row landed"
else echo "MISMATCH — re-run to fill the gap before building silver"; exit 1; fi
