#!/usr/bin/env bash
# ClickStack (HyperDX all-in-one) — the observability side of the stack.
#
#   scripts/clickstack.sh up       start it
#   scripts/clickstack.sh status   is it up, and are spans arriving?
#   scripts/clickstack.sh spans    what has been recorded, by service
#   scripts/clickstack.sh trace    the most recent full trace, nested
#   scripts/clickstack.sh down     stop and remove the container (keeps data)
#   scripts/clickstack.sh reset    wipe container AND data, back to first-run
#
# PORTS ARE NOT THE DEFAULTS, on purpose. The documented 8080/4317/4318 were all
# taken on the machine this was built on -- 8080 by an unrelated node process,
# 4317/4318 by Docker Desktop's own collector. Hard-coding the defaults would
# have meant a container that silently fails to bind. These are shifted and
# fixed so the endpoint in .env.local always matches.
set -euo pipefail
cd "$(dirname "$0")/.."

NAME=trueccu-clickstack
IMAGE=docker.hyperdx.io/hyperdx/hyperdx-all-in-one
# NAMED volumes, not the image's anonymous ones. `up` recreates the container,
# which orphans an anonymous volume and silently starts from empty -- so the
# traces that are our pipeline evidence would vanish on any restart. Named
# volumes survive re-creation, and MongoDB has to persist too or the team,
# login and ingest key are lost and the collector loses its receivers again.
VOL_CH=trueccu-clickstack-ch
VOL_MONGO=trueccu-clickstack-mongo
UI_PORT=8081
OTLP_GRPC=4417
OTLP_HTTP=4418

ch() { docker exec "$NAME" clickhouse-client -q "$1"; }

case "${1:-status}" in
  up)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker run -d --name "$NAME" \
      --restart unless-stopped \
      -v "$VOL_CH:/var/lib/clickhouse" \
      -v "$VOL_MONGO:/data/db" \
      -p "$UI_PORT:8080" -p "$OTLP_GRPC:4317" -p "$OTLP_HTTP:4318" "$IMAGE"
    echo "waiting for the UI..."
    for _ in $(seq 1 40); do
      [[ "$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$UI_PORT/" || true)" == "200" ]] && break
      sleep 3
    done
    cat <<EOF

  UI     http://localhost:$UI_PORT
  OTLP   http://localhost:$OTLP_HTTP  (http/protobuf)

FIRST RUN ONLY: create the account in the UI. Until a team exists, the bundled
collector has NO OTLP receivers at all -- they are pushed to it over OpAMP once
setup completes, so a fresh container silently drops everything you send it.
Then put the team's ingest key in .env.local as:
  OTEL_EXPORTER_OTLP_HEADERS=authorization=<key>
EOF
    ;;

  down)
    # Container only. The volumes stay, so `up` afterwards keeps the account,
    # the ingest key and every span. Use `reset` to actually wipe.
    docker rm -f "$NAME" >/dev/null 2>&1 && echo "removed $NAME (data volumes kept)" || echo "$NAME was not running"
    ;;

  reset)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker volume rm "$VOL_CH" "$VOL_MONGO" >/dev/null 2>&1 || true
    echo "removed container AND volumes -- next 'up' needs the UI setup again"
    ;;

  status)
    docker ps --filter "name=$NAME" --format '  container  {{.Status}}'
    echo -n "  receivers  "
    docker exec "$NAME" sh -c "netstat -tln 2>/dev/null | grep -qE ':(4317|4318) '" \
      && echo "OTLP up" || echo "NOT configured — finish setup in the UI"
    echo -n "  spans      "
    ch "SELECT count() FROM default.otel_traces" 2>/dev/null || echo "?"
    ;;

  spans)
    ch "SELECT ServiceName, SpanName, SpanKind, count() AS spans,
               round(avg(Duration)/1e6, 1) AS avg_ms
        FROM default.otel_traces
        GROUP BY ServiceName, SpanName, SpanKind
        ORDER BY spans DESC FORMAT PrettyCompactMonoBlock"
    ;;

  trace)
    # Most recent root span, then everything sharing its trace id.
    ch "WITH (SELECT TraceId FROM default.otel_traces
               WHERE ParentSpanId = '' ORDER BY Timestamp DESC LIMIT 1) AS t
        SELECT SpanName, SpanKind, round(Duration/1e6, 1) AS ms,
               SpanAttributes['clickhouse.read_rows']    AS read_rows,
               SpanAttributes['clickhouse.written_rows'] AS written_rows,
               SpanAttributes['db.statement']            AS statement
        FROM default.otel_traces WHERE TraceId = t
        ORDER BY Timestamp FORMAT PrettyCompactMonoBlock"
    ;;

  *)
    sed -n '2,10p' "$0"; exit 1
    ;;
esac
