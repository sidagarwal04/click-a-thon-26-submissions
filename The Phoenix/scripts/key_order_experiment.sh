#!/usr/bin/env bash
# Measure candidate ORDER BY keys for concurrency_deltas against every filter shape.
#
#   ./scripts/key_order_experiment.sh
#
# schema-pk-cardinality-order says order sort-key columns low-to-high cardinality, and the
# shipped key does not: country (1 distinct value) sits second where it can never prune, and
# content_id (3,357, the highest) sits fourth, ahead of app_version (65). That is a real
# deviation from the rule, so the question is whether it costs anything MEASURABLE.
#
# This builds each candidate in a scratch database, loads identical data, and reports granules
# read per filter shape. Nothing is applied to phoenix: reordering a sort key is a modelling
# decision for the team, and TASK.md says not to.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${1:-phoenix_scratch_keyorder}"
case "$DB" in phoenix|phoenix_live|phoenix_unseen) echo "refusing to run into $DB" >&2; exit 1;; esac
ch() { CH_DATABASE="$DB" ./scripts/ch.sh "$@" 2>/dev/null; }

echo "== building candidates in $DB" >&2
./scripts/ch.sh --query "DROP DATABASE IF EXISTS $DB" >/dev/null 2>&1
./scripts/ch.sh --query "CREATE DATABASE $DB" >/dev/null 2>&1
ch --queries-file sql/experiments/key_order_candidates.sql

for t in deltas_a_shipped deltas_b_cardinality deltas_c_no_dead_column; do
  ch --query "INSERT INTO $t SELECT platform, country, video_type, content_id, app_version, minute, delta
              FROM phoenix.concurrency_deltas WHERE minute < {frozen_before:String}"
done

# Identical filter shapes to scripts/bench.sh, so the two tables of numbers are comparable.
SHAPES=(
  "unfiltered|||||0"
  "platform|ANDROID_PHONE||||0"
  "country||india|||0"
  "content|||||2078157818"
  "video_type|||vod||0"
  "app_version||||6.34.8|0"
  "platform+country|ANDROID_PHONE|india|||0"
  "content+platform|ANDROID_PHONE||||2078157818"
)

granules() {  # table plat ctry vtype appv cid
  ch --format TSVRaw --query "
    EXPLAIN indexes = 1
    SELECT minute, sum(delta) FROM $1
    WHERE ('$2' = '' OR platform = '$2') AND ('$3' = '' OR country = '$3')
      AND ('$4' = '' OR video_type = '$4') AND ('$5' = '' OR app_version = '$5')
      AND ($6 = 0 OR content_id = $6)
    GROUP BY minute" </dev/null \
  | tr -d '\r' | awk '/Granules:/ { sub(/^ *Granules: */, ""); g = $0 } END { print (g == "" ? "?" : g) }'
}

{
  printf 'shape\tA_shipped\tB_cardinality_order\tC_no_dead_column\n'
  for spec in "${SHAPES[@]}"; do
    IFS='|' read -r name plat ctry vtype appv cid <<< "$spec"
    echo "  $name" >&2
    printf '%s\t%s\t%s\t%s\n' "$name" \
      "$(granules deltas_a_shipped        "$plat" "$ctry" "$vtype" "$appv" "$cid")" \
      "$(granules deltas_b_cardinality    "$plat" "$ctry" "$vtype" "$appv" "$cid")" \
      "$(granules deltas_c_no_dead_column "$plat" "$ctry" "$vtype" "$appv" "$cid")"
  done
  printf '#\n# granules read / granules total. Lower is better; equal totals mean identical data.\n'
  printf '# A = shipped: platform, country, video_type, content_id, app_version, minute\n'
  printf '# B = strict low-to-high cardinality: country, video_type, platform, app_version, minute, content_id\n'
  printf '# C = dead single-valued column dropped: video_type, platform, app_version, content_id, minute\n'
  printf '# cardinalities: country 1, video_type 3, platform 10, app_version 65, minute 1532, content_id 3357\n'
  for t in deltas_a_shipped deltas_b_cardinality deltas_c_no_dead_column; do
    printf '# size.%s\t%s\n' "$t" "$(ch --format TSVRaw --query "SELECT formatReadableSize(sum(bytes_on_disk)) FROM system.parts WHERE active AND database = currentDatabase() AND table = '$t'" </dev/null)"
  done
} | evidence key_order_candidates "granules read per filter shape for three candidate ORDER BY keys, measured on identical data" \
  | xargs cat
