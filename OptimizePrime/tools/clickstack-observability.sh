#!/usr/bin/env bash
# tools/clickstack-observability.sh — H7: the dashboard for OUR OWN telemetry.
#
# tools/clickstack-sources.sh points HyperDX at the concurrency VIEWS (the
# thing we ask ClickStack to visualise). This script is the other direction:
# it builds a dashboard over the OTLP metrics `sonyliv observe` emits (see
# cmd/sonyliv/observe.go, docs/OBSERVABILITY.md) — watermark lag, build-stage
# duration, and the reconcile gate. It reuses the local self-hosted stack's
# DEFAULT "Metrics"/"Logs" sources (every ClickStack team gets these the
# moment it is created — verified via `GET /sources` on a fresh team), so it
# does not create a connection or a source, only a dashboard.
#
# Same login-cookie pattern as tools/clickstack-sources.sh, and the same
# idempotent PUT-not-skip pattern tools/clickstack-cloud.sh uses for its
# dashboard — a re-run converges the remote dashboard to this script rather
# than leaving a stale hand-edit in place.
#
# NOTE: the local self-hosted API is NOT the Cloud control-plane API
# tools/clickstack-cloud.sh drives. Verified by hand (curl) to differ in three
# ways from the Cloud dashboard schema/verbs:
#   - a tile needs an explicit `id`;
#   - a line tile's chart config field is `source` (a bare source id), not
#     `sourceId`;
#   - update is PATCH /dashboards/:id, not PUT — confirmed by reading the
#     server's own router (routers/api/dashboards.js): PUT isn't registered
#     at all and returns 404, which reads exactly like "dashboard not found"
#     and sends you debugging the wrong thing if you assume the Cloud verb.
# There is also no /dashboards/validate route locally — POST /dashboards is
# itself the validation.
#
#   tools/clickstack-observability.sh
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

: "${CS_EMAIL:?set CS_EMAIL in .env}"
: "${CS_PASSWORD:?set CS_PASSWORD in .env}"

BASE=http://localhost:8000
JAR=$(mktemp -t cs-obs-cookies.XXXXXX)
trap 'rm -f "$JAR"' EXIT

curl -sf -o /dev/null "$BASE/health" || { echo "ClickStack is not up — run: make stack-up" >&2; exit 1; }

curl -sS -c "$JAR" -X POST "$BASE/login/password" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$CS_EMAIL\",\"password\":\"$CS_PASSWORD\"}" -o /dev/null -w "login -> HTTP %{http_code}\n" \
  || { echo "login failed — run tools/clickstack-bootstrap.sh first" >&2; exit 1; }

METRICS_SOURCE_ID=$(curl -sS -b "$JAR" "$BASE/sources" | python3 -c '
import json, sys
srcs = json.load(sys.stdin)
m = next((s for s in srcs if s.get("kind") == "metric"), None)
if not m:
    sys.exit("no default Metrics source found — has clickstack-bootstrap.sh run yet?")
print(m["id"])
')
[ -n "$METRICS_SOURCE_ID" ] || { echo "could not resolve the default Metrics source id" >&2; exit 1; }
echo "metrics source: $METRICS_SOURCE_ID"

DASH_NAME="SonyLIV pipeline health"

# Stable tile ids derived from a label, same trick tools/clickstack-cloud.sh
# uses for filter ids: a re-run updates the same tile instead of duplicating it.
tile_id() { python3 -c "import hashlib,sys; print(hashlib.md5(('sonyliv-tile-'+sys.argv[1]).encode()).hexdigest()[:24])" "$1"; }

DASH_JSON=$(python3 - "$METRICS_SOURCE_ID" "$DASH_NAME" <<'PYEOF'
import hashlib, json, sys
src, name = sys.argv[1], sys.argv[2]

def tid(label):
    return hashlib.md5(("sonyliv-tile-" + label).encode()).hexdigest()[:24]

def line(label, metric, x, y, w, h, group=None, agg="max"):
    cfg = {
        "displayType": "line",
        "source": src,
        "select": [{
            "aggFn": agg, "valueExpression": "Value", "alias": metric.split(".")[-1],
            "metricType": "gauge", "metricName": metric,
        }],
        "where": "", "whereLanguage": "sql",
    }
    if group:
        cfg["groupBy"] = group
    return {"id": tid(label), "name": label, "x": x, "y": y, "w": w, "h": h, "config": cfg}

dashboard = {
    "name": name,
    "tags": ["clickathon", "observability", "h7"],
    "tiles": [
        # The headline, per the brief: freshness next to the concurrency curve.
        line("Watermark sealed lag (s) — negative is healthy", "sonyliv.watermark.sealed_lag_seconds", 0, 0, 6, 4),
        line("Watermark healthy (1/0)", "sonyliv.watermark.healthy", 6, 0, 3, 4),
        line("Hour tier complete (1/0)", "sonyliv.watermark.hour_tier_complete", 9, 0, 3, 4),
        line("Build stage duration (s)", "sonyliv.build.stage_duration_seconds", 0, 4, 6, 4, group="stage"),
        line("Seconds since last build per stage", "sonyliv.build.seconds_since_last_run", 6, 4, 6, 4, group="stage"),
        line("Reconcile gate pass (1/0)", "sonyliv.reconcile.gate_pass", 0, 8, 4, 4),
        line("Reconcile max |delta|", "sonyliv.reconcile.max_abs_delta", 4, 8, 4, 4),
        line("Reconcile evidence age (s)", "sonyliv.reconcile.evidence_age_seconds", 8, 8, 4, 4),
    ],
}
print(json.dumps(dashboard))
PYEOF
)

EXISTING=$(curl -sS -b "$JAR" "$BASE/dashboards" | DASH_NAME="$DASH_NAME" python3 -c '
import json, os, sys
print(next((d.get("id","") for d in json.load(sys.stdin) if d.get("name") == os.environ["DASH_NAME"]), ""))
')

if [ -n "$EXISTING" ]; then
  curl -sS -b "$JAR" -X PATCH "$BASE/dashboards/$EXISTING" -H 'Content-Type: application/json' -d "$DASH_JSON" \
    -o /dev/null -w "updated dashboard '$DASH_NAME' ($EXISTING) -> HTTP %{http_code}\n"
else
  curl -sS -b "$JAR" -X POST "$BASE/dashboards" -H 'Content-Type: application/json' -d "$DASH_JSON" \
    -o /dev/null -w "created dashboard '$DASH_NAME' -> HTTP %{http_code}\n"
fi

echo
echo "HyperDX UI: http://localhost:8080 -> dashboard '$DASH_NAME'"
echo "  Metrics only exist from when 'sonyliv observe' first ran — set the time"
echo "  range to cover that run (e.g. last 1 hour), not the concurrency dataset's"
echo "  2026-07-14 -> 2026-07-26 window, which is unrelated data."
