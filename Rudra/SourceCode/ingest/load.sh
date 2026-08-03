#!/usr/bin/env bash
# Load the SonyLIV dataset into ClickHouse and build the concurrency model.
#   1) create schema (sql/01_tables.sql)   2) load content   3) load raw (7M) with
#   transform + resolution normalization   4) backfill hist (sql/02_backfill_hist.sql)
#
# Config: copy ingest/.env.example -> ingest/.env and fill in. Usage: bash ingest/load.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a
: "${CH_URL:?set CH_URL in ingest/.env}"; : "${CH_USER:?}"; : "${CH_PASSWORD:?}"
: "${RAW_CSV:?path to ch-hackathon-raw-data*.csv}"; : "${CONTENT_CSV:?path to content csv}"
AUTH="$CH_USER:$CH_PASSWORD"
q(){ curl -s --user "$AUTH" --data-binary "$1" "$CH_URL"; }
runfile(){ python3 - "$1" <<'PY'
import sys,urllib.request,base64,os
url=os.environ['CH_URL']; user,pw=os.environ['CH_USER'],os.environ['CH_PASSWORD']
sql="\n".join(l for l in open(sys.argv[1]) if not l.strip().startswith('--'))
for s in (x.strip() for x in sql.split(';') if x.strip()):
    req=urllib.request.Request(url+'?allow_experimental_refreshable_materialized_view=1',data=s.encode())
    req.add_header('Authorization','Basic '+base64.b64encode(f"{user}:{pw}".encode()).decode())
    try: urllib.request.urlopen(req,timeout=300); print("  ok:",s.splitlines()[0][:60])
    except urllib.error.HTTPError as e: print("  ERR:",e.read().decode()[:200]); raise
PY
}

echo "== 1) schema =="; CH_URL="$CH_URL" CH_USER="$CH_USER" CH_PASSWORD="$CH_PASSWORD" runfile "$ROOT/sql/01_tables.sql"

echo "== 2) content =="
q "TRUNCATE TABLE sonyliv.content_raw" >/dev/null
{ echo "INSERT INTO sonyliv.content_raw (content_id,title,video_type,category,show_name) FORMAT CSV"; cat "$CONTENT_CSV"; } \
  | curl -s --user "$AUTH" --data-binary @- "$CH_URL?input_format_csv_skip_first_lines=1&format_csv_allow_single_quotes=0"
q "SYSTEM RELOAD DICTIONARY sonyliv.content_dict" >/dev/null
echo "   content_raw rows: $(q 'SELECT count() FROM sonyliv.content_raw')"

echo "== 3) raw events (gzip-stream + transform; normalize resolution) =="
q "TRUNCATE TABLE sonyliv.raw_events" >/dev/null
STMT="INSERT INTO sonyliv.raw_events (content_id, video_session_id, user_id, event_type, event, event_timestamp, platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch, video_resolution) SELECT content_id, video_session_id, user_id, event_type, event, fromUnixTimestamp64Milli(toInt64(event_timestamp)), platform, app_version, lowerUTF8(country), lowerUTF8(audio_language), upperUTF8(subtitle_language), player_version, fromUnixTimestamp64Milli(toInt64(session_start_epoch)), multiIf(video_resolution='' OR video_resolution='NA' OR video_resolution='Auto-Auto' OR video_resolution='Auto','unknown', replaceRegexpOne(replaceRegexpAll(video_resolution,' ',''),'^(Auto-|NA-|0-)','')) FROM input('content_id String, video_session_id String, user_id String, event_type String, event String, event_timestamp String, platform String, app_version String, country String, audio_language String, subtitle_language String, player_version String, session_start_epoch String, video_resolution String') FORMAT CSV"
URL=$(python3 -c "import urllib.parse,os,sys; print(os.environ['CH_URL']+'?'+urllib.parse.urlencode({'query':sys.stdin.read(),'input_format_csv_skip_first_lines':'1','format_csv_allow_single_quotes':'0','input_format_null_as_default':'0'}))" <<<"$STMT")
gzip -c "$RAW_CSV" | curl -s --max-time 1200 --user "$AUTH" --data-binary @- -H 'Content-Encoding: gzip' "$URL"
echo "   raw_events rows: $(q 'SELECT count() FROM sonyliv.raw_events')  sessions: $(q 'SELECT uniqExact(video_session_id) FROM sonyliv.raw_events')"

echo "== 4) backfill hist =="
q "TRUNCATE TABLE sonyliv.hist_minute_full" >/dev/null
q "$(sed '/^--/d' "$ROOT/sql/02_backfill_hist.sql")"
echo "   hist rows: $(q 'SELECT count() FROM sonyliv.hist_minute_full')"
echo "   PEAK concurrency: $(q 'SELECT max(c) FROM (SELECT minute,sum(cnt) c FROM sonyliv.hist_minute_full GROUP BY minute)')"
echo "done."
