#!/usr/bin/env bash
# Run a validation query against a local CSV, with no ClickHouse service needed.
# Defines the `events_src` view the queries expect, then runs the query file.
#
#   ./scripts/oracle.sh data/ch-hackathon-raw-data.csv sql/queries/validation/oracle_concurrency.sql
#   TOLERANCE_S=60 PAUSE_INACTIVE=0 ./scripts/oracle.sh <csv> <sql>
set -euo pipefail
cd "$(dirname "$0")/.."

FILE="${1:?usage: ./scripts/oracle.sh <file.csv> <query.sql>}"
SQL="${2:?usage: ./scripts/oracle.sh <file.csv> <query.sql>}"

VIEW="CREATE VIEW events_src AS SELECT
  video_session_id, user_id, content_id, event_type, event,
  fromUnixTimestamp64Milli(event_timestamp) AS event_timestamp,
  platform, app_version, country, audio_language, subtitle_language, player_version,
  fromUnixTimestamp64Milli(session_start_epoch) AS session_start_epoch
FROM file('$FILE', CSVWithNames);"

# content_src, defined only when a content CSV is present, so queries that do not need it are
# unaffected and queries that do get title and category from the same source of truth the
# service was loaded from rather than from the service itself. Validating a denormalised title
# against the table it was denormalised from would prove only that the copy copied.
CONTENT="${CONTENT_CSV:-data/ch-hackathon-content-data.csv}"
CVIEW=""
[ -f "$CONTENT" ] && CVIEW="CREATE VIEW content_src AS SELECT
  content_id, title, video_type, category
FROM file('$CONTENT', CSVWithNames);"

{ echo "$VIEW"; [ -n "$CVIEW" ] && echo "$CVIEW"; cat "$SQL"; } | clickhouse local \
  --param_tolerance_s="${TOLERANCE_S:-90}" \
  --param_pause_inactive="${PAUSE_INACTIVE:-1}" \
  --format "${FORMAT:-PrettyCompact}" \
  --session_timezone UTC \
  --schema_inference_make_columns_nullable=0   # CSV inference makes everything Nullable, which
                                               # blocks arrayJoin(timeSlots(...)) and hides nulls
