#!/usr/bin/env bash
# Facts about a raw event CSV, before any modelling. Runs entirely locally.
#
#   ./scripts/profile.sh data/ch-hackathon-raw-data.csv
set -euo pipefail
FILE="${1:?usage: ./scripts/profile.sh <file.csv>}"
Q() { clickhouse local --query "$1" --format PrettyCompact; }
SRC="file('$FILE', CSVWithNames)"

echo "== columns";      Q "DESCRIBE $SRC"
echo "== volume";       Q "SELECT count() rows, uniqExact(video_session_id) sessions, uniqExact(user_id) users, uniqExact(content_id) contents FROM $SRC"
echo "== event types";  Q "SELECT event_type, count() FROM $SRC GROUP BY 1 ORDER BY 2 DESC"
# event_timestamp is epoch MILLIseconds, not seconds. See docs/assumptions.md.
echo "== time span";    Q "SELECT fromUnixTimestamp64Milli(min(event_timestamp)) first, fromUnixTimestamp64Milli(max(event_timestamp)) last FROM $SRC"
echo "== dimensions";   Q "SELECT platform, country, count() FROM $SRC GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20"
echo "== open sessions (start seen, no VideoSessionEnd)"
Q "SELECT countIf(ends = 0) open, countIf(ends > 0) closed FROM (SELECT video_session_id, countIf(event_type = 'VideoSessionEnd') ends FROM $SRC GROUP BY 1)"
echo "== heartbeat gap distribution (seconds between consecutive events in a session)"
Q "SELECT quantiles(0.5, 0.9, 0.99, 0.999)(gap) q, max(gap) max_gap FROM (
     SELECT (event_timestamp - lagInFrame(event_timestamp) OVER (PARTITION BY video_session_id ORDER BY event_timestamp)) / 1000 AS gap
     FROM $SRC) WHERE gap > 0"
