#!/bin/bash
# Demo fault injection. One function per beat, called by name.
set -euo pipefail
CH() { docker exec -i ch clickhouse-client -q "$1" < /dev/null; }

# SYSTEM STOP VIEW is a REFRESHABLE-MV command: on an incremental MV it is accepted
# with no error and does NOTHING. DETACH is the mechanism that actually stalls it.
stall_mv()   { CH "DETACH TABLE mv_stateless"; echo "mv stalled - the curve will now go stale"; }
resume_mv()  { CH "ATTACH TABLE mv_stateless"; echo "mv resumed - NOTE: rows missed while detached are NOT backfilled"; }
backfill()   { CH "INSERT INTO cc_minute_stateless SELECT toStartOfMinute(event_timestamp), platform, country, content_id, uniqState(video_session_id) FROM ev_raw WHERE event_type IN ('VideoHeartbeat','VideoPlay') GROUP BY 1,2,3,4"; echo "backfilled"; }

# Prove the freshness panel is load-bearing: stop ingestion and watch ClickStack show the lag.
stall_ingest() { docker pause ch >/dev/null; echo "ingestion paused"; }
resume_ingest(){ docker unpause ch >/dev/null; echo "ingestion resumed"; }

"${1:?usage: demo/chaos.sh <stall_mv|resume_mv|backfill|stall_ingest|resume_ingest>}"
