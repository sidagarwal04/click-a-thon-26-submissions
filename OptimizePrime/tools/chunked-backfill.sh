#!/usr/bin/env bash
# tools/chunked-backfill.sh — Cloud-legal date chunks for day-partitioned tiers.
#
# One INSERT touching more than 100 partitions is rejected by ClickHouse Cloud,
# and max_partitions_per_insert_block is read-only there. Full rebuilds therefore
# run the canonical SQL40/SQL45 INSERTs over sets of at most 64 ACTUAL output
# dates. Dates come from session_intervals, the accepted-row-derived boundary;
# sparse histories do not execute empty calendar chunks.
#
#   tools/chunked-backfill.sh users
#   tools/chunked-backfill.sh deltas
set -euo pipefail
cd "$(dirname "$0")/.."

usage() {
  sed -n '2,12p' "$0" >&2
  exit 2
}
die() { printf '\nchunked-backfill.sh FAILED: %s\n' "$*" >&2; exit 1; }

case "${1:-}" in
  users|deltas) TIER="$1" ;;
  *) usage ;;
esac
[ "$#" -eq 1 ] || usage

TARGET="${TARGET:-local}"
CHUNK_SIZE="${MODEL_DATE_CHUNK_SIZE:-64}"
case "$CHUNK_SIZE" in
  ''|*[!0-9]*) die "MODEL_DATE_CHUNK_SIZE must be an integer from 1 to 64 (got '$CHUNK_SIZE')." ;;
esac
[ "$CHUNK_SIZE" -ge 1 ] && [ "$CHUNK_SIZE" -le 64 ] || \
  die "MODEL_DATE_CHUNK_SIZE must be from 1 to 64 (got '$CHUNK_SIZE')."

q() {
  if [ "$TARGET" = cloud ]; then tools/ch -c "$1"; else tools/ch "$1"; fi
}
apply_file() {
  TARGET="$TARGET" tools/apply-sql.sh "$1" >/dev/null
}

TMP_ROOT="${TMPDIR:-/tmp}"
TMP_DIR="$(mktemp -d "${TMP_ROOT%/}/sonyliv-chunked-backfill.XXXXXX")"
cleanup() {
  [ -n "${TMP_DIR:-}" ] || return 0
  [ -d "$TMP_DIR" ] && [ ! -L "$TMP_DIR" ] || return 0
  case "${TMP_DIR##*/}" in sonyliv-chunked-backfill.*) rm -r -- "$TMP_DIR" ;; esac
}
trap cleanup EXIT

if [ "$TIER" = users ]; then
  # SQL45 contains DDL, one canonical INSERT (between the publisher markers),
  # and serving views. Apply the two schema/view fragments once and only the
  # INSERT once per date chunk. The same marker is consumed by publish.sh.
  awk '/PUBLISH_EXTRACT_BEGIN:user/{exit} {print}' sql/45_user_concurrency.sql \
    > "$TMP_DIR/users-pre.sql"
  sed -n '/PUBLISH_EXTRACT_BEGIN:user/,/PUBLISH_EXTRACT_END:user/p' \
    sql/45_user_concurrency.sql > "$TMP_DIR/template.sql"
  awk 'seen {print} /PUBLISH_EXTRACT_END:user/ {seen=1}' \
    sql/45_user_concurrency.sql > "$TMP_DIR/users-post.sql"
  grep -q '^INSERT INTO cc_user_minute' "$TMP_DIR/template.sql" || \
    die "could not extract the canonical user INSERT from sql/45_user_concurrency.sql."
  apply_file "$TMP_DIR/users-pre.sql"
else
  cp sql/40_deltas.sql "$TMP_DIR/template.sql"
fi

ANCHOR='WHERE 1 /* backfill: output dates */'
[ "$(grep -Fxc "$ANCHOR" "$TMP_DIR/template.sql")" = 1 ] || \
  die "expected exactly one output-date anchor in the canonical $TIER INSERT."

# Enumerate days touched by accepted intervals, not min..max calendar days and
# not ev_raw. Expanding by DAY is bounded by interval duration; the model's gap
# split keeps ordinary intervals short, while a legitimately multi-day interval
# contributes each day because SQL40 re-opens it at every hour and SQL45 expands
# its active minutes.
DATES="$(q "
SELECT toString(output_date)
FROM
(
    SELECT DISTINCT toDate(day_epoch) AS output_date
    FROM session_intervals FINAL
    ARRAY JOIN range(
        toUInt32(toStartOfDay(interval_start)),
        toUInt32(toStartOfDay(interval_end)) + 86400,
        86400
    ) AS day_epoch
)
ORDER BY output_date
FORMAT TSVRaw")"

TOTAL_DATES=0
CHUNKS=0
IN_LIST=""
IN_COUNT=0

run_chunk() {
  local predicate
  [ "$IN_COUNT" -gt 0 ] || return 0
  predicate="WHERE toDate(minute) IN (${IN_LIST}) /* backfill: output dates */"
  awk -v anchor="$ANCHOR" -v predicate="$predicate" \
    '{ print ($0 == anchor ? predicate : $0) }' \
    "$TMP_DIR/template.sql" > "$TMP_DIR/chunk.sql"
  grep -Fqx "$predicate" "$TMP_DIR/chunk.sql" || \
    die "date predicate was not injected into the canonical $TIER INSERT."
  CHUNKS=$((CHUNKS + 1))
  printf '   %s chunk %d: %d output date(s)\n' "$TIER" "$CHUNKS" "$IN_COUNT"
  apply_file "$TMP_DIR/chunk.sql"
  IN_LIST=""
  IN_COUNT=0
}

while IFS= read -r output_date; do
  [ -n "$output_date" ] || continue
  printf '%s\n' "$output_date" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || \
    die "server returned an unsafe output date: '$output_date'."
  if [ -n "$IN_LIST" ]; then IN_LIST="${IN_LIST}, "; fi
  IN_LIST="${IN_LIST}toDate('${output_date}')"
  IN_COUNT=$((IN_COUNT + 1))
  TOTAL_DATES=$((TOTAL_DATES + 1))
  if [ "$IN_COUNT" -eq "$CHUNK_SIZE" ]; then run_chunk; fi
done <<EOF
$DATES
EOF
run_chunk

if [ "$TIER" = users ]; then
  apply_file "$TMP_DIR/users-post.sql"
fi

printf '   %s backfill complete: %d actual output date(s), %d insert chunk(s), max %d dates/insert\n' \
  "$TIER" "$TOTAL_DATES" "$CHUNKS" "$CHUNK_SIZE"
